"""Public-history conditioned search over resident, isolated native JS worlds.

No real exam object, private snapshot, hidden deck, or real RNG is accepted by
the sampler. Recording uses an independent live session API; models receive
only ``world.observe()``. This module never starts or alters RL training.
"""
from __future__ import annotations

import atexit
import copy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

from .training import TrainingError, content_version, _source_stamp

HERE = Path(__file__).resolve().parent
SEARCH_SCHEMA = "arena-public-search/1"
_LOADED_SEARCH_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def search_content_version():
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != _LOADED_SEARCH_SHA:
        raise TrainingError("version_mismatch", "search.py", "restart Python after source changes")
    base = content_version()
    files = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
             for name in ("search.py", "search_loader.mjs", "search_worker.mjs")}
    return {"schema_version": SEARCH_SCHEMA, "base_effective_sha256": base["effective_sha256"],
            "search_sha256": hashlib.sha256(_canonical({"base": base, "files": files}).encode()).hexdigest(),
            "search_files_sha256": files, "posterior_model": "draw-conditioned-sequential-importance/1"}


def _stamp():
    return _source_stamp()+tuple((name,(HERE/name).stat().st_mtime_ns,(HERE/name).stat().st_size)
                                for name in ("search.py","search_loader.mjs","search_worker.mjs"))


def search_capabilities():
    return {"schema_version": SEARCH_SCHEMA, "version": search_content_version(),
            "sampling": "finite likelihood-weighted public-history posterior",
            "branching": "resident state copy; no episode replay",
            "pending_choice": "replay only the single in-flight native command",
            "unsupported": ["private_snapshot_input", "actual_world_fork_for_sampling", "linkContest",
                            "external_peek_or_known_bottom_not_in_native_public_projection",
                            "unknown_native_DSL_or_content", "missing_initial_public_history"],
            "production_training_enabled": False,
            "training_activation_owner": "RL collector and checkpoint migration; per-root sampler status gate required"}


@dataclass(frozen=True)
class SearchBudget:
    milliseconds: int = 5000
    candidates: int = 512
    native_actions: int = 200000
    rule_operations: int = 1000000
    rng_calls: int = 2000000
    replay_entries: int = 100000

    def payload(self):
        result = asdict(self)
        for key, value in result.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{key} must be a nonnegative integer")
        if self.milliseconds > 60000:
            raise ValueError("one request is limited to 60 seconds; use explicit bounded batches")
        return result


def public_history(initial_observation, *, initial_draws=None):
    """Create a history for an existing public-only recorder.

    Without draw traces sampling is still full-history rejection, with explicit
    budgets; use RecordedExam for efficient public draw-conditioned proposals.
    Never synthesize a draw trace by guessing from the latest hand.
    """
    initial = {"observation": copy.deepcopy(initial_observation)}
    if initial_draws is not None:
        initial["draws"] = list(initial_draws)
    return {"schema_version": "arena-public-history/1", "initial": initial, "steps": []}


def append_public_transition(history, command, observation, *, draws=None):
    if command.get("type") in ("choice_append", "choice_finish"):
        raise ValueError("history must store the single committed native choose, not sub-selections")
    result = copy.deepcopy(history)
    record = {"command": copy.deepcopy(command), "observation": copy.deepcopy(observation)}
    if draws is not None:
        record["draws"] = list(draws)
    result["steps"].append(record)
    return result


class SearchWorld:
    """Opaque execution handle. Its identifier must not be a policy feature."""
    def __init__(self, client, handle):
        self._client, self._handle = client, handle

    def observe(self, *, budget=None):
        result = self._client._request({"op": "observe", "handle": self._handle}, budget=budget)
        self._client._require_ok(result)
        return result["view"]

    def step(self, command, *, budget=None, cancel=None):
        return self._client._request({"op": "step", "handle": self._handle, "command": command},
                                     budget=budget, cancel=cancel)

    def clone(self, *, budget=None):
        result = self._client._request({"op": "clone", "handle": self._handle}, budget=budget)
        self._client._require_ok(result)
        return SearchWorld(self._client, result["handle"])

    def release(self):
        if self._handle is not None:
            result = self._client._request({"op": "release", "handle": self._handle})
            self._handle = None
            return result

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release()


