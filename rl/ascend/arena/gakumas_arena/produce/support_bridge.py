"""Support-card probabilities and master +2/+3 deltas for the native engine.

The original golden DSL remains the program. Only differences proven by the
master rows are compiled into atomic substitutions or unconditional insertions.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from functools import lru_cache
import math


class SkillCardSupportError(ValueError):
    pass


def _fmt(n):
    return f"{n:g}"


def _scaled(name, n):
    return name if n == 1 else f"{name}*{_fmt(n)}"


def _primitive(row):
    """Native expressions for the finite master differences, not all game rules."""
    kind = row.get("effectType", "").removeprefix("ProduceExamEffectType_")
    a, b, turns = row.get("effectValue1", 0), row.get("effectValue2", 0), row.get("effectTurn", 0)
    fields = {"ExamLesson": "score", "ExamBlock": "genki", "ExamBlockFix": "fixedGenki",
              "ExamLessonBuff": "concentration", "ExamReview": "goodImpressionTurns",
              "ExamCardPlayAggressive": "motivation", "ExamFullPowerPoint": "fullPowerCharge",
              "ExamStaminaRecoverFix": "fixedStamina", "ExamPlayableValueAdd": "cardUsesRemaining"}
    turn_fields = {"ExamParameterBuff": "goodConditionTurns", "ExamStaminaConsumptionDown": "halfCostTurns",
                   "ExamParameterBuffMultiplePerTurn": "perfectConditionTurns"}
    depend = {"ExamLessonDependParameterBuff": "goodConditionTurns", "ExamLessonDependStamina": "stamina",
              "ExamLessonDependBlock": "genki", "ExamLessonDependExamReview": "goodImpressionTurns",
              "ExamLessonDependExamCardPlayAggressive": "motivation"}
    if kind in fields:
        value = row.get("effectCount", 0) if kind == "ExamPlayableValueAdd" else a
        program = f"{fields[kind]}+={value}"
    elif kind in turn_fields:
        program = f"{turn_fields[kind]}+={turns}"
    elif kind in depend:
        program = f"score+={_scaled(depend[kind], a / 1000)}"
    elif kind == "ExamLessonBuffDependParameterBuff":
        program = f"concentration+={_scaled('goodConditionTurns', a / 1000)}"
    elif kind in ("ExamMultipleLessonBuffLesson", "ExamLessonAddMultipleParameterBuff", "ExamMultipleEnthusiasticLesson", "ExamBlockAddMultipleAggressive"):
        field, out = {"ExamMultipleLessonBuffLesson": ("concentrationMultiplier", "score"),
                      "ExamLessonAddMultipleParameterBuff": ("goodConditionTurnsMultiplier", "score"),
                      "ExamMultipleEnthusiasticLesson": ("enthusiasmMultiplier", "score"),
                      "ExamBlockAddMultipleAggressive": ("motivationMultiplier", "genki")}[kind]
        program = f"{field}={_fmt(1 + b / 1000)}; {out}+={a}"
    elif kind == "ExamReviewMultiple":
        program = f"setGoodImpressionTurnsEffectBuff({_fmt(a / 1000)}" + (f",{turns}" if turns > 0 else "") + ")"
    elif kind == "ExamBlockPerUseCardCount":
        program = f"genki+={a}+{_scaled('cardsUsed', b)}"
    elif kind == "ExamStaminaRecoverMultiple":
        program = f"fixedStamina+={_scaled('maxStamina', a / 1000)}"
    elif kind == "ExamCardDraw":
        program = "drawCard" if a == 1 else f"drawCard({a})"
    elif kind == "ExamLessonFullPowerPoint":
        program = "score+=" + (f"{a}+" if a else "") + _scaled('cumulativeFullPowerCharge', b / 1000)
    elif kind == "ExamPreservation":
        program = f"setStance(preservation{'2' if a == 2 else ''})"
    elif kind == "ExamEnthusiasticAdditive":
        program = f"setEnthusiasmBonus({a}" + (f",{turns}" if turns > 0 else "") + ")"
    elif kind in ("ProduceCardGrowEffectType_LessonAdd", "ProduceCardGrowEffectType_BlockAdd"):
        program = f"g.{'score' if kind.endswith('_LessonAdd') else 'genki'}+={row['value']}"
    else:
        return None
    if "score+=" in program and row.get("effectCount", 0) > 1:
        head, _, tail = program.rpartition("; ")
        return (head + "; " if head else "") + "; ".join([tail] * row["effectCount"])
    return program


def _semantic(row):
    return {k: v for k, v in row.items() if k not in {"id", "effectGroupIds"} and "escription" not in k}


def _leaves(repository, row, seen=()):
    if row["id"] in seen:
        raise SkillCardSupportError(f"Cyclic support variant effect: {row['id']}")
    seen = seen + (row["id"],)
    children = []
    semantic = _semantic(row)
    for key, table in (("chainProduceExamEffectId", repository.exam_effects),
                       ("produceExamStatusEnchantId", repository.exam_status_enchants),
                       ("produceCardStatusEnchantId", repository.load_table("ProduceCardStatusEnchant"))):
        if row.get(key):
            children += _leaves(repository, table.first(row[key]), seen)
            semantic[key] = "resolved-child"
    for key, table in (("produceExamEffectIds", repository.exam_effects),
                       ("chainProduceExamEffectIds", repository.exam_effects),
                       ("produceCardGrowEffectIds", repository.load_table("ProduceCardGrowEffect"))):
        if row.get(key):
            for identifier in row[key]:
                children += _leaves(repository, table.first(identifier), seen)
            semantic[key] = ["resolved-child"] * len(row[key])
    return [{"kind": row.get("effectType", "enchant"), "program": _primitive(row),
             "semantic": semantic, "id": row["id"]}] + children


def _card_leaves(repository, card, attribute):
    if attribute == "effects":
        identifier = card.get("produceCardStatusEnchantId")
        return _leaves(repository, repository.load_table("ProduceCardStatusEnchant").first(identifier)) if identifier else []
    result = []
    for effect in card["playEffects"]:
        result += _leaves(repository, repository.exam_effects.first(effect["produceExamEffectId"]))
    return result


def _diff_program(repository, base, variant, attribute):
    before = _card_leaves(repository, base, attribute)
    after = _card_leaves(repository, variant, attribute)
    patches = []
    for tag, i, j, k, l in SequenceMatcher(None, [x["kind"] for x in before], [x["kind"] for x in after], autojunk=False).get_opcodes():
        if tag == "equal":
            for offset, (a, b) in enumerate(zip(before[i:j], after[k:l])):
                if a["semantic"] == b["semantic"]:
                    continue
                if a["program"] is None or b["program"] is None:
                    # Parent ids can change while their executable child nodes
                    # remain the only material difference.
                    if a["semantic"] == b["semantic"]:
                        continue
                    raise SkillCardSupportError(f"Unmapped support delta: {base['id']} {a['id']} -> {b['id']}")
                old = a["program"]
                occurrence = sum(x["program"] == old for x in before[:i + offset])
                if old != b["program"]:
                    patches.append({"op": "replace", "old": old, "new": b["program"], "occurrence": occurrence})
        elif tag in ("insert", "delete", "replace"):
            old = before[i:j]
            new = after[k:l]
            if any(x["program"] is None for x in old + new):
                raise SkillCardSupportError(f"Unmapped structural support delta: {base['id']} level {variant['upgradeCount']}")
            # Existing data inserts direct effects at top level. Preserve their
            # relative position by locating the next executable original atom.
            anchor = next((x["program"] for x in before[j:] if x["program"]), None)
            occurrence = sum(x["program"] == anchor for x in before[:j]) if anchor else 0
            patches.append({"op": "splice", "old": "; ".join(x["program"] for x in old),
                            "new": "; ".join(x["program"] for x in new), "before": anchor,
                            "occurrence": occurrence})
    return patches


@lru_cache(maxsize=4)
def support_variant_catalog(repository, definition_id):
    """All existing +2/+3 differences, checked against fixed master rows."""
    variants = []
    for base in repository.load_table("ProduceCard").rows:
        if base["upgradeCount"] != 1:
            continue
        native_id = definition_id("card", base)
        level_zero = repository.card_row_by_upgrade(base["id"], 0, fallback_to_canonical=False)
        entry = {"master_card_id": base["id"], "base_definition_id": definition_id("card", level_zero),
                 "upgraded_definition_id": native_id, "levels": {}}
        for level in (2, 3):
            variant = repository.card_row_by_upgrade(base["id"], level, fallback_to_canonical=False)
            if variant is None:
                raise SkillCardSupportError(f"Missing support upgrade row: {base['id']}@{level}")
            programs = {attribute: _diff_program(repository, base, variant, attribute) for attribute in ("actions", "effects")}
            cost_patches = []
            for field, native in (("stamina", "cost"), ("forceStamina", "stamina"), ("costValue", None)):
                if base[field] == variant[field]:
                    continue
                if native is None:
                    native = {"ExamCostType_ExamLessonBuff": "concentration", "ExamCostType_ExamFullPowerPoint": "fullPowerCharge",
                              "ExamCostType_ExamParameterBuff": "goodConditionTurns", "ExamCostType_ExamReview": "goodImpressionTurns",
                              "ExamCostType_ExamCardPlayAggressive": "motivation"}.get(base["costType"])
                if native is None:
                    raise SkillCardSupportError(f"Unknown support cost: {base['costType']}")
                cost_patches.append({"op": "replace", "old": f"{native}-={base[field]}",
                                     "new": f"{native}-={variant[field]}", "occurrence": 0})
            programs["cost"] = cost_patches
            # The current master has one threshold-only higher-level change.
            trigger_pairs = zip(base["playEffects"], variant["playEffects"])
            for old, new in trigger_pairs:
                a, b = old["produceExamTriggerId"], new["produceExamTriggerId"]
                if a != b and a.startswith("e_trigger-exam_card_play-review_up-") and b.startswith("e_trigger-exam_card_play-review_up-"):
                    programs["actions"].append({"op": "condition", "field": "goodImpressionTurns",
                                                "old": int(a.rsplit("-", 1)[1]), "new": int(b.rsplit("-", 1)[1])})
            entry["levels"][str(level)] = {"name": variant["name"], "patches": programs}
        variants.append(entry)
    return variants


def build_skill_card_support(runtime, definition_id, settings=None):
    """Resolve source-specific level bonuses. No global reward-card rate reuse."""
    settings = settings or {}
    allowed = {"probability_overrides", "target_policy"}
    if set(settings) - allowed:
        raise SkillCardSupportError(f"Unknown support settings: {sorted(set(settings) - allowed)}")
    if settings.get("target_policy", "uniform") != "uniform":
        raise SkillCardSupportError("Only the explicitly approximate uniform hand-target policy is defined")
    repository = runtime.repository
    selected = getattr(runtime, "selected_support_cards", None)
    if selected is None:
        selected = runtime.idol_loadout.support_cards if runtime.idol_loadout else ()
    sources = []
    tables = [repository.load_table("SupportCardProduceSkillLevel" + suffix) for suffix in ("Vocal", "Dance", "Visual", "Assist")]
    overrides = settings.get("probability_overrides", {})
    for card in selected:
        identifier = card.support_card_id
        row = repository.support_cards.first(identifier)
        if row is None:
            raise SkillCardSupportError(f"Unknown support card: {identifier}")
        if row["upgradeProduceCardSearchId"] != "p_card_search-hand":
            raise SkillCardSupportError(f"Unexpected support target search: {identifier}")
        unlocked = {}
        for table in tables:
            for link in table.rows:
                if link["supportCardId"] == identifier and link["supportCardLevel"] <= card.support_card_level:
                    sid = link["produceSkillId"]
                    unlocked[sid] = max(unlocked.get(sid, 0), link["produceSkillLevel"])
        increments = []
        for sid, level in unlocked.items():
            skill = next(s for s in repository.load_table("ProduceSkill").all(sid) if s["level"] == level)
            for slot in (1, 2, 3):
                effect_id = skill.get(f"produceEffectId{slot}")
                effect = repository.produce_effects.first(effect_id) if effect_id else None
                if effect and effect["produceEffectType"] == "ProduceEffectType_SupportCardProduceCardUpgradeProbabilityUp":
                    if effect["effectValueMin"] != effect["effectValueMax"]:
                        raise SkillCardSupportError(f"Support probability is a range: {effect_id}")
                    increments.append({"skill_id": sid, "level": level, "effect_id": effect_id,
                                       "permil": effect["effectValueMin"]})
        # The skill says occurrence rate "increased by X%". For example
        # R Lv40 is +100% of its 19-permil base, not +100 percentage points.
        probability = min(1., row["produceCardUpgradePermil"] / 1000 *
                          (1 + sum(x["permil"] for x in increments) / 1000))
        probability = overrides.get(identifier, probability)
        if isinstance(probability, bool) or not isinstance(probability, (float, int)) or not math.isfinite(probability) or not 0 <= probability <= 1:
            raise SkillCardSupportError(f"Invalid support probability: {identifier}")
        color = row["produceCardUpgradeLessonParameterType"].removeprefix("ProduceParameterType_").lower()
        if color not in ("vocal", "dance", "visual", "unknown"):
            raise SkillCardSupportError(f"Unknown support lesson type: {color}")
        sources.append({"support_card_id": identifier, "level": card.support_card_level,
                        "turn_type": None if color == "unknown" else color, "probability": probability,
                        "base_permil": row["produceCardUpgradePermil"], "increments": increments,
                        "probability_overridden": identifier in overrides})
    if set(overrides) - {s["support_card_id"] for s in sources}:
        raise SkillCardSupportError("Support probability override references a card not in the loadout")
    return {"schema_version": "arena-skill-card-support/1", "sources": sources,
            "target_policy": "uniform", "order_policy": "loadout_order",
            "probability_model": "base_permil/1000 * (1 + own_skill_bonus_permil/1000)",
            "probability_basis": "Relative-increase interpretation of master skill descriptions; explicit overrides supported.",
            "sampling_approximation": "Per-source independent rolls; uniform legal hand target; loadout order.",
            "variants": support_variant_catalog(repository, definition_id) if sources else []}
