"""Compile HIF memory master chains to native golden phase declarations.

No examination effects execute in Python. One declaration belongs to one memory
effect, not to a deck instance: its native limit is shared by every matching card
and is recreated for each examination. The first-turn wrapper is preserved so
the listener precedes effects subsequently installed by cards such as Spotlight.
"""

from __future__ import annotations

from copy import deepcopy


PREFIX = "enchant-p_ef-hif_memory-"
DECLARATION_PREFIX = "hif-memory:"


class HifMemoryBridgeError(ValueError):
    """A recognized HIF memory has unsupported or inconsistent master semantics."""


def _row(table, key):
    row = table.first(key)
    if row is None:
        raise HifMemoryBridgeError(f"Missing HIF memory reference: {key}")
    return row


def _require(condition, description):
    if not condition:
        raise HifMemoryBridgeError(description)


def _semantics(row, allowed):
    """Reject additional active semantics rather than silently compiling a subset."""
    cosmetic = {"id", "assetId", "effectGroupIds"}
    for key, value in row.items():
        if key in allowed or key in cosmetic or "description" in key.lower():
            continue
        if value in (None, "", 0, False) or value == []:
            continue
        if isinstance(value, str) and value.endswith("_Unknown"):
            continue
        raise HifMemoryBridgeError(f"Unsupported HIF memory field {row['id']}/{key}: {value!r}")


def _target_ids(repository, search, definition_id, *, upgraded):
    _semantics(search, {"produceCardIds", "cardPositionType"})
    cards = search.get("produceCardIds") or []
    _require(len(cards) == 1, f"HIF memory needs a single master card target: {search['id']}")
    result = []
    for level in ((0, 1) if upgraded else (0,)):
        row = repository.card_row_by_upgrade(cards[0], level)
        _require(row is not None, f"Missing HIF memory card: {cards[0]}@{level}")
        native_id = definition_id("card", row)
        _require(type(native_id) is int, f"Invalid golden identity for {cards[0]}@{level}")
        result.append(native_id)
    return "|".join(f"id({native_id})" for native_id in dict.fromkeys(result))


