"""Mechanism-level support inspection, independent of card/enchant identity."""

from __future__ import annotations

from dataclasses import dataclass

from gakumas_rl.simulation.exam.effects.registry import EXAM_EFFECT_REGISTRY
from gakumas_rl.simulation.exam.ids import ExamEffect, ExamPhase, FieldStatus, GrowEffect

LIVE_FIELDS = {
    FieldStatus.BLOCK_UP: "block",
    FieldStatus.NO_BLOCK: "block",
    FieldStatus.LESSON_BUFF_UP: "lesson_buff",
    FieldStatus.PARAMETER_BUFF: "parameter_buff",
    FieldStatus.PARAMETER_BUFF_UP: "parameter_buff",
    FieldStatus.PARAMETER_BUFF_MULTIPLE_PER_TURN_UP: "parameter_buff_multiple_per_turn",
    FieldStatus.STAMINA_LESS_MULTIPLE: "stamina",
    FieldStatus.STAMINA_UP_MULTIPLE: "stamina",
    FieldStatus.REMAINING_TURN: "turn",
    FieldStatus.TURN_PROGRESS_UP: "turn",
    FieldStatus.PLAY_CARD_SKILL: "plays_used",
    FieldStatus.REVIEW_UP: "review",
    FieldStatus.CARD_PLAY_AGGRESSIVE_UP: "aggressive",
}
LIVE_PHASES = {
    ExamPhase.START_EXAM,
    ExamPhase.START_TURN,
    ExamPhase.END_TURN,
    "ProduceExamPhaseType_ExamCardPlay",
    "ProduceExamPhaseType_ExamCardPlayAfter",
}
LIVE_EFFECTS = {
    ExamEffect.LESSON,
    ExamEffect.LESSON_FIX,
    ExamEffect.BLOCK,
    ExamEffect.BLOCK_FIX,
    ExamEffect.LESSON_BUFF,
    ExamEffect.PARAMETER_BUFF,
    ExamEffect.PARAMETER_BUFF_MULTIPLE_PER_TURN,
    ExamEffect.REVIEW,
    ExamEffect.CARD_PLAY_AGGRESSIVE,
    ExamEffect.STAMINA_RECOVER,
    ExamEffect.STAMINA_RECOVER_FIX,
    ExamEffect.STAMINA_REDUCE,
    ExamEffect.CARD_DRAW,
    ExamEffect.PLAYABLE_VALUE_ADD,
    ExamEffect.CARD_MOVE,
    ExamEffect.LESSON_VALUE_MULTIPLE,
    ExamEffect.STAMINA_CONSUMPTION_DOWN,
}


@dataclass(frozen=True)
class CapabilityIssue:
    path: str
    mechanism: str


def inspect_enchant(repository, enchant_id: str, *, live: bool = False):
    """Return unsupported mechanisms, never infer current instance state from definitions."""
    return inspect_definition(repository, "enchant", enchant_id, live=live)


def inspect_definition(repository, root_kind: str, root_id: str, *, live: bool = False):
    """Inspect an effect/trigger/enchant dependency closure without executing it."""
    issues = []
    active = set()
    visited = set()
    phases = {v for k, v in vars(ExamPhase).items() if k.isupper()}
    fields = {v for k, v in vars(FieldStatus).items() if k.isupper()}
    effects = {v for k, v in vars(ExamEffect).items() if k.isupper()}

    def reject(path, mechanism):
        issues.append(CapabilityIssue(path, mechanism))

    def search(sid, path):
        row = repository.load_table("ProduceCardSearch").first(sid)
        if row is None:
            reject(path, "unknown_search")
        elif live and (
            row.get("isSelf")
            or row.get("produceCardRandomPoolId")
            or row.get("produceCardPoolId")
            or row.get("effectGroupIds")
            or row.get("cardStatusType", "").replace("ProduceCardSearchStatusType_Unknown", "")
        ):
            reject(path, "search_requires_unbound_history_or_pool")

    def visit(kind, key):
        path = f"{kind}.{key}"
        if (kind, key) in active:
            reject(path, "recursive_definition")
            return
        if (kind, key) in visited:
            return
        active.add((kind, key))
        try:
            if kind in {"card_enchant", "growth"}:
                table = (
                    "ProduceCardStatusEnchant"
                    if kind == "card_enchant"
                    else "ProduceCardGrowEffect"
                )
                row = repository.load_table(table).first(key)
                if row is None:
                    reject(path, "unknown_" + kind)
                    return
                if live:
                    reject(path, "card_bound_or_growth")
                if kind == "growth" and row.get("effectType") not in {
                    v for k, v in vars(GrowEffect).items() if k.isupper()
                }:
                    reject(path, row.get("effectType", "unknown_growth_type"))
                if row.get("produceExamTriggerId"):
                    visit("trigger", row["produceExamTriggerId"])
                if row.get("produceCardStatusEnchantId"):
                    visit("card_enchant", row["produceCardStatusEnchantId"])
                for growth in row.get("produceCardGrowEffectIds", []):
                    visit("growth", growth)
            elif kind == "enchant":
                row = repository.exam_status_enchant_map.get(key)
                if row is None:
                    reject(path, "unknown_enchant")
                    return
                visit("trigger", row.get("produceExamTriggerId", ""))
                for effect in row.get("produceExamEffectIds", []):
                    visit("effect", effect)
            elif kind == "trigger":
                row = repository.exam_trigger_map.get(key)
                if row is None:
                    reject(path, "unknown_trigger")
                    return
                for phase in row.get("phaseTypes", []):
                    if phase not in (LIVE_PHASES if live else phases):
                        reject(path, phase)
                for field in row.get("fieldStatusTypes", []):
                    if field not in (LIVE_FIELDS if live else fields):
                        reject(path, field)
                if row.get("produceCardSearchId"):
                    search(row["produceCardSearchId"], path)
                if live and (row.get("fieldStatusProduceCardSearchIds") or row.get("effectTypes")):
                    reject(path, "trigger_requires_effect_or_search_history")
            else:
                row = repository.exam_effect_map.get(key)
                if row is None:
                    reject(path, "unknown_effect")
                    return
                effect_type = row.get("effectType", "")
                if (live and effect_type not in LIVE_EFFECTS) or (
                    not live
                    and (
                        effect_type not in effects
                        or not EXAM_EFFECT_REGISTRY.is_registered(effect_type)
                    )
                    and effect_type not in getattr(repository, "content_handlers", {})
                ):
                    reject(path, effect_type)
                if row.get("produceCardSearchId"):
                    search(row["produceCardSearchId"], path)
                if row.get("produceExamStatusEnchantId"):
                    visit("enchant", row["produceExamStatusEnchantId"])
                if row.get("chainProduceExamEffectId"):
                    visit("effect", row["chainProduceExamEffectId"])
                for chain in row.get("chainProduceExamEffectIds", []):
                    visit("effect", chain)
                for growth in row.get("produceCardGrowEffectIds", []):
                    visit("growth", growth)
                if row.get("produceCardStatusEnchantId"):
                    visit("card_enchant", row["produceCardStatusEnchantId"])
                if live and (
                    row.get("produceCardStatusEnchantId") or row.get("produceCardGrowEffectIds")
                ):
                    reject(path, "card_bound_or_growth")
        finally:
            active.remove((kind, key))
            visited.add((kind, key))

    visit(root_kind, root_id)
    return tuple(issues)
