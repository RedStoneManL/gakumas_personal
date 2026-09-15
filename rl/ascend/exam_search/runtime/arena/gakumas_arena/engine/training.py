"""Public, externally controlled training sessions over the pinned golden engine.

Configurable examinations compose native golden definitions and stage effects.
It intentionally does not import legacy Gym observations or rewards.
"""

from __future__ import annotations

import atexit
import copy
import hashlib
import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from . import RULES_VERSION

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "_vendor/gakumas_tools"
PRESET = "hif-round2-shro-golden/1"
SCHEMA = "arena-public-exam/1"
_LOADED_PYTHON_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _effective_paths():
    return (
        sorted((VENDOR / "packages").rglob("*.js"))
        + sorted((VENDOR / "packages").rglob("*.json"))
        + [
            VENDOR / "scripts/extensionless-loader.mjs",
            Path(__file__),
            Path(__file__).with_name("training_worker.mjs"),
            Path(__file__).with_name("training_config.mjs"),
            Path(__file__).with_name("training_basic_pool.mjs"),
            Path(__file__).with_name("training_support.mjs"),
            Path(__file__).with_name("training_catalogue.mjs"),
            Path(__file__).with_name("catalogue_overrides.py"),
            ROOT / "content/native_catalogue_overrides.json",
            Path(__file__).with_name("__init__.py"),
            ROOT / "__init__.py",
        ]
    )


def _source_stamp():
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in _effective_paths())


class TrainingError(ValueError):
    """Rejected input/native failure; never a zero-score terminal training sample."""

    def __init__(self, kind: str, path: str, message: str):
        self.kind, self.path = kind, path
        super().__init__(f"{kind}: {path}: {message}")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_version() -> dict:
    """Hash actual effective files, including uncommitted adapter changes."""
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != _LOADED_PYTHON_SHA:
        raise TrainingError(
            "version_mismatch", "training.py", "restart Python after source updates"
        )
    paths = _effective_paths()
    files = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }
    return {
        "golden_rules": RULES_VERSION,
        "public_schema": SCHEMA,
        "effective_sha256": hashlib.sha256(_canonical(files).encode()).hexdigest(),
        "files_sha256": files,
    }