class RecordedExam:
    """Live native exam plus complete public action/observation/draw history.

    The seed stays outside its exported history. This real-world handle cannot
    be branched. Existing TrainingExam remains unchanged and available.
    """
    def __init__(self, client, entry, *, seed=0, budget=None):
        result = client._request({"op": "record_create", "entry": entry, "seed": seed}, budget=budget)
        client._require_ok(result)
        self._world = SearchWorld(client, result["handle"])
        self._entry = copy.deepcopy(entry)
        self._view = result["view"]
        self._history = public_history(self._view["observation"], initial_draws=result["draws"])
        self.last_cost = result["cost"]

    def observe(self):
        return copy.deepcopy(self._view["observation"])

    def export_entry(self):
        return copy.deepcopy(self._entry)

    def export_public_history(self):
        return copy.deepcopy(self._history)

    def _submit(self, command, **kwargs):
        if command.get('type') in ('choice_append', 'choice_finish'):
            raise ValueError('record only committed native choose commands; keep partial selections in the search tree')
        result = self._world.step(command, **kwargs)
        self._world._client._require_ok(result)
        self._view = result["view"]
        self.last_cost = result["cost"]
        self._history = append_public_transition(self._history, command, self.observe(), draws=result["draws"])
        return self.observe()

    def act(self, action, **kwargs):
        return self._submit(copy.deepcopy(action), **kwargs)

    def choose(self, indices, *, decision_version, **kwargs):
        return self._submit({"type": "choose", "indices": list(indices),
                             "decision_version": decision_version}, **kwargs)

    def close(self):
        return self._world.release()


