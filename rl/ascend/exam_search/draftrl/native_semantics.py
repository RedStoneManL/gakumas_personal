"""Batched, versioned read-only compilation against the pinned native rules.

Prepare a batch before sampling, then use ``card``/``program`` on the hot path.
Those accessors never launch Node. Effective programs do not bake in growth:
golden applies growth during execution, so growth is retained as an overlay.
No accelerator libraries, training workers or private snapshots are imported.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
from functools import lru_cache

SCHEMA_VERSION = "arena-native-semantics/1"
ROOT = Path(__file__).resolve().parents[1]
ARENA = ROOT / "runtime/arena/gakumas_arena"
VENDOR = ARENA / "_vendor/gakumas_tools"
WORKER = Path(__file__).with_suffix(".mjs")


class NativeSemanticsError(ValueError):
    pass


class SemanticCacheMiss(NativeSemanticsError):
    """Prepare public definitions before entering the per-entity hot path."""


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@lru_cache(maxsize=4)
def _hash_files(stamp):
    digest = hashlib.sha256()
    for name, _, _ in stamp:
        path = Path(name)
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def source_version():
    """Includes native code/data, the effective catalogue and this bridge."""
    paths = sorted(set(
        list((VENDOR / "packages").rglob("*.js"))
        + list((VENDOR / "packages").rglob("*.json"))
        + [VENDOR / "scripts/extensionless-loader.mjs", WORKER, Path(__file__),
           ARENA / "engine/training_catalogue.mjs",
           ARENA / "content/native_catalogue_overrides.json"]
    ), key=lambda path: path.relative_to(ROOT).as_posix())
    stamp = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
    return _hash_files(stamp)


@lru_cache(maxsize=4)
def _growth_fields(version):
    # Read the native declaration rather than maintaining a second growth list.
    text = (VENDOR / "packages/gakumas-engine/constants.js").read_text(encoding="utf-8")
    match = re.search(r"export const GROWTH_FIELDS = (\[[\s\S]*?\]);", text)
    if not match:
        raise NativeSemanticsError("Native growth declaration cannot be read")
    # Native JS permits a trailing comma; the declaration is a string array.
    return frozenset(json.loads(re.sub(r",\s*]", "]", match.group(1))))


def _card_request(card, version):
    if card.get("temporary_support"):
        raise NativeSemanticsError("Use public effective programs for temporary support; base compilation would erase its overlay")
    definition_id = card.get("definition_id")
    if type(definition_id) is not int:
        raise NativeSemanticsError("definition_id must be a native integer ID")
    customizations = card.get("customizations", {})
    growth = card.get("growth", {})
    if not isinstance(customizations, dict) or not isinstance(growth, dict):
        raise NativeSemanticsError("customizations and growth must be mappings")
    customs = {}
    for key, level in customizations.items():
        if not str(key).isdigit() or type(level) is not int or level < 1:
            raise NativeSemanticsError("Invalid customization identity/level")
        native_key = str(int(key))
        if native_key in customs:
            raise NativeSemanticsError("Duplicate normalized customization ID")
        customs[native_key] = level
    for name, value in growth.items():
        if (name not in _growth_fields(version) or type(value) not in (int, float)
                or not math.isfinite(value) or abs(value) > 10000):
            raise NativeSemanticsError(f"Invalid native growth field {name}")
    return {"definition_id": definition_id, "customizations": customs, "growth": copy.deepcopy(growth)}


def _card_key(card):
    # getLines/customization metadata are independent of run-time growth.
    return _canonical({"definition_id": card["definition_id"], "customizations": card["customizations"]})


class NativeSemantics:
    def __init__(self, node=None, cache_path=None, timeout=60):
        self.node = node
        self.timeout = timeout
        self.version = source_version()
        self._cards = {}
        self._programs = {}
        self._lock = threading.RLock()
        self.native_calls = 0
        if cache_path is not None:
            self.load(cache_path)

    def prepare(self, cards=(), programs=()):
        """Compile all missing definitions/programs in one native batch.

        Returns aligned results. Repeated variants and DSL strings are deduped;
        changing only growth needs no native call. All failures are explicit.
        """
        cards = [_card_request(card, self.version) for card in cards]
        programs = list(programs)
        if any(not isinstance(text, str) or len(text) > 100000 for text in programs):
            raise NativeSemanticsError("Expected native DSL of at most 100000 characters")
        with self._lock:
            missing_cards = {_card_key(c): {**c, "growth": {}} for c in cards if _card_key(c) not in self._cards}
            missing_programs = list(dict.fromkeys(p for p in programs if p not in self._programs))
            calls = 0
            if missing_cards or missing_programs:
                if source_version() != self.version:
                    raise NativeSemanticsError("Native source changed; create a new compiler/cache version")
                executable = self.node or shutil.which("node")
                if not executable:
                    raise NativeSemanticsError("Node.js is required only to prepare missing semantic batches")
                payload = {"schema_version": SCHEMA_VERSION, "cards": list(missing_cards.values()), "programs": missing_programs}
                try:
                    process = subprocess.run(
                        [str(executable), "--no-warnings", "--loader", (VENDOR / "scripts/extensionless-loader.mjs").as_uri(), str(WORKER)],
                        input=_canonical(payload), capture_output=True, text=True, encoding="utf-8",
                        timeout=self.timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    result = json.loads(process.stdout)
                except (OSError, subprocess.TimeoutExpired, ValueError) as error:
                    raise NativeSemanticsError(f"Native semantic compilation failed: {error}") from error
                self.native_calls += 1
                calls = 1
                if process.returncode or result.get("ok") is not True:
                    raise NativeSemanticsError(result.get("error", "Native semantic worker failed"))
                if (result.get("schema_version") != SCHEMA_VERSION or result.get("rng_calls_delta") != 0
                        or len(result.get("cards", [])) != len(missing_cards)
                        or len(result.get("programs", [])) != len(missing_programs)):
                    raise NativeSemanticsError("Invalid native semantic response or unexpected RNG use")
                self._cards.update(zip(missing_cards, result["cards"]))
                self._programs.update(zip(missing_programs, result["programs"]))
            return {"cards": [self.card(c) for c in cards], "programs": [self.program(p) for p in programs],
                    "native_calls": calls, "rng_calls_delta": 0}

    def card(self, card):
        """Cache-only: no Node, no engine, no random numbers."""
        request = _card_request(card, self.version)
        key = _card_key(request)
        with self._lock:
            if key not in self._cards:
                raise SemanticCacheMiss(f"Card variant not prepared: {key}")
            result = copy.deepcopy(self._cards[key])
        result["growth"] = request["growth"]
        return result

    def program(self, text):
        """Return the exact cached native AST; unresolved symbols remain AST."""
        with self._lock:
            if text not in self._programs:
                raise SemanticCacheMiss("Native DSL was not prepared")
            return copy.deepcopy(self._programs[text])

    get_cached_card = card
    get_cached_program = program

    def dump(self, path):
        """Write a portable, source-bound offline catalogue atomically."""
        path = Path(path)
        with self._lock:
            payload = {"schema_version": SCHEMA_VERSION, "source_sha256": self.version,
                       "cards": self._cards, "programs": self._programs}
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            temporary.write_text(_canonical(payload), encoding="utf-8")
            temporary.replace(path)

    def load(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION or data.get("source_sha256") != self.version:
            raise NativeSemanticsError("Offline semantic catalogue version mismatch")
        if not isinstance(data.get("cards"), dict) or not isinstance(data.get("programs"), dict):
            raise NativeSemanticsError("Malformed semantic catalogue")
        with self._lock:
            self._cards.update(data["cards"])
            self._programs.update(data["programs"])


# Dependencies hidden in native intermediate resolvers, not visible in an AST
# rhs such as `score += 10`. Descriptors are static potential dependencies, not
# a second evaluator, trigger prediction, reward or hand-authored play policy.
# The exact assignment operator matters: score*=2 does not call resolveScore.
_SCORE_READS = (
    "concentration", "concentrationMultiplier", "concentrationEffectBuffs",
    "enthusiasm", "enthusiasmMultiplier", "goodConditionTurns", "perfectConditionTurns",
    "goodConditionTurnsMultiplier", "stance", "strengthEffectBuffs", "fullPowerEffectBuffs",
    "scoreBuffs", "scoreDebuffs", "prideTurns", "goodImpressionTurns", "motivation",
    "poorConditionTurns", "context.multipliers", "context.turn_types", "turnsElapsed",
    "card.growth", "scoreTimes",
)
_COST_READS = ("card.growth", "stance", "halfCostTurns", "doubleCostTurns", "costReduction", "costIncrease")
OPERATOR_SEMANTICS = {
    "score+=": {"resolver": "resolveScore", "reads": _SCORE_READS, "writes": ("score",)},
    "genki+=": {"resolver": "resolveGenki", "reads": ("nullifyGenkiTurns", "motivation", "motivationMultiplier", "uneaseTurns", "card.growth"), "writes": ("genki",)},
    "goodImpressionTurns+=": {"resolver": "resolveGoodImpressionTurns", "reads": ("goodImpressionTurnsBuffs", "card.growth"), "writes": ("goodImpressionTurns",)},
    "motivation+=": {"resolver": "resolveMotivation", "reads": ("motivationAdditionBuffs", "motivationBuffs", "card.growth"), "writes": ("motivation",)},
    "goodConditionTurns+=": {"resolver": "resolveGoodConditionTurns", "reads": ("goodConditionTurnsBuffs", "card.growth"), "writes": ("goodConditionTurns",)},
    "concentration+=": {"resolver": "resolveConcentration", "reads": ("concentrationAdditionBuffs", "concentrationBuffs", "card.growth"), "writes": ("concentration",)},
    "enthusiasm+=": {"resolver": "resolveEnthusiasm", "reads": ("enthusiasmBonusBuffs", "enthusiasmBuffs"), "writes": ("enthusiasm",)},
    "fullPowerCharge+=": {"resolver": "resolveFullPowerCharge", "reads": ("fullPowerChargeBuffs", "card.growth"), "writes": ("fullPowerCharge", "cumulativeFullPowerCharge")},
    "stamina-=": {"resolver": "resolveStamina", "reads": _COST_READS, "writes": ("stamina", "consumedStamina")},
}


def operator_semantics(lhs, op):
    """Potential implicit reads/writes; unknown never means no dependencies."""
    if lhs in {"cost", "fixedGenki", "fixedStamina"} and op in {"=", "+=", "-=", "*=", "/=", "%="}:
        descriptor = {
            "cost": {"resolver": "resolveCost", "reads": _COST_READS + ("genki", "stamina"), "writes": ("genki", "stamina", "consumedStamina")},
            "fixedGenki": {"resolver": "resolveFixedGenki", "reads": (), "writes": ("genki",)},
            "fixedStamina": {"resolver": "resolveFixedStamina", "reads": (), "writes": ("stamina", "consumedStamina")},
        }[lhs]
    else:
        descriptor = OPERATOR_SEMANTICS.get(f"{lhs}{op}")
    if descriptor is None:
        return {"resolved": False, "scope": "implicit_native_dependencies", "operator": f"{lhs}{op}", "unresolved": True}
    return {"resolved": True, "scope": "implicit_native_dependencies", "operator": f"{lhs}{op}",
            "potential_only": True, "includes_explicit_rhs": False, "includes_event_dispatch": False,
            **copy.deepcopy(descriptor)}