def try_hif_memory_enchant(repository, spec, definition_id):
    """Return a native declaration, or ``None`` for a non-HIF-memory enchant.

    ``definition_id`` has GoldenProduceBridge.definition_id's (kind, row)
    signature. Call after explicit caller overrides and before generic carry
    conversion. Translate HifMemoryBridgeError to the public bridge error at the
    call site. HIF eligibility is enforced by the produce loadout resolver; this
    compiler deliberately does not infer a scenario from an enchant ID.
    """
    if not spec.enchant_id.startswith(PREFIX):
        return None
    _require(spec.effect_turn in (None, 0) and spec.effect_count in (None, 0, 1),
             f"Unexpected HIF memory carry duration/count: {spec.enchant_id}")
    outer = _row(repository.exam_status_enchants, spec.enchant_id)
    _semantics(outer, {"produceExamTriggerId", "produceExamEffectIds"})
    timer = _row(repository.exam_triggers, outer["produceExamTriggerId"])
    _semantics(timer, {"phaseTypes", "phaseValues"})
    _require(timer.get("phaseTypes") == ["ProduceExamPhaseType_ExamTurnTimer"]
             and timer.get("phaseValues") == [1], f"Unsupported HIF timer: {timer['id']}")
    grants = outer.get("produceExamEffectIds") or []
    _require(len(grants) == 1, f"Unsupported HIF memory grant: {outer['id']}")
    grant = _row(repository.exam_effects, grants[0])
    _semantics(grant, {"effectType", "effectCount", "effectTurn", "produceExamStatusEnchantId"})
    _require(grant.get("effectType") == "ProduceExamEffectType_ExamStatusEnchant"
             and grant.get("effectTurn") == -1 and grant.get("effectCount") in (1, 2),
             f"Unsupported HIF memory grant limit: {grant['id']}")
    inner = _row(repository.exam_status_enchants, grant["produceExamStatusEnchantId"])
    _semantics(inner, {"produceExamTriggerId", "produceExamEffectIds"})
    trigger = _row(repository.exam_triggers, inner["produceExamTriggerId"])
    _semantics(trigger, {"phaseTypes", "produceCardSearchId", "lowerSearchCount"})
    _require(trigger.get("phaseTypes") == ["ProduceExamPhaseType_ExamCardPlayAfter"]
             and trigger.get("lowerSearchCount") == 1, f"Unsupported HIF use trigger: {trigger['id']}")
    search = _row(repository.load_table("ProduceCardSearch"), trigger["produceCardSearchId"])
    _require(search.get("cardPositionType") == "ProduceCardPositionType_Target",
             f"Unsupported HIF used-card search: {search['id']}")
    target = _target_ids(repository, search, definition_id, upgraded=True)
    actions, kinds = [], []
    for effect_id in inner.get("produceExamEffectIds") or []:
        effect = _row(repository.exam_effects, effect_id)
        kind = effect["effectType"].removeprefix("ProduceExamEffectType_")
        kinds.append(kind)
        if kind == "ExamPlayableValueAdd":
            _semantics(effect, {"effectType", "effectCount"})
            _require(effect.get("effectCount") == 1, f"Unsupported extra-play count: {effect_id}")
            actions.append("cardUsesRemaining+=1")
        elif kind == "ExamCardDraw":
            _semantics(effect, {"effectType", "effectValue1"})
            _require(effect.get("effectValue1") == 1, f"Unsupported draw count: {effect_id}")
            actions.append("drawCard(1)")
        elif kind == "ExamCardMove":
            _semantics(effect, {"effectType", "produceCardSearchId", "movePositionType",
                                "pickRangeType", "pickCountMin", "pickCountMax"})
            _require(effect.get("movePositionType") == "ProduceCardMovePositionType_Lost"
                     and effect.get("pickRangeType") == "ProducePickRangeType_Random"
                     and effect.get("pickCountMin") == effect.get("pickCountMax") == 1,
                     f"Unsupported HIF removal: {effect_id}")
            removal = _row(repository.load_table("ProduceCardSearch"), effect["produceCardSearchId"])
            _require(removal.get("cardPositionType") == "ProduceCardPositionType_DeckGrave"
                     and removal.get("produceCardIds") == ["p_card-00-acc-0_002"],
                     f"Unsupported HIF removal range: {removal['id']}")
            remove_target = _target_ids(repository, removal, definition_id, upgraded=False)
            actions.append(f"removeRandom[(deck|discarded)&({remove_target})]")
        else:
            raise HifMemoryBridgeError(f"Unsupported HIF memory action: {effect_id} ({kind})")
    limits = {("ExamPlayableValueAdd",): 2,
              ("ExamPlayableValueAdd", "ExamCardDraw"): 1,
              ("ExamCardMove",): 1}
    _require(limits.get(tuple(kinds)) == grant["effectCount"],
             f"Unsupported HIF memory template/count: {inner['id']}")
    actions.append(f"limit:{grant['effectCount']}")
    effects = ("at:turn { if:turnsElapsed==0 { "
               f"at:afterCardUsed[{target}] {{ {'; '.join(actions)} }}"
               " }; limit:1 }")
    return {"id": DECLARATION_PREFIX + outer["id"], "effects": effects, "counters": {}}


def deduplicate_hif_memory_declarations(declarations):
    """Keep first HIF effect in carry order; never deduplicate unrelated abilities.

    This also handles repeated StartAudition grants across HIF rounds. An equal
    ID with different semantics is an error, preventing arbitrary caller
    overrides from silently winning a content conflict.
    """
    result, seen = [], {}
    for declaration in declarations:
        key = declaration["id"]
        if key.startswith(DECLARATION_PREFIX):
            if key in seen:
                _require(seen[key] == declaration, f"Conflicting HIF memory declaration: {key}")
                continue
            seen[key] = declaration
        result.append(deepcopy(declaration))
    return result


__all__ = ["HifMemoryBridgeError", "try_hif_memory_enchant", "deduplicate_hif_memory_declarations"]