class SearchClient:
    """One serial, independently cancellable search worker; use one per process.

    Search handles are resident and bounded. Native deadline failures preserve
    the touched handle. External cancellation kills only this search worker,
    invalidating all its handles; cost is then explicitly incomplete.
    """
    def __init__(self, *, node=None, max_worlds=256):
        if type(max_worlds) is not int or not 1 <= max_worlds <= 4096:
            raise ValueError("max_worlds must be in 1..4096")
        self.node = node or shutil.which("node")
        if not self.node:
            raise TrainingError("dependency", "node", "Node.js is required")
        self.version = search_content_version()
        self._source_stamp = _stamp()
        self.base_version = {k: v for k, v in content_version().items() if k != "files_sha256"}
        self.max_worlds, self.owner_pid = max_worlds, os.getpid()
        self._lock, self._output = threading.Lock(), queue.Queue()
        self._process = subprocess.Popen(
            [self.node, "--no-warnings", "--loader", (HERE / "search_loader.mjs").as_uri(),
             str(HERE / "search_worker.mjs")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self._stderr = []
        process = self._process

        def reader():
            for line in process.stdout:
                self._output.put(line)
            self._output.put(None)

        def errors():
            for line in process.stderr:
                self._stderr.append(line.rstrip())
                self._stderr[:] = self._stderr[-8:]

        threading.Thread(target=reader, daemon=True).start()
        threading.Thread(target=errors, daemon=True).start()
        atexit.register(self.close)
        self.last_cost = None
        self.total_cost = {}

    @staticmethod
    def _require_ok(result):
        if result.get("status") not in ("ok", "terminal"):
            raise TrainingError(result.get("status", "search_error"), "search", result.get("message", result.get("status")))

    def _request(self, request, *, budget=None, cancel=None):
        if os.getpid() != self.owner_pid:
            raise TrainingError("wrong_process", "search", "create a SearchClient in the child process")
        if self._source_stamp != _stamp():
            raise TrainingError("version_mismatch", "search", "source changed; recreate the client in a fresh Python process")
        budget = budget or SearchBudget()
        payload = budget.payload()
        with self._lock:
            if self._process is None:
                return {"status": "closed", "valid_for_search": False, "final_score": None,
                        "search_version": self.version}
            started = time.monotonic()
            progress = None
            try:
                self._process.stdin.write(_canonical({**request, "budget": {**payload, "max_worlds": self.max_worlds}}) + "\n")
                self._process.stdin.flush()
                while True:
                    if cancel is not None and cancel.is_set():
                        self.close()
                        return {"status": "cancelled", "valid_for_search": False, "final_score": None,
                                "search_version": self.version,
                                "cost": {"last_checkpoint": progress, "cost_complete": False,
                                         "milliseconds": (time.monotonic()-started)*1000}, "handles_invalidated": True}
                    if time.monotonic()-started > budget.milliseconds/1000 + 5:
                        self.close()
                        return {"status": "worker_timeout", "valid_for_search": False, "final_score": None,
                                "search_version": self.version,
                                "cost": {"last_checkpoint": progress, "cost_complete": False,
                                         "milliseconds": (time.monotonic()-started)*1000}, "handles_invalidated": True}
                    try:
                        line = self._output.get(timeout=0.02)
                    except queue.Empty:
                        continue
                    if line is None:
                        raise RuntimeError("search worker exited: " + " | ".join(self._stderr))
                    result = json.loads(line)
                    if "progress" in result:
                        progress = result["progress"]
                        continue
                    result["search_version"] = self.version
                    for item in [result, *result.get("results", [])]:
                        if "view" in item:
                            item["view"]["observation"]["version"] = copy.deepcopy(self.base_version)
                    self.last_cost = result.get("cost")
                    for key, value in (self.last_cost or {}).items():
                        if type(value) in (int, float):
                            self.total_cost[key] = self.total_cost.get(key, 0) + value
                    return result
            except (OSError, RuntimeError, ValueError) as error:
                self.close()
                raise TrainingError("transport", "search_worker", str(error)) from error

    def sample_public_worlds(self, public_entry, public_history, *, search_seed, particles=8,
                             partial_selection=(), budget=None, min_ess_fraction=0.5, cancel=None):
        if type(search_seed) is not int or not 0 <= search_seed < 2**32:
            raise ValueError("an independent uint32 search_seed is required")
        if type(particles) is not int or not 1 <= particles <= 128:
            raise ValueError("particles must be in 1..128")
        if not math.isfinite(min_ess_fraction) or not 0 <= min_ess_fraction <= 1:
            raise ValueError("min_ess_fraction must be in 0..1")
        if set(public_history) != {"schema_version", "initial", "steps"}:
            raise ValueError("only public history fields accepted; no snapshots or RNG")
        for record in [public_history["initial"], *public_history["steps"]]:
            version = record["observation"].get("version")
            if not version or version.get("effective_sha256") != self.version["base_effective_sha256"]:
                raise TrainingError("version_mismatch", "history", "history must include the current native content version")
        budget = budget or SearchBudget()
        result = self._request({"op": "sample", "entry": public_entry, "history": public_history,
                                "search_seed": search_seed, "particles": particles,
                                "partial_selection": list(partial_selection),
                                "max_candidates": budget.candidates, "min_ess_fraction": min_ess_fraction},
                               budget=budget, cancel=cancel)
        result["worlds"] = [SearchWorld(self, handle) for handle in result.pop("handles", [])]
        return result

    def create_recorded_exam(self, entry, *, seed=0, budget=None):
        """Create a live recorder in THIS worker.

        Use a dedicated recording client for actual episodes, separate from
        the cancellable sampling client. Hard cancellation invalidates every
        handle of its owning client, including any diagnostic recorder there.
        """
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("seed must be uint32")
        return RecordedExam(self, entry, seed=seed, budget=budget)

    def step_batch(self, jobs, *, budget=None, cancel=None):
        for world, _ in jobs:
            if world._client is not self:
                raise ValueError("all batch worlds must belong to this client")
        return self._request({"op": "batch", "commands": [
            {"handle": world._handle, "command": command} for world, command in jobs]},
            budget=budget, cancel=cancel)

    def stats(self):
        return self._request({"op": "stats"})

    def close(self):
        if self.owner_pid != os.getpid():
            return
        process, self._process = self._process, None
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def public_build_rules(entry, *, turn_order_known=False, drink_supply=None):
    """Versioned default draw rules and information timing, not future inventory.

    Supply probabilities must be supplied by the caller's actual environment;
    Arena does not infer them from one sampled inventory.
    """
    context = entry["context"]
    return {"schema_version": "arena-public-build-rules/1", "version": search_content_version(),
            "draw_rules": {"hand_limit": 5, "base_draws_per_turn": 3,
                           "opening_forced_cards": "native initial-hand partition then up to two additional forced draws",
                           "recycle": "uniform Fisher-Yates shuffle of discards when a draw needs an empty deck",
                           "end_turn": "native discard/hold lifecycle and effects",
                           "effect_overrides": "entry card, item, stage, memory and persistent programs"},
            "turn_counts": copy.deepcopy(context.get("stage", {}).get("turnCounts")),
            "turn_order": copy.deepcopy(context.get("turn_types")) if turn_order_known else None,
            "turn_order_reveal": "before_build_explicit_experiment" if turn_order_known else "exam_opening",
            "drink_supply": copy.deepcopy(drink_supply), "actual_drink_inventory_included": False}
