"""One owned, nonblocking Notebook training process with bounded live output."""
from __future__ import annotations

from collections import deque
import html
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import threading
import time
import uuid


_ACTIVE = None
_START_LOCK = threading.Lock()
CONTROL_LIMITS = dict.fromkeys(('workers', 'episodes_per_update', 'minibatch_size', 'microbatch_size'))


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        with temporary.open('x', encoding='utf8') as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _host_id():
    boot = Path('/proc/sys/kernel/random/boot_id')
    return platform.node() + ':' + (boot.read_text().strip() if boot.is_file() else platform.platform())


def _pid_alive(pid):
    if type(pid) is not int or pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def write_runtime_control(persistent_run, *, workers, episodes_per_update,
                          minibatch_size, microbatch_size):
    """Atomically request four execution settings without changing base identity."""
    values = dict(workers=workers, episodes_per_update=episodes_per_update,
                  minibatch_size=minibatch_size, microbatch_size=microbatch_size)
    for key in CONTROL_LIMITS:
        if type(values[key]) is not int or values[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    if microbatch_size > minibatch_size:
        raise ValueError('microbatch_size must not exceed minibatch_size')
    values['_request_id'] = uuid.uuid4().hex
    run = Path(persistent_run).resolve()
    path = run.parent / '_runtime_controls' / (run.name + '.json')
    _atomic_json(path, values)
    return path


class NotebookSession:
    def __init__(self, process, logfile, log_stream, persistent_run, lease, *, display):
        self.process, self.logfile, self._log = process, logfile, log_stream
        self.persistent_run, self._lease = persistent_run, lease
        self._token = uuid.uuid4().hex
        self._tail, self._tail_lock = deque(maxlen=200), threading.Lock()
        self.error = None
        self._display = None
        self._last_display = 0.
        self._finished = threading.Event()
        self._write_lease()
        if display:
            try:
                from IPython.display import HTML, display as show
                self._display = show(HTML(self._html()), display_id=True)
            except Exception as error:
                # Console persistence and training are independent of a UI client.
                self._append(f'Live display unavailable: {error}; full log: {logfile}')
        self._reader = threading.Thread(target=self._read_output, name='hif-notebook-log-reader', daemon=True)
        self._reader.start()
        self._ticker = threading.Thread(target=self._update_display, name='hif-notebook-display', daemon=True)
        self._ticker.start()

    def _write_lease(self):
        _atomic_json(self._lease, {'schema': 'hif-notebook-owned-session/1', 'token': self._token,
            'host_id': _host_id(), 'pid': self.process.pid, 'returncode': self.process.poll(),
            'persistent_run': str(self.persistent_run), 'logfile': str(self.logfile), 'error': self.error})

    def _append(self, line):
        text = line.rstrip('\r\n')
        if len(text) > 4000:
            text = text[:4000] + ' … [display truncated; full line in console log]'
        with self._tail_lock:
            self._tail.append(text)

    def tail(self):
        with self._tail_lock:
            return '\n'.join(self._tail)

    def status(self):
        control = {}
        folder = self.persistent_run.parent / '_runtime_controls'
        for label, path in (('desired', folder / (self.persistent_run.name + '.json')),
                            ('runtime', folder / (self.persistent_run.name + '.status.json'))):
            if path.is_file():
                try:
                    control[label] = json.loads(path.read_text(encoding='utf8'))
                except (OSError, ValueError) as error:
                    control[label + '_read_error'] = str(error)
        return {'pid': self.process.pid, 'running': self.process.poll() is None,
                'returncode': self.process.poll(), 'logfile': str(self.logfile),
                'persistent_run': str(self.persistent_run), 'error': self.error, 'control': control}

    def _html(self):
        state = self.status()
        label = '训练运行中' if state['running'] else f'训练已退出，退出码 {state["returncode"]}'
        if self.error:
            label += '；日志/会话错误：' + self.error
        control = html.escape(json.dumps(state['control'], ensure_ascii=False, indent=2)[:6000])
        return ('<b>' + html.escape(label) + '</b><br><small>完整日志：' + html.escape(str(self.logfile)) +
                '</small><details open><summary>运行参数：请求 / 实际生效 / 待生效 / 错误</summary><pre>' +
                control + '</pre></details><pre style="max-height:480px;overflow:auto;white-space:pre-wrap">' +
                html.escape(self.tail()) + '</pre>')

    def _update_display(self):
        while not self._finished.wait(2.):
            self.refresh(force=False)

    def refresh(self, *, force=True):
        if self._display is not None and (force or time.monotonic() - self._last_display >= 2.):
            try:
                from IPython.display import HTML
                self._display.update(HTML(self._html()))
                self._last_display = time.monotonic()
            except Exception:
                self._display = None
        return self.status()

    def _read_output(self):
        try:
            for line in self.process.stdout:
                self._log.write(line); self._log.flush()
                self._append(line)
                self.refresh(force=False)
            self.process.wait()
        except BaseException as error:
            self.error = f'{type(error).__name__}: {error}'
            self._append('Session error: ' + self.error)
            try:
                self.terminate_owned()
            except BaseException as stop_error:
                self.error += f'; shutdown failed: {stop_error}'
        finally:
            for stream in (self._log, self.process.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except Exception as error:
                        self.error = (self.error or '') + f'; output close failed: {error}'
            try:
                self._write_lease()
            except Exception as error:
                self.error = (self.error or '') + f'; session status write failed: {error}'
            self._finished.set()
            self.refresh()

    def request_stop(self):
        """Nonblocking normal stop: finish a safe boundary and publish to Drive."""
        if not (self.persistent_run / 'run-identity.json').is_file():
            raise RuntimeError('运行仍在初始化/迁移；看到运行初始化完成后再请求安全停止。')
        path = self.persistent_run / 'STOP'
        path.touch(exist_ok=True)
        self._append('已请求安全停止；等待当前安全边界保存，训练进程尚未因此立即退出。')
        self.refresh()
        return path

    def terminate_owned(self, *, grace_seconds=5):
        """Explicit emergency operation, restricted to this owned Popen handle."""
        if not 0 < grace_seconds <= 10:
            raise ValueError('Emergency shutdown grace must be in (0, 10] seconds')
        process = self.process
        if process.poll() is None:
            process.send_signal(signal.SIGINT if os.name != 'nt' else signal.SIGTERM)
            try:
                process.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=3)
        return process.returncode

    def wait(self, timeout=30):
        """Bounded test/inspection helper; the Notebook start cell never calls it."""
        if not self._finished.wait(timeout):
            raise TimeoutError('Training session is still active')
        return self.status()


def start_session(command, logfile, *, cwd, env, persistent_run, display=True):
    """Return immediately; retain a strong global reference and reject duplicates."""
    global _ACTIVE
    persistent_run = Path(persistent_run).resolve()
    lease = persistent_run.parent / '_notebook_sessions' / (persistent_run.name + '.json')
    logfile = Path(logfile).resolve()
    with _START_LOCK:
        if _ACTIVE is not None and (_ACTIVE.process.poll() is None or not _ACTIVE._finished.is_set()):
            raise RuntimeError('此 Notebook 已有训练进程运行；请使用下面的控制格，或先请求安全停止。')
        if lease.exists():
            previous = json.loads(lease.read_text(encoding='utf8'))
            if (previous.get('host_id') == _host_id() and previous.get('returncode') is None
                    and _pid_alive(previous.get('pid'))):
                raise RuntimeError('此运行仍有存活训练进程，禁止重复启动；当前 kernel 不拥有该旧进程。')
        logfile.parent.mkdir(parents=True, exist_ok=True)
        log = logfile.open('a', encoding='utf8')
        process = None
        try:
            log.write('\n--- Notebook training session start ---\n'); log.flush()
            process = subprocess.Popen(command, cwd=cwd, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding='utf8', errors='replace', bufsize=1,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                start_new_session=os.name != 'nt')
            _ACTIVE = NotebookSession(process, logfile, log, persistent_run, lease, display=display)
        except BaseException:
            if process is not None and process.poll() is None:
                process.kill(); process.wait(timeout=5)
            if process is not None and process.stdout is not None:
                process.stdout.close()
            log.close()
            raise
        return _ACTIVE
