"""Synchronous spawned Arena workers with one parent-owned batched policy.

Each wave waits for one decision or terminal result from every active slot.
Inference and episode assignment use slot order, independent of OS arrival
order. No model, vocabulary, or encoded transition is sent to an environment.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import multiprocessing as mp
from multiprocessing.connection import wait
import os
import random
import signal
import subprocess
import sys
import time
import traceback
import threading
import _thread

from ..contracts import Episode, PolicySelection, Transition


class RemoteWorkerError(RuntimeError):
    pass


class _Cancelled(Exception):
    pass


@dataclass
class TaskFactory:
    task_class: type
    config: object
    arena_root: object = None

    @classmethod
    def from_task(cls, task):
        if not hasattr(task, 'config'):
            raise TypeError('Parallel tasks must have a picklable config and accept Task(config, *, arena_root=...)')
        return cls(type(task), task.config, getattr(task, 'arena_root', None))

    def create(self):
        kwargs = {'arena_root': self.arena_root} if self.arena_root is not None else {}
        return self.task_class(self.config, **kwargs)


def _node_pid():
    native = sys.modules.get('gakumas_arena.engine.training')
    process = getattr(getattr(native, '_transport', None), 'process', None)
    return process.pid if process is not None and process.poll() is None else None


def _worker(connection, factory, cancel_event):
    task = None
    isolated = False
    watcher = None
    watcher_done = threading.Event()
    try:
        # Parent handles Ctrl-C and owns teardown. On POSIX every native child
        # belongs to this dedicated process group, including startup failures.
        def cancel_signal(signum, frame):
            raise _Cancelled()
        signal.signal(signal.SIGINT, cancel_signal)
        if os.name != 'nt':
            os.setsid()
            isolated = True
        def watch_cancellation():
            while not watcher_done.is_set():
                if cancel_event.wait(.1):
                    if watcher_done.is_set():
                        return
                    # The worker owns the Popen handle, including on Windows.
                    # Killing its own native helper unblocks a pending read;
                    # the main thread then unwinds through task.close().
                    native = sys.modules.get('gakumas_arena.engine.training')
                    if native is not None:
                        try:
                            native.close_training_worker()
                        except BaseException:
                            pass  # Main-thread finally repeats close and reports failures.
                    if not watcher_done.is_set():
                        _thread.interrupt_main()
                    return
        watcher = threading.Thread(target=watch_cancellation, daemon=True)
        watcher.start()
        task = factory.create()
        connection.send({'type': 'ready', 'pid': os.getpid(), 'isolated': isolated, 'node_pid': _node_pid()})
        while True:
            command = connection.recv()
            if command['type'] in ('close', 'cancel'):
                break
            if command['type'] != 'episode':
                raise ValueError('Unexpected parent command')
            seed, version = command['seed'], command['policy_version']
            random.seed(seed)
            import numpy as np
            np.random.seed(seed % 2**32)
            sequence, selection_ids = 0, {}
            started = time.perf_counter()

            def choose(context):
                nonlocal sequence
                request = sequence
                sequence += 1
                connection.send({'type': 'decision', 'request': request, 'context': context,
                                 'seed': seed, 'node_pid': _node_pid()})
                reply = connection.recv()
                if reply['type'] in ('cancel', 'close'):
                    raise _Cancelled()
                if reply['type'] != 'selection' or reply['request'] != request:
                    raise ValueError('Policy response does not match request')
                selection = reply['selection']
                if selection.encoded is not None:
                    raise ValueError('Encoded learner state was sent to an environment worker')
                selection_ids[id(selection)] = request
                return selection

            episode = task.run_episode(choose, seed=seed, policy_version=version)
            # Preserve precisely the transactions the Task committed. A failed
            # transaction may discard prior callbacks; never infer this from a
            # simple callback count or send an entire duplicate trajectory back.
            requests = [selection_ids[id(t.selection)] for t in episode.transitions]
            episode = replace(episode, transitions=[])
            connection.send({'type': 'done', 'episode': episode, 'requests': requests,
                             'seconds': time.perf_counter() - started, 'node_pid': _node_pid()})
    except (_Cancelled, EOFError, BrokenPipeError):
        pass
    except BaseException as error:
        try:
            connection.send({'type': 'error', 'error_type': type(error).__name__, 'message': str(error),
                             'traceback': traceback.format_exc(), 'node_pid': _node_pid(),
                             'pid': os.getpid(), 'isolated': isolated})
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        watcher_done.set()
        try:
            if task is not None and hasattr(task, 'close'):
                task.close()
        finally:
            if watcher is not None:
                watcher.join(timeout=6.)
            connection.close()


def _kill_tree(process, isolated, node_pids):
    """Only terminate processes belonging to the workers created by this call."""
    if os.name == 'nt':
        # Kill the tree while the Python parent still exists. Terminating Python
        # first would lose the tree relationship and can orphan the Node child.
        pids = [process.pid] if process.is_alive() else list(node_pids)
        for pid in pids:
            result = subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW, check=False)
            if result.returncode != 0:
                raise RuntimeError(f'Could not terminate owned worker tree {pid}: taskkill exit {result.returncode}')
    elif isolated:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.is_alive():
        process.terminate()


class SynchronousCollector:
    def __init__(self, task, policy_runner, *, workers):
        if type(workers) is not int or workers < 1:
            raise ValueError("Parallel collection workers must be a positive integer")
        if not callable(getattr(policy_runner, 'act_batch', None)):
            raise TypeError('Parallel collection requires PolicyRunner.act_batch')
        self.factory = TaskFactory.from_task(task)
        self.policy_runner, self.workers = policy_runner, workers
        self.processes, self.connections, self.isolated, self.node_pids = [], [], [], []
        self.last_worker_pids = []
        self.cancel_event = None

    def _wave(self, slots):
        pending, messages = set(slots), {}
        while pending:
            ready = wait([self.connections[i] for i in sorted(pending)], timeout=.2)
            for slot in sorted(pending):
                connection = self.connections[slot]
                if connection not in ready:
                    if not self.processes[slot].is_alive():
                        raise RemoteWorkerError(f'Environment slot {slot} exited with code {self.processes[slot].exitcode}')
                    continue
                try:
                    message = connection.recv()
                except (EOFError, BrokenPipeError, OSError) as error:
                    raise RemoteWorkerError(f'Environment slot {slot} disconnected') from error
                self.node_pids[slot] = {message['node_pid']} if message.get('node_pid') is not None else set()
                if 'isolated' in message:
                    if message['pid'] != self.processes[slot].pid:
                        raise RemoteWorkerError('Environment identity mismatch')
                    self.isolated[slot] = bool(message['isolated'])
                if message['type'] == 'error':
                    raise RemoteWorkerError(f"Environment slot {slot}: {message['error_type']}: {message['message']}\n{message['traceback']}")
                messages[slot] = message
            pending.difference_update(messages)
        return messages

    def close(self):
        if not self.processes:
            return
        if self.cancel_event is not None:
            self.cancel_event.set()
        # Cooperative cancellation lets a worker waiting at its policy callback
        # run task.close(). A busy engine gets a short grace period, then its
        # whole process tree is stopped. All workers are joined before returning.
        for connection in self.connections:
            try:
                connection.send({'type': 'close'})
            except (BrokenPipeError, EOFError, OSError):
                pass
            connection.close()
        deadline = time.monotonic() + 6.
        for process in self.processes:
            process.join(timeout=max(0., deadline - time.monotonic()))
        failures = []
        for slot, process in enumerate(self.processes):
            if process.is_alive() or process.exitcode not in (0, None):
                try:
                    _kill_tree(process, self.isolated[slot], self.node_pids[slot])
                except BaseException as error:
                    failures.append(str(error))
        for slot, process in enumerate(self.processes):
            process.join(timeout=1.)
            if process.is_alive():
                if os.name != 'nt' and self.isolated[slot]:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                process.join(timeout=5.)
            if process.is_alive():
                failures.append(f'Could not reap environment worker {process.pid}')
        self.processes, self.connections, self.isolated, self.node_pids = [], [], [], []
        self.cancel_event = None
        if failures:
            raise RuntimeError('; '.join(failures))

    def collect(self, seeds, *, policy_version, deterministic=False, on_episode=None):
        seeds = list(seeds)
        if not seeds or len(set(seeds)) != len(seeds):
            raise ValueError('Collection requires distinct episode seeds')
        if self.processes:
            raise RuntimeError('Collector is already running')
        context = mp.get_context('spawn')
        count = min(self.workers, len(seeds))
        episodes, active, next_index = {}, {}, 0
        self.last_worker_pids = []
        self.cancel_event = context.Event()
        try:
            for slot in range(count):
                parent, child = context.Pipe(duplex=True)
                process = context.Process(target=_worker, args=(child, self.factory, self.cancel_event), name=f'arena-slot-{slot}')
                process.start()
                child.close()
                self.processes.append(process)
                self.connections.append(parent)
                self.isolated.append(False)
                self.node_pids.append(set())
                self.last_worker_pids.append(process.pid)
            ready = self._wave(range(count))
            if any(message['type'] != 'ready' for message in ready.values()):
                raise RemoteWorkerError('Worker did not complete its startup handshake')

            def assign(slot):
                nonlocal next_index
                index = next_index
                next_index += 1
                active[slot] = {'index': index, 'seed': seeds[index], 'transitions': {}}
                self.connections[slot].send({'type': 'episode', 'seed': seeds[index], 'policy_version': policy_version})

            for slot in range(count):
                assign(slot)
            while active:
                messages = self._wave(active)
                decision_slots, contexts = [], []
                finished = []
                for slot in sorted(messages):
                    message, current = messages[slot], active[slot]
                    if message['type'] == 'done':
                        episode = message['episode']
                        if not isinstance(episode, Episode) or episode.seed != current['seed'] or episode.transitions:
                            raise RemoteWorkerError('Worker returned an invalid terminal episode envelope')
                        requests = message['requests']
                        if len(set(requests)) != len(requests) or requests != sorted(requests):
                            raise RemoteWorkerError('Worker returned invalid committed decision order')
                        try:
                            episode.transitions = [current['transitions'][request] for request in requests]
                        except KeyError as error:
                            raise RemoteWorkerError('Worker committed an unknown policy decision') from error
                        episodes[current['index']] = episode
                        finished.append((current['index'], episode, message['seconds']))
                        del active[slot]
                    elif message['type'] == 'decision':
                        if message['seed'] != current['seed'] or message['request'] in current['transitions']:
                            raise RemoteWorkerError('Worker decision identity mismatch')
                        decision_slots.append(slot)
                        contexts.append(message['context'])
                    else:
                        raise RemoteWorkerError('Unexpected worker message inside an episode')
                for _, episode, seconds in sorted(finished):
                    if on_episode is not None:
                        on_episode(episode, seconds)
                if decision_slots:
                    selections = self.policy_runner.act_batch(contexts, policy_version=policy_version,
                                                               deterministic=deterministic)
                    if len(selections) != len(contexts):
                        raise ValueError('Batched policy returned the wrong number of selections')
                    for slot, decision, selection in zip(decision_slots, contexts, selections):
                        if (not isinstance(selection, PolicySelection) or selection.policy_version != policy_version
                                or type(selection.action_index) is not int
                                or not 0 <= selection.action_index < len(decision.candidates)
                                or selection.encoded is None or selection.log_prob > 1e-6
                                or not math.isfinite(selection.log_prob) or not math.isfinite(selection.value)):
                            raise ValueError('Batched policy returned an invalid behavior selection')
                        request = messages[slot]['request']
                        active[slot]['transitions'][request] = Transition(decision, selection)
                        self.connections[slot].send({'type': 'selection', 'request': request,
                                                    'selection': replace(selection, encoded=None)})
                for slot in range(count):
                    if slot not in active and next_index < len(seeds):
                        assign(slot)
            return [episodes[i] for i in range(len(seeds))]
        finally:
            original = sys.exc_info()[1]
            try:
                self.close()
            except BaseException as cleanup_error:
                if original is None:
                    raise
                original.add_note(f'Environment cleanup also failed: {cleanup_error}')
                print(f'Environment cleanup also failed: {cleanup_error}', file=sys.stderr, flush=True)
