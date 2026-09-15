"""Conservative public-state compression for the current Arena support contract."""
from __future__ import annotations

from dataclasses import asdict
from .buckets import BuffContribution


_PLAIN_TRIGGERS = {
    "p_trigger-get_produce_card-0000_0000-p_card_search-deck_all": "ProducePhaseType_GetProduceCard",
    "p_trigger-get_produce_drink": "ProducePhaseType_GetProduceDrink",
}
_ADDITIONS = {"ProduceEffectType_VocalAddition": "vocal", "ProduceEffectType_DanceAddition": "dance",
              "ProduceEffectType_VisualAddition": "visual"}
_SKILL_FIELDS = frozenset({'skill_id', 'level', 'trigger_id', 'effect_ids', 'fire_limit',
                           'fire_count', 'activation_rate_permille', 'source'})
_ADDITION_FIELDS = frozenset({'id', 'produceEffectType', 'effectValueMin', 'effectValueMax', 'produceDescriptions'})
_ADDITION_DEFAULTS = {
    'produceResourceType': 'ProduceResourceType_Unknown', 'produceRewards': [],
    'produceCardSearchId': '', 'produceExamStatusEnchantId': '', 'produceStepEventDetailId': '',
    'pickRangeType': 'ProducePickRangeType_Unknown', 'pickCountMin': 0, 'pickCountMax': 0, 'isResearch': False,
}


def _plain_addition_fields(effect):
    # Projection runs before graph validation. Never remove a definition with
    # unrecognized fields, or its normal semantic-coverage check would vanish.
    return (set(effect) <= _ADDITION_FIELDS | _ADDITION_DEFAULTS.keys()
            and all(effect[key] == default for key, default in _ADDITION_DEFAULTS.items() if key in effect))


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _strings(child)


def build_buff_projection(observation, candidates=()):
    """Return an observational projection and a coverage report, without mutation.

    Certification deliberately covers only plain get-card/get-drink triggers,
    one nonnegative integer parameter addition, unlimited deterministic support
    abilities, and contiguous listeners. This mirrors inspected Arena arithmetic
    (positive integer gain + cap) without simulating or firing any rule. More
    complicated programs remain fully expanded and independently counted.
    """
    produce = observation.get("produce")
    rows = observation.get("mechanisms") or []
    if not produce or not rows or "buff_contributions" in observation:
        return observation, {"projected_sources": 0, "mode": "explicit_or_no_support"}
    index = {(r["table"], str(r.get("id", r.get("data", {}).get("id", "")))): r["data"] for r in rows}
    candidate_refs = set(_strings(candidates))
    kept, contributions, removed_skills, removed_effects, removed_triggers = [], [], set(), set(), set()
    phase_segments = {}
    unknown_barrier = 0
    for position, skill in enumerate(produce.get("support_skills", [])):
        trigger_id = skill.get("trigger_id")
        trigger = index.get(("ProduceTrigger", str(trigger_id)))
        phase = trigger.get("phaseType") if trigger else None
        ids = skill.get("effect_ids", [])
        effect = index.get(("ProduceEffect", str(ids[0]))) if len(ids) == 1 else None
        minimum = effect.get("effectValueMin") if effect else None
        maximum = effect.get("effectValueMax") if effect else None
        skill_id = str(skill.get("skill_id", ""))
        eligible = (trigger_id in _PLAIN_TRIGGERS and trigger is not None
                    and trigger.get("phaseType") == _PLAIN_TRIGGERS[trigger_id]
                    and set(trigger) <= {"id", "phaseType"}
                    and effect is not None and effect.get("produceEffectType") in _ADDITIONS
                    and _plain_addition_fields(effect) and set(skill) <= _SKILL_FIELDS
                    and isinstance(minimum, (int, float)) and minimum >= 0 and float(minimum).is_integer()
                    and minimum == maximum
                    and skill.get("source") in {"support_skill", "memory_skill"}
                    and skill.get("fire_limit") == 0
                    and skill.get("activation_rate_permille") in {0, 1000}
                    and skill_id not in candidate_refs and not candidate_refs.intersection(ids))
        if not eligible:
            kept.append(skill)
            if phase:
                phase_segments[phase] = phase_segments.get(phase, 0) + 1
            else:
                unknown_barrier += 1
            continue
        target = _ADDITIONS[effect["produceEffectType"]]
        contribution = BuffContribution(
            contribution_id=f"support:{position}:{skill_id}", trigger={"phase": trigger["phaseType"]},
            operation="add", target=target, value=float(minimum),
            predicate={"card_filter": "any"} if trigger_id.startswith("p_trigger-get_produce_card") else None,
            settlement={"unit": "parameter_points", "rounding": "integer", "cap": "parameter_growth_limit",
                        "chain_guard": "support_and_memory",
                        "listener_segment": [unknown_barrier, phase_segments.get(phase, 0)],
                        "projection_contract": "arena_support_plain_integer_add/1"},
            equivalent_settlement=True)
        contributions.append(asdict(contribution))
        removed_skills.add(skill_id); removed_effects.update(ids); removed_triggers.add(trigger_id)
    if not contributions:
        return observation, {"projected_sources": 0, "mode": "no_certified_rules"}
    # Only remove definitions whose sole remaining purpose was a projected rule.
    # A candidate or a retained program referencing the same effect keeps it live.
    remaining_rows = [r for r in rows if not (r["table"] == "ProduceSkill" and str(r.get("id")) in removed_skills)]
    tentative = [r for r in remaining_rows if not (
        r["table"] == "ProduceEffect" and str(r.get("id")) in removed_effects or
        r["table"] == "ProduceTrigger" and str(r.get("id")) in removed_triggers)]
    produce_copy = {**produce, "support_skills": kept}
    referenced = set(_strings(produce_copy)) | set(_strings(candidates))
    for row in tentative:
        referenced.update(_strings(row.get("data", {})))
    retained = []
    for row in remaining_rows:
        row_id = str(row.get("id"))
        removed = (row["table"] == "ProduceEffect" and row_id in removed_effects or
                   row["table"] == "ProduceTrigger" and row_id in removed_triggers)
        if not removed or row_id in referenced:
            retained.append(row)
    projected = {**observation, "produce": produce_copy, "mechanisms": retained,
                 "buff_contributions": contributions}
    return projected, {"projected_sources": len(contributions), "removed_skill_definitions": len(rows)-len(remaining_rows),
                       "retained_support_sources": len(kept), "mode": "certified_public_projection"}
