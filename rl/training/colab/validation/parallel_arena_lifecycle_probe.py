"""CPU-only spawn/Pipe isolation and native-worker cleanup experiment.

Uses deterministic control policies, never contributes PPO trajectories. Run as
a real Python script (spawn requires an importable main), with training on
PYTHONPATH. It only terminates process trees created by this experiment.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import multiprocessing as mp
from multiprocessing.connection import wait
import os
from pathlib import Path
import signal
import subprocess
import time


class ProbeCancelled(Exception):
    pass


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()


def node_process_alive(pid):
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only.
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


def worker(connection, arena_root):
    if os.name != 'nt':
        os.setsid()
    from gakumas_training.arena_adapter.environment import ensure_arena, close_arena
    ensure_arena(arena_root)
    import gakumas_arena.engine.training as native
    from gakumas_training.tasks import ExamScoreTask, FullProduceTask
    tasks = {}
    last_process = None
    try:
        connection.send({'kind': 'ready', 'pid': os.getpid()})
        while True:
            command = connection.recv()
            if command['kind'] == 'stop':
                break
            task_name, seed = command['task'], command['seed']
            if task_name not in tasks:
                tasks[task_name] = (FullProduceTask if task_name == 'full_produce' else ExamScoreTask)(
                    arena_root=arena_root)
            trace = []
            def policy(context):
                nonlocal last_process
                if native._transport.process is not None:
                    last_process = native._transport.process
                trace.append(fingerprint(asdict(context)))
                connection.send({'kind': 'decision', 'context': context,
                    'request': len(trace), 'node_pid': last_process.pid if last_process else None})
                answer = connection.recv()
                if answer['kind'] != 'selection':
                    raise ProbeCancelled('Parent cancelled this in-flight episode')
                return answer['selection']
            try:
                episode = tasks[task_name].run_episode(policy, seed=seed, policy_version=19)
                connection.send({'kind': 'episode', 'task': task_name, 'seed': seed,
                    'raw_score': episode.raw_score, 'termination': episode.termination,
                    'trace_sha256': fingerprint(trace), 'transitions': len(episode.transitions),
                    'kinds': dict(Counter(t.decision.kind for t in episode.transitions)),
                    'node_pid': native._transport.process.pid})
            except ProbeCancelled as error:
                connection.send({'kind': 'cancelled', 'error': str(error), 'episode_returned': False})
    except (EOFError, BrokenPipeError, ConnectionResetError):
        pass
    finally:
        close_arena()
        try:
            connection.send({'kind': 'closed', 'node_returncode':
                last_process.poll() if last_process is not None else None})
        except (EOFError, BrokenPipeError, ConnectionResetError, OSError):
            pass
        connection.close()


def force_stop_owned_worker(process):
    if not process.is_alive():
        return {'already_stopped': True}
    diagnostics = {}
    if os.name == 'nt':
        # Kill the tree while its Python parent still exists; never terminate
        # Python first and then hope its detached Node descendant is discoverable.
        result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
            capture_output=True, timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        diagnostics = {'taskkill_returncode': result.returncode,
                       'taskkill_stdout': result.stdout.decode(errors='replace'),
                       'taskkill_stderr': result.stderr.decode(errors='replace')}
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.join(timeout=10)
    if process.is_alive():
        raise RuntimeError(f'Own probe worker failed to stop: {diagnostics}')
    return diagnostics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--arena-root', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--skip-force', action='store_true',
                        help='Skip force-stop when the local sandbox forbids process-tree termination')
    args = parser.parse_args()
    from gakumas_training.contracts import PolicySelection
    context = mp.get_context('spawn')
    processes, channels = [], []
    started = time.monotonic()
    schedules = [[('full_produce', 1961), ('exam_score', 1961), ('exam_score', 1962)],
                 [('exam_score', 1962), ('exam_score', 1961), ('full_produce', 1961)]]
    report = {'scope': 'CPU process/RNG isolation and lifecycle control probe; '
                       'no throughput claim, neural inference or PPO training.',
              'platform': os.name, 'start_method': 'spawn', 'episodes': [[], []]}
    def start_one():
        parent, child = context.Pipe()
        process = context.Process(target=worker, args=(child, str(Path(args.arena_root).resolve())))
        process.start()
        child.close()  # Parent must not retain the peer end and suppress EOF.
        processes.append(process); channels.append(parent)
        if not parent.poll(30):
            raise TimeoutError('Spawn worker did not start')
        ready = parent.recv()
        assert ready == {'kind': 'ready', 'pid': process.pid}, ready
        return process, parent
    try:
        for _ in range(2):
            start_one()
        pending = {channels[i]: (i, 0) for i in range(2)}
        for connection, (i, index) in pending.items():
            task, seed = schedules[i][index]
            connection.send({'kind': 'run', 'task': task, 'seed': seed})
        while pending:
            ready = wait(list(pending), timeout=60)
            if not ready:
                raise TimeoutError('No CPU decision/result for 60 seconds')
            for connection in ready:
                i, index = pending[connection]
                message = connection.recv()
                if message['kind'] == 'decision':
                    decision = message['context']
                    action_index = next((j for j, action in enumerate(decision.candidates)
                        if action.get('type') == 'play' or action.get('action_type') == 'audition_accept'), 0)
                    connection.send({'kind': 'selection',
                        'selection': PolicySelection(action_index, 0., 0., 19)})
                elif message['kind'] == 'episode':
                    report['episodes'][i].append(message)
                    index += 1
                    if index == len(schedules[i]):
                        del pending[connection]
                    else:
                        pending[connection] = (i, index)
                        task, seed = schedules[i][index]
                        connection.send({'kind': 'run', 'task': task, 'seed': seed})
                else:
                    raise AssertionError(message)
        left = {(r['task'], r['seed']): r for r in report['episodes'][0]}
        right = {(r['task'], r['seed']): r for r in report['episodes'][1]}
        for key in left:
            for field in ('trace_sha256', 'raw_score', 'termination', 'transitions'):
                assert left[key][field] == right[key][field], (key, field)
        assert left['exam_score', 1961]['trace_sha256'] != left['exam_score', 1962]['trace_sha256']
        node_ids = [{r['node_pid'] for r in rows} for rows in report['episodes']]
        assert len(node_ids[0]) == len(node_ids[1]) == 1
        assert node_ids[0].isdisjoint(node_ids[1])
        report['same_seed_different_interleaving_identical'] = True
        report['different_seed_trace_differs'] = True
        report['worker_pids'] = [p.pid for p in processes]
        report['node_pids'] = [list(ids)[0] for ids in node_ids]
        # Cancel on a real decision, then close normally. No Episode is emitted.
        channels[0].send({'kind': 'run', 'task': 'exam_score', 'seed': 1963})
        assert channels[0].poll(30)
        assert channels[0].recv()['kind'] == 'decision'
        channels[0].send({'kind': 'cancel'})
        assert channels[0].poll(30)
        report['cancel'] = channels[0].recv()
        assert report['cancel']['kind'] == 'cancelled'
        channels[0].send({'kind': 'stop'})
        assert channels[0].poll(30)
        report['normal_close'] = channels[0].recv()
        assert report['normal_close']['kind'] == 'closed'
        processes[0].join(10)
        assert not processes[0].is_alive()
        assert not node_process_alive(report['node_pids'][0])
        # Parent disconnect while child is waiting for inference must reach finally.
        channels[1].send({'kind': 'run', 'task': 'exam_score', 'seed': 1964})
        assert channels[1].poll(30)
        assert channels[1].recv()['kind'] == 'decision'
        channels[1].close()
        processes[1].join(10)
        assert not processes[1].is_alive()
        assert not node_process_alive(report['node_pids'][1])
        report['pipe_disconnect_cleaned_child_and_node'] = True
        if args.skip_force:
            report['forced_tree_stop_cleaned_node'] = None
            report['forced_tree_stop_scope'] = 'Skipped by explicit flag; no forced-stop coverage claimed'
        else:
            # Independent third worker tests forced tree termination while blocked.
            process, connection = start_one()
            connection.send({'kind': 'run', 'task': 'exam_score', 'seed': 1965})
            assert connection.poll(30)
            message = connection.recv()
            assert message['kind'] == 'decision'
            report['forced_tree_stop_diagnostics'] = force_stop_owned_worker(process)
            assert not node_process_alive(message['node_pid'])
            report['forced_tree_stop_cleaned_node'] = True
        report['seconds'] = time.monotonic() - started
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print(json.dumps({k: v for k, v in report.items() if k != 'episodes'}, ensure_ascii=False))
    finally:
        for connection in channels:
            connection.close()
        for process in processes:
            process.join(timeout=2)
            if process.is_alive():
                force_stop_owned_worker(process)


if __name__ == '__main__':
    main()
