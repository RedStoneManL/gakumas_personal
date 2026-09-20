"""Public-only Arena client; no game controls and no search over real RNG."""
from __future__ import annotations

import multiprocessing as mp
import os
import sys
import traceback
from pathlib import Path


def arena_module(arena):
    root = str(Path(arena).resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    from gakumas_arena.engine import training
    return training


def submit(exam, command):
    if command["method"] == "choose":
        return exam.choose(command["indices"], decision_version=command["decision_version"])
    return exam.act(command["action"])


def worker(connection, arena, expected_hash):
    try:
        api = arena_module(arena)
        if api.content_version()["effective_sha256"] != expected_hash:
            raise ValueError("Arena changed after binding; verify the new version first")
        exam = None
        from gakumas_arena.engine.search import SearchClient
        recorder = SearchClient(max_worlds=2)
        while True:
            command, payload = connection.recv()
            if command == "close":
                break
            if command == "reset":
                entry, seed = payload
                if exam is not None:
                    exam.close()
                exam = recorder.create_recorded_exam(entry, seed=seed)
                answer = {"observation": exam.observe(), "entry": entry}
            elif command == "step":
                if exam is None:
                    raise RuntimeError("step without reset")
                answer = {"observation": submit(exam, payload)}
            elif command == 'encode':
                from draftrl.fast_collate import prepare_encoded
                prepared = prepare_encoded(payload)._prepared_input
                connection.send((True, {'prepared': prepared}))
                continue
            elif command == 'history':
                if exam is None:
                    raise RuntimeError('history requested before reset')
                connection.send((True, {'history': exam.export_public_history()}))
                continue
            else:
                raise ValueError(command)
            obs = answer["observation"]
            if obs["version"]["effective_sha256"] != expected_hash:
                raise ValueError("Arena effective version changed mid-run")
            if (os.environ.get('GAKUMAS_RELATIONAL_SEMANTICS') and not obs.get('choice')
                    and not obs['result']['terminated'] and not obs['result']['truncated']):
                from draftrl.encoding import encode_exam
                from draftrl.fast_collate import prepare_encoded
                from draftrl.compact_input import compact_prepared
                answer['encoded'] = compact_prepared(prepare_encoded(encode_exam(obs)))
            connection.send((True, answer))
    except EOFError:
        pass
    except BaseException:
        try:
            connection.send((False, traceback.format_exc()))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        if 'recorder' in locals():
            recorder.close()
        if "api" in locals():
            api.close_training_worker()
        connection.close()


class Workers:
    def __init__(self, number, arena, expected_hash):
        ctx = mp.get_context("spawn")
        self.connections, self.processes = [], []
        for _ in range(number):
            parent, child = ctx.Pipe()
            process = ctx.Process(target=worker, args=(child, arena, expected_hash), daemon=True)
            process.start(); child.close()
            self.connections.append(parent); self.processes.append(process)

    def send(self, index, command, payload):
        self.connections[index].send((command, payload))

    def receive(self, index):
        pipe = self.connections[index]
        if not pipe.poll(90):
            raise TimeoutError("Arena worker timed out; latest completed batch is resumable")
        ok, value = pipe.recv()
        if not ok:
            raise RuntimeError(value)
        return value

    def prepare_encoded(self, indices, examples):
        path = os.environ.get('GAKUMAS_RELATIONAL_SEMANTICS')
        if not path:
            return examples
        result = list(examples)
        pending = []
        for position, (index, encoded) in enumerate(zip(indices, examples)):
            cached = getattr(encoded, '_prepared_input', None)
            if cached is None or cached[0] != path:
                self.send(index, 'encode', encoded)
                pending.append((position, index))
        for position, index in pending:
            encoded = result[position]
            encoded._prepared_input = self.receive(index)['prepared']
            encoded.__dict__.pop('_relational_cached', None)
        return result

    def public_history(self, index):
        self.send(index, 'history', None)
        return self.receive(index)['history']

    def close(self):
        for pipe in self.connections:
            try:
                pipe.send(("close", None))
            except (BrokenPipeError, EOFError, OSError):
                pass
        for process in self.processes:
            process.join(timeout=3)
            if process.is_alive():
                process.terminate(); process.join(timeout=3)
        for pipe in self.connections:
            pipe.close()
