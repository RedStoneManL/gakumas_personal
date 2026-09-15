"""ID-independent, bounded passive/effect tensors shared by simulation and live views."""

from __future__ import annotations

import hashlib
import json

import numpy as np

from .ids import ExamEffect, ExamPhase, FieldStatus

PASSIVE_CAPACITY = 32
EFFECT_CAPACITY = 128
PHASES = tuple(sorted({v for k, v in vars(ExamPhase).items() if k.isupper()}))
FIELDS = tuple(sorted({v for k, v in vars(FieldStatus).items() if k.isupper()}))
EFFECTS = tuple(
    sorted({v for k, v in vars(ExamEffect).items() if k.isupper() and not k.endswith("PREFIX")})
)
PASSIVE_NUMBERS = (
    "present",
    "remaining_turns",
    "unlimited_turns",
    "remaining_count",
    "unlimited_count",
    "applied_turn",
    "last_fired_turn",
    "never_fired",
    "bound_to_card",
    "once_per_turn",
)
EFFECT_NUMBERS = (
    "present",
    "parent_slot",
    "effect_order",
    "value1",
    "value2",
    "turns",
    "count",
    "pick_min",
    "pick_max",
    "select",
    "random",
    "all",
)


def structural_manifest():
    return {
        "version": "arena-passive-features/1",
        "passive_capacity": PASSIVE_CAPACITY,
        "effect_capacity": EFFECT_CAPACITY,
        "passive_numbers": list(PASSIVE_NUMBERS),
        "effect_numbers": list(EFFECT_NUMBERS),
        "phase_types": list(PHASES),
        "field_types": list(FIELDS),
        "effect_types": list(EFFECTS),
        "definition_fingerprint": "sha256-semantic-structure/8-u32",
        "normalization": "signed x/(abs(x)+10); slots are one-based/capacity",
    }


def passive_shapes():
    return {
        "passive_features": (
            PASSIVE_CAPACITY,
            len(PASSIVE_NUMBERS) + len(PHASES) + len(FIELDS) + 8,
        ),
        "passive_effect_features": (EFFECT_CAPACITY, len(EFFECT_NUMBERS) + len(EFFECTS) + 8),
    }


def _semantic_row(row):
    return {
        k: v
        for k, v in row.items()
        if k
        not in {
            "id",
            "produceDescriptions",
            "customizeProduceDescriptions",
            "playEffectProduceDescriptions",
            "name",
        }
    }


def _fingerprint(row):
    raw = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).digest()
    return [int.from_bytes(raw[i : i + 4], "big") / 4294967295 for i in range(0, 32, 4)]


def _bound(value):
    value = float(value or 0)
    return value / (abs(value) + 10)


def encode_passive_structure(runtime, *, known: bool):
    shapes = passive_shapes()
    result = {k: np.zeros(shape, dtype=np.float32) for k, shape in shapes.items()}
    result.update(
        {k + "_known_mask": np.zeros(shape, dtype=np.float32) for k, shape in shapes.items()}
    )
    if not known:
        return result
    for name in shapes:
        result[name + "_known_mask"][:] = 1
    if len(runtime.active_enchants) > PASSIVE_CAPACITY:
        raise ValueError("unsupported passive feature capacity")
    repository = runtime.repository
    entries = []
    for enchant in runtime.active_enchants:
        trigger = repository.exam_trigger_map[enchant.trigger_id]
        effect_rows = [repository.exam_effect_map[e] for e in enchant.effect_ids]
        normalized = _semantic_row(trigger)
        sid = normalized.pop("produceCardSearchId", "")
        if sid:
            normalized["search"] = _semantic_row(
                repository.load_table("ProduceCardSearch").first(sid) or {}
            )
        signature = json.dumps(
            {"trigger": normalized, "effects": [_semantic_row(e) for e in effect_rows]},
            sort_keys=True,
        )
        # Identity only breaks ties among semantically identical states; no vocabulary slot per ID.
        entries.append((signature, enchant.uid, enchant, trigger, effect_rows, normalized))
    effect_index = 0
    for slot, (_, _, enchant, trigger, effects, normalized) in enumerate(
        sorted(entries, key=lambda e: (e[0], e[1]))
    ):
        row = result["passive_features"][slot]
        row[: len(PASSIVE_NUMBERS)] = [
            1,
            _bound(enchant.remaining_turns),
            enchant.remaining_turns is None,
            _bound(enchant.remaining_count),
            enchant.remaining_count is None,
            _bound(enchant.applied_turn),
            _bound(max(enchant.last_fired_turn, 0)),
            enchant.last_fired_turn < 0,
            enchant.bound_card_uid is not None,
            enchant.once_per_turn,
        ]
        for phase in trigger.get("phaseTypes", []):
            if phase not in PHASES:
                raise ValueError("unsupported passive phase encoding: " + phase)
            row[len(PASSIVE_NUMBERS) + PHASES.index(phase)] = 1
        for field, value in zip(
            trigger.get("fieldStatusTypes", []), trigger.get("fieldStatusValues", [])
        ):
            if field not in FIELDS:
                raise ValueError("unsupported passive field encoding: " + field)
            row[len(PASSIVE_NUMBERS) + len(PHASES) + FIELDS.index(field)] = _bound(value)
        row[-8:] = _fingerprint(normalized)
        for order, effect in enumerate(effects):
            if effect_index >= EFFECT_CAPACITY:
                raise ValueError("unsupported passive effect feature capacity")
            out = result["passive_effect_features"][effect_index]
            effect_index += 1
            kind = effect.get("effectType", "")
            if kind not in EFFECTS:
                raise ValueError("unsupported effect encoding: " + kind)
            out[: len(EFFECT_NUMBERS)] = [
                1,
                (slot + 1) / PASSIVE_CAPACITY,
                _bound(order),
                *[
                    _bound(effect.get(k))
                    for k in (
                        "effectValue1",
                        "effectValue2",
                        "effectTurn",
                        "effectCount",
                        "pickCountMin",
                        "pickCountMax",
                    )
                ],
                *[
                    effect.get("pickRangeType") == "ProducePickRangeType_" + k
                    for k in ("Select", "Random", "All")
                ],
            ]
            out[len(EFFECT_NUMBERS) + EFFECTS.index(kind)] = 1
            definition = _semantic_row(effect)
            search = definition.pop("produceCardSearchId", "")
            if search:
                definition["search"] = _semantic_row(
                    repository.load_table("ProduceCardSearch").first(search) or {}
                )
            out[-8:] = _fingerprint(definition)
    return result
