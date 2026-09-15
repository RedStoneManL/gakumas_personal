"""Arena's current golden exam backend: the pinned, unmodified gakumas-tools engine.

Each request executes in an isolated Node process and replays a seeded journal.
This preserves upstream RNG behavior and makes snapshots portable across processes,
including actions paused at multiple nested selections. This is an offline interface;
it does not submit game commands or replace the existing live recovery protocol.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

RULES_VERSION = "arena-gakumas-tools/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/1"
DEFAULT_EXAM_BACKEND = "gakumas-tools"
DEFAULT_SEED = 610397104
_PACKAGE = Path(__file__).resolve().parents[1]
_VENDOR = _PACKAGE / "_vendor/gakumas_tools"


class GoldenEngineError(ValueError):
    """Invalid request or upstream execution error; the prior snapshot is retained."""


def _request(payload: dict, node: str | None = None) -> dict:
    executable = node or shutil.which("node")
    if not executable:
        raise RuntimeError("Arena's golden backend requires Node.js 20+ on PATH or node=...")
    command = [
        executable,
        "--no-warnings",
        "--loader",
        (_VENDOR / "scripts/extensionless-loader.mjs").as_uri(),
        str(Path(__file__).with_name("worker.mjs")),
    ]
    process = subprocess.run(
        command,
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        result = json.loads(process.stdout)
    except ValueError as error:
        raise GoldenEngineError(process.stderr.strip() or "Invalid Node response") from error
    if not result.get("ok"):
        raise GoldenEngineError(result.get("error", "Golden engine failed"))
    return result["result"]


class ArenaExam:
    """Step a golden exam using community IDs and explicit loadout/stage configuration.

    act({"type":"play", "card": observation["actions"][0]["card"]})
    choose([0])  # indices in the exposed selection candidates, not card IDs
    snapshot() / ArenaExam.restore(snapshot) include seed, config and the choice tape.
    """

    def __init__(self, config: dict, *, seed: int = DEFAULT_SEED, node: str | None = None):
        self.node = node
        self._adopt(
            _request(
                {
                    "op": "replay",
                    "snapshot": {
                        "schema_version": "arena-golden-snapshot/1",
                        "rules_version": RULES_VERSION,
                        "config": copy.deepcopy(config),
                        "seed": int(seed),
                        "history": [],
                        "pending": {"action": {"type": "start"}, "choices": []},
                    },
                },
                node,
            )
        )

    def _adopt(self, result: dict) -> dict:
        self._snapshot = result["snapshot"]
        self._observation = result["observation"]
        return self.observe()

    def observe(self) -> dict:
        return copy.deepcopy(self._observation)

    def snapshot(self) -> dict:
        return copy.deepcopy(self._snapshot)

    @classmethod
    def restore(cls, snapshot: dict, *, node: str | None = None) -> ArenaExam:
        result = _request({"op": "replay", "snapshot": snapshot}, node)
        instance = cls.__new__(cls)
        instance.node = node
        instance._adopt(result)
        return instance

    def act(self, action: dict[str, Any]) -> dict:
        if self._snapshot["pending"]:
            raise GoldenEngineError("Resolve the pending selection first")
        candidate = self.snapshot()
        if action.get("type") not in {"play", "drink", "end_turn"}:
            raise GoldenEngineError("Unknown action type")
        candidate["pending"] = {"action": copy.deepcopy(action), "choices": []}
        return self._adopt(_request({"op": "replay", "snapshot": candidate}, self.node))

    def choose(self, indices: list[int]) -> dict:
        if not self._snapshot["pending"]:
            raise GoldenEngineError("No pending selection")
        candidate = self.snapshot()
        candidate["pending"]["choices"].append(copy.deepcopy(indices))
        return self._adopt(_request({"op": "replay", "snapshot": candidate}, self.node))


def run_exam(config: dict, *, seed: int = DEFAULT_SEED, node: str | None = None) -> dict:
    """Run the unmodified upstream heuristic/StagePlayer; output includes full logs."""
    return _request({"op": "rollout", "config": config, "seed": int(seed)}, node)


def find_effects(query: str, *, node: str | None = None) -> dict:
    """Query the golden catalog by name; definitions contain parsed effect ASTs."""
    return _request({"op": "lookup", "query": query}, node)


def loadout_from_query(query: str) -> dict:
    """Decode an upstream simulator URL query without conflating native master IDs."""
    from urllib.parse import parse_qs

    values = parse_qs(query.lstrip("?"))
    get = lambda key, default="": values.get(key, [default])[0]
    ids = lambda text: [int(n or 0) for n in text.split("-")]
    cards = [ids(g) for g in get("cards").split("_")]
    customs = []
    for group in get("customizations").split("_"):
        parsed = []
        for slot in group.split("-"):
            parsed.append(
                {k: int(v) for part in slot.split("e") if part for k, v in [part.split("x")]}
            )
        customs.append(parsed)
    if len(cards) != len(customs):
        customs = [[{} for _ in group] for group in cards]
    return {
        "stage_id": int(get("stage")),
        "loadout": {
            "params": ids(get("params")),
            "supportBonus": float(get("support_bonus", "0")),
            "pItemIds": ids(get("items")),
            "skillCardIdGroups": cards,
            "customizationGroups": customs,
        },
    }


__all__ = [
    "DEFAULT_EXAM_BACKEND",
    "RULES_VERSION",
    "ArenaExam",
    "GoldenEngineError",
    "find_effects",
    "loadout_from_query",
    "run_exam",
]
