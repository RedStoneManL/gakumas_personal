"""Notebook subprocess logging with bounded, confirmed shutdown on interruption."""
from __future__ import annotations

from pathlib import Path
import signal
import subprocess


def stop_and_drain(process, *, grace_seconds=30, force_seconds=5):
    """Give the writer a chance to commit, then confirm it exited before returning.

    communicate drains stdout while waiting, so a full pipe cannot deadlock the
    graceful save. Forced termination loses only work since the last committed
    snapshot; it must not leave a second writer behind when a cell is rerun.
    """
    if not 0 < grace_seconds <= 30 or not 0 < force_seconds <= 5:
        raise ValueError("Shutdown timeouts must be bounded")
    try:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        try:
            return process.communicate(timeout=grace_seconds)[0] or ""
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                process.terminate()
        try:
            return process.communicate(timeout=force_seconds)[0] or ""
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                process.kill()
        try:
            return process.communicate(timeout=force_seconds)[0] or ""
        except subprocess.TimeoutExpired as error:
            # A descendant could keep the read pipe open after the writer died.
            # Closing that pipe is safe only after confirming the writer exited.
            process.wait(timeout=force_seconds)
            if process.stdout is not None:
                process.stdout.close()
            tail = error.output or ""
            return tail.decode("utf-8", errors="replace") if isinstance(tail, bytes) else tail
    except BaseException:
        # Even a second interrupt must not silently leave a training writer live.
        if process.poll() is None:
            process.kill()
        process.wait(timeout=force_seconds)
        raise


def run_logged(command, logfile, *, cwd, env):
    logfile = Path(logfile)
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", bufsize=1)
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line); log.flush()
            code = process.wait()
        except KeyboardInterrupt:
            print("\n正在等待训练进程保存并退出（最多30秒，之后强制停止）……", flush=True)
            tail = stop_and_drain(process)
            if tail:
                print(tail, end="", flush=True)
                log.write(tail); log.flush()
            print("旧训练进程已退出；可重新运行此单元格。", flush=True)
            raise
        except BaseException as error:
            # Drive log writes can fail while the learner still runs. Reap it
            # before returning control; do not write again to the failed log.
            try:
                stop_and_drain(process)
            except BaseException as shutdown_error:
                error.add_note(f"Subprocess shutdown also raised {type(shutdown_error).__name__}: {shutdown_error}")
            raise
        finally:
            if process.stdout is not None:
                process.stdout.close()
    if code:
        raise RuntimeError(f"子进程退出码 {code}；日志：{logfile}")
    return code