class _Transport:
    """One serialized native worker per Python process; native RNG reset per replay."""

    def __init__(self):
        self.owner_pid = os.getpid()
        self.process = None
        self.lock = threading.Lock()
        self.output = queue.Queue()
        self.executable = None
        self.version = None

    def _start(self, node=None):
        executable = node or shutil.which("node")
        if not executable:
            raise TrainingError("dependency", "node", "Node.js 20+ required")
        self.executable = executable
        self.output = queue.Queue()
        self.process = subprocess.Popen(
            [
                executable,
                "--no-warnings",
                "--loader",
                (VENDOR / "scripts/extensionless-loader.mjs").as_uri(),
                str(Path(__file__).with_name("training_worker.mjs")),
                "--server",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        process, out = self.process, self.output

        def reader():
            for line in process.stdout:
                out.put(line)
            out.put(None)

        threading.Thread(target=reader, daemon=True).start()

    def request(self, payload, node=None, timeout=60, version=None):
        if self.owner_pid != os.getpid():
            self.__init__()  # Never reuse or kill a worker inherited through fork.
        with self.lock:
            if self.version != version:
                self.close()
            if self.process is None or self.process.poll() is not None:
                self._start(node)
                self.version = version
            elif node and node != self.executable:
                raise TrainingError(
                    "dependency", "node", "close_training_worker() before switching Node"
                )
            try:
                self.process.stdin.write(_canonical(payload) + "\n")
                self.process.stdin.flush()
                line = self.output.get(timeout=timeout)
                if line is None:
                    raise RuntimeError("native worker exited")
                response = json.loads(line)
            except (OSError, RuntimeError, ValueError, queue.Empty) as error:
                self.close()
                raise TrainingError(
                    "transport", "worker", str(error) or "request timed out"
                ) from error
            if not response["ok"]:
                error = response["error"]
                raise TrainingError(error["kind"], error["path"], error["message"])
            return response["result"]

    def close(self):
        if self.owner_pid != os.getpid():
            return
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()


_transport = _Transport()
atexit.register(_transport.close)


def close_training_worker():
    _transport.close()


def training_catalog(*, scope: str = "all") -> dict:
    """All native structured definitions, or scope='legacy' for the old fixture."""
    if scope not in ("all", "legacy"):
        raise ValueError("scope must be 'all' or 'legacy'")
    return _transport.request(
        {"op": "catalog", "scope": scope}, version=content_version()["effective_sha256"]
    )


def effect_declaration(ability_id: str, effects: str, *, counters: dict | None = None) -> dict:
    """Declare native phase effects, optionally with carried counter values."""
    return {"id": ability_id, "effects": effects, "counters": copy.deepcopy(counters or {})}


def make_training_entry(
    cards: list[int | dict],
    *,
    plan: str | None = None,
    idol_id: int | None = None,
    score_percents: tuple | list | None = None,
    scoring: dict | None = None,
    hif_scoring: dict | None = None,
    max_stamina: int = 40,
    stamina: int | None = None,
    drinks=(),
    p_items=(),
    turn_types: list[str] | None = None,
    stage: dict | None = None,
    stage_effects: str | None = None,
    basic_card_pool=(),
    basic_card_weights=None,
    skill_card_support=None,
    memory_abilities=(),
    persistent_effects=(),
    preset: str = "custom-exam",
    family: str = "custom-environment/1",
) -> dict:
    """Build a configurable before-opening entry using native golden components.

    No fixed idol, deck count, scoring values or turn sequence is imposed.
    'scoring' selects native inputs; 'hif_scoring' resolves raw HIF inputs using
    the user-approved empirical model. Both exclude score_percents. Card dictionaries
    preserve instance IDs, customizations, growth and effect bindings.
    Optional basic_card_weights align with a unique basic_card_pool; omitted
    weights preserve the pinned engine's legacy uniform-over-unique-IDs policy.
    """
    if sum(x is not None for x in (scoring, score_percents, hif_scoring)) > 1:
        raise ValueError("choose scoring, score_percents or hif_scoring, not more than one")
    scoring_provenance = None
    if hif_scoring is not None:
        from ..scoring import calculate_hif_multiplier
        scoring_provenance = calculate_hif_multiplier(**copy.deepcopy(hif_scoring))
        score_percents = scoring_provenance['score_percents']
    if plan is None:
        if idol_id is None:
            plan = "sense"
        else:
            idol = next((i for i in training_catalog()["idols"] if i["id"] == idol_id), None)
            if idol is None:
                raise TrainingError("invalid_configuration", "idol_id", "unknown golden idol")
            plan = idol["plan"]
    built_stage = {
        "type": "contest",
        "season": 51,
        "turnCounts": {"vocal": 5, "dance": 4, "visual": 3},
        "firstTurns": {"vocal": 1, "dance": 0, "visual": 0},
        "criteria": {"vocal": 0.45, "dance": 0.30, "visual": 0.25},
        "effects": "",
        "linkTurnCounts": [],
    }
    if stage is not None:
        built_stage.update(copy.deepcopy(stage))
    if turn_types is not None and (stage is None or "turnCounts" not in stage):
        built_stage["turnCounts"] = {k: turn_types.count(k) for k in ("vocal", "dance", "visual")}
    if stage_effects is not None:
        built_stage["effects"] = stage_effects
    instances = []
    for i, card in enumerate(cards):
        if type(card) is int:
            instances.append(
                {
                    "instance_id": f"entry:{i:03}",
                    "definition_id": card,
                    "customizations": {},
                    "growth": {},
                    "bindings": [],
                }
            )
        elif isinstance(card, dict):
            instances.append(copy.deepcopy(card))
        else:
            raise TrainingError(
                "invalid_configuration",
                f"cards[{i}]",
                "expected definition ID or full card instance",
            )
    return {
        "schema_version": "arena-exam-entry/2",
        "preset": preset,
        "source": {"kind": "custom_environment", "family": family,
                   **({"hif_scoring": scoring_provenance} if scoring_provenance else {})},
        "cards": instances,
        "resources": {
            "stamina": max_stamina if stamina is None else stamina,
            "max_stamina": max_stamina,
            "drinks": list(drinks),
        },
        "p_items": list(p_items),
        "memory_abilities": copy.deepcopy(list(memory_abilities)),
        "persistent_effects": copy.deepcopy(list(persistent_effects)),
        "context": {
            "idol_id": idol_id,
            "plan": plan,
            "boundary": "before_opening",
            "scoring": copy.deepcopy(scoring)
            if scoring is not None
            else {
                "mode": "percent",
                "values": list((100, 100, 100) if score_percents is None else score_percents),
                "support_bonus": 0,
            },
            "stage": built_stage,
            "turn_types": copy.deepcopy(turn_types),
            "basic_card_pool": list(basic_card_pool),
            **({"basic_card_weights": copy.deepcopy(list(basic_card_weights))}
               if basic_card_weights is not None else {}),
            **({"skill_card_support": copy.deepcopy(skill_card_support)}
               if skill_card_support is not None else {}),
        },
    }


def hif_round2_entry(cards: list[int | dict] | None = None, **overrides) -> dict:
    """Editable 12-turn HIF Round2 template; every field can be overridden.

    The default kit is Garakuta Road Hiro. For another kit override cards,
    plan/idol_id, p_items and basic_card_pool together as appropriate.
    score_percents are final native input percentages (2030 means 20.30x).
    """
    old = default_training_entry()
    options = {
        "plan": "sense",
        "idol_id": 140,
        "score_percents": [2030, 1472, 1098],
        "max_stamina": 35,
        "stamina": 25,
        "drinks": [18, 22, 14, 12],
        "p_items": [428, 442],
        "basic_card_pool": [646, 648, 666, 668, 670],
        "preset": "hif-round2",
        "family": "hif-round2-custom/2",
    }
    if "scoring" in overrides or "hif_scoring" in overrides:
        options.pop("score_percents")
    if "max_stamina" in overrides and "stamina" not in overrides:
        options["stamina"] = overrides["max_stamina"]
    if "idol_id" in overrides and "plan" not in overrides:
        options["plan"] = None
    options.update(overrides)
    return make_training_entry(old["cards"] if cards is None else cards, **options)


def default_training_entry(*, card_count: int = 22) -> dict:
    """Legacy v1 regression fixture. Use hif_round2_entry for custom training."""
    if not 19 <= card_count <= 24:
        raise ValueError("example family supports card_count 19..24")
    ids = [
        816,
        818,
        762,
        752,
        752,
        709,
        593,
        169,
        117,
        597,
        293,
        87,
        648,
        159,
        599,
        145,
        707,
        108,
        584,
        247,
        668,
        670,
        646,
        648,
    ][:card_count]
    return {
        "schema_version": "arena-round2-entry/1",
        "preset": PRESET,
        "source": {"kind": "constrained_curriculum", "family": "shro-fixed-exam/1"},
        "cards": [
            {
                "instance_id": f"entry:{i:03}",
                "definition_id": card,
                "customizations": {},
                "growth": {},
                "bindings": [],
            }
            for i, card in enumerate(ids)
        ],
        "resources": {"stamina": 25, "max_stamina": 35, "drinks": [18, 22, 14, 12]},
        "p_items": [428, 442],
        "memory_abilities": [],
        "persistent_effects": [],
        "context": {
            "idol_id": 140,
            "params": [1871, 1392, 1088],
            "star_quality": 800,
            "dearness_bonus": 0.5,
            "boundary": "before_opening",
        },
    }


class TrainingExam:
    """No hidden state in observe/act/choose results; snapshots are private.

    Decision versions are mandatory. Errors leave this instance unchanged.
    Different instances may share the serialized static worker but never state.
    """

    def __init__(
        self,
        entry: dict,
        *,
        seed: int = 0,
        node: str | None = None,
        logs: bool = False,
        max_native_actions: int = 200000,
    ):
        self.node = node
        self.options = {"logs": logs, "max_native_actions": max_native_actions}
        self.version = content_version()
        self._source_stamp = _source_stamp()
        snapshot = {
            "schema_version": "arena-training-snapshot/1",
            "version": self.version,
            "entry": copy.deepcopy(entry),
            "seed": seed,
            "revision": 0,
            "history": [],
            "pending": {"action": {"type": "start"}, "choices": []},
            "status": "running",
        }
        self._adopt(self._request(snapshot))

    def _request(self, snapshot):
        if self._source_stamp != _source_stamp():
            raise TrainingError(
                "version_mismatch",
                "source",
                "source files changed during this session; restart and recreate",
            )
        if snapshot.get("version", {}).get("effective_sha256") != self.version["effective_sha256"]:
            raise TrainingError(
                "version_mismatch", "snapshot.version", "effective source content changed"
            )
        return _transport.request(
            {"op": "replay", "snapshot": snapshot, "options": self.options},
            node=self.node,
            version=self.version["effective_sha256"],
        )

    def _adopt(self, result):
        self._snapshot = result["snapshot"]
        self._observation = result["observation"]
        self._observation["version"] = {
            k: v for k, v in self.version.items() if k != "files_sha256"
        }
        self.last_cost = result["cost"]
        return self.observe()

    def observe(self) -> dict:
        return copy.deepcopy(self._observation)

    def snapshot(self) -> dict:
        return copy.deepcopy(self._snapshot)

    def export_entry(self) -> dict:
        return copy.deepcopy(self._snapshot["entry"])

    def inspect_private(self) -> dict:
        """Explicit private replay diagnostics, including true order; never model input."""
        if self._source_stamp != _source_stamp():
            raise TrainingError("version_mismatch", "source", "source files changed")
        result = _transport.request(
            {
                "op": "replay",
                "snapshot": self.snapshot(),
                "options": {**self.options, "logs": True, "debug": True},
            },
            node=self.node,
            version=self.version["effective_sha256"],
        )
        return {"debug": result["private_debug"], "cost": result["cost"]}

    def initial_snapshot(self) -> dict:
        saved = self.snapshot()
        saved.update(
            history=[],
            pending={"action": {"type": "start"}, "choices": []},
            revision=0,
            status="running",
        )
        return saved

    @classmethod
    def restore(cls, snapshot: dict, *, node=None, logs=False, max_native_actions=200000):
        instance = cls.__new__(cls)
        instance.node = node
        instance.options = {"logs": logs, "max_native_actions": max_native_actions}
        instance.version = content_version()
        instance._source_stamp = _source_stamp()
        instance._adopt(instance._request(copy.deepcopy(snapshot)))
        return instance

    def _check_revision(self, revision):
        if type(revision) is not int or revision != self._snapshot["revision"]:
            raise TrainingError(
                "stale_decision", "decision_version", "missing or expired decision version"
            )
        result = self._observation["result"]
        if result["terminated"] or result["truncated"]:
            raise TrainingError("episode_closed", "action", "episode is closed")

    def act(self, action: dict) -> dict:
        if not isinstance(action, dict):
            raise TrainingError("invalid_input", "action", "expected current action object")
        self._check_revision(action.get("decision_version"))
        if self._observation["choice"] is not None:
            raise TrainingError("pending_choice", "action", "resolve the current choice first")
        if action not in self._observation["actions"]:
            raise TrainingError(
                "illegal_action", "action", "submit a current legal candidate exactly"
            )
        saved = self.snapshot()
        saved["revision"] += 1
        saved["pending"] = {
            "action": {k: v for k, v in action.items() if k != "decision_version"},
            "choices": [],
        }
        return self._adopt(self._request(saved))

    def choose(self, indices: list[int], *, decision_version: int) -> dict:
        self._check_revision(decision_version)
        if self._observation["choice"] is None:
            raise TrainingError("no_choice", "choice", "no selection is pending")
        saved = self.snapshot()
        saved["revision"] += 1
        saved["pending"]["choices"].append(copy.deepcopy(indices))
        return self._adopt(self._request(saved))

    def truncate(self, *, decision_version: int) -> dict:
        self._check_revision(decision_version)
        saved = self.snapshot()
        saved["revision"] += 1
        saved["status"] = "truncated"
        return self._adopt(self._request(saved))

    def fork(self):
        """Same private world; NOT a fair-search conditional world sampler."""
        return self.restore(self.snapshot(), node=self.node, **self.options)


def create_training_exam(entry: dict | None = None, *, seed: int = 0, **kwargs) -> TrainingExam:
    return TrainingExam(hif_round2_entry() if entry is None else entry, seed=seed, **kwargs)


__all__ = [
    "TrainingError",
    "TrainingExam",
    "close_training_worker",
    "content_version",
    "create_training_exam",
    "default_training_entry",
    "effect_declaration",
    "hif_round2_entry",
    "make_training_entry",
    "training_catalog",
]
