"""Strict native inventory boundary shared by authoring and the real-content catalogue.

Eligibility means the definition has a supported execution path, not real-game fidelity.
Produce lifecycle items must not silently become inert exam-only items.
"""

from __future__ import annotations

from .capabilities import CapabilityIssue, inspect_definition

NATIVE_EXAM_CAPABILITY_VERSION = "arena-native-exam-capabilities/3"


def inspect_native_exam(repository, table, row, *, live=False):
    issues = []
    roots = []
    path = f"{table}.{row['id']}"

    def reject(message):
        issues.append(CapabilityIssue(path, message))

    if table == "ProduceCard":
        for effect in row.get("playEffects", []):
            for field, kind in (
                ("produceExamEffectId", "effect"),
                ("produceExamTriggerId", "trigger"),
            ):
                if effect.get(field):
                    roots.append((kind, effect[field]))
        if row.get("playProduceExamTriggerId"):
            roots.append(("trigger", row["playProduceExamTriggerId"]))
        if row.get("produceCardStatusEnchantId"):
            roots.append(("card_enchant", row["produceCardStatusEnchantId"]))
        if row.get("moveProduceExamEffectIds") or row.get("moveProduceExamTriggerIds"):
            if live:
                reject("card_move_live_binding_not_verified")
            if row.get("moveEffectTriggerType") not in {
                "ProduceCardMoveEffectTriggerType_Hand",
                "ProduceCardMoveEffectTriggerType_Hold",
            }:
                reject("unsupported_card_move_destination")
            if row.get("moveProduceExamTriggerIds"):
                reject("card_move_conditions_not_bound")
            roots.extend(("effect", key) for key in row.get("moveProduceExamEffectIds", []))
    elif table == "ProduceDrink":
        for key in row.get("produceDrinkEffectIds", []):
            effect = repository.load_table("ProduceDrinkEffect").first(key)
            if effect is None:
                reject("unknown_drink_effect:" + key)
                continue
            if effect.get("produceEffectId"):
                reject("drink_requires_produce_lifecycle")
            if effect.get("produceExamEffectId"):
                roots.append(("effect", effect["produceExamEffectId"]))
    elif table == "ProduceItem":
        if (
            row.get("produceTriggerId")
            or row.get("produceTriggerIds")
            or row.get("fireLimit")
            or row.get("fireInterval")
            or any(s.get("produceTriggerId") for s in row.get("skills", []))
        ):
            reject("item_requires_produce_lifecycle")
        for key in row.get("produceItemEffectIds", []):
            effect = repository.load_table("ProduceItemEffect").first(key)
            if effect is None:
                reject("unknown_item_effect:" + key)
                continue
            if effect.get("effectType") != "ProduceItemEffectType_ExamStatusEnchant":
                reject("item_requires_produce_lifecycle")
            elif effect.get("produceExamStatusEnchantId"):
                roots.append(("enchant", effect["produceExamStatusEnchantId"]))
            else:
                reject("missing_item_enchant:" + key)
    else:
        reject("not_an_exam_inventory_type")
    for kind, key in roots:
        issues.extend(inspect_definition(repository, kind, key, live=live))
    return tuple(dict.fromkeys(issues))


def native_item_enchants(repository, item_id, *, identity):
    row = repository.produce_items.first(item_id)
    if row is None:
        raise ValueError(f"unknown item: {item_id}")
    issues = inspect_native_exam(repository, "ProduceItem", row)
    if issues:
        raise ValueError("; ".join(i.mechanism for i in issues))
    specs = []
    for index, key in enumerate(row.get("produceItemEffectIds", [])):
        effect = repository.load_table("ProduceItemEffect").first(key)
        turns, count = int(effect.get("effectTurn", 0)), int(effect.get("effectCount", 0))
        specs.append(
            {
                "enchant_id": effect["produceExamStatusEnchantId"],
                "effect_turn": turns if turns > 0 else None,
                "effect_count": count if count > 0 else None,
                "source": "item",
                "source_identity": f"{identity}:{index}:{item_id}",
            }
        )
    return specs
