"""arena-passive/2: source-chain and mechanism validation without an identity whitelist."""

from __future__ import annotations

import hashlib

from pydantic import ValidationError

from gakumas_arena.content.capabilities import inspect_enchant
from gakumas_rl.simulation.exam.runtime import TriggeredEnchant

from .passive import ExamEnchantState, _identity
from .session import MissingFields, ProtocolError


def source_limits(repository, setup, obs, state, card_row, path):
    source = state.source
    if (
        not source.definition_id
        or not source.evidence
        or source.instance_id.startswith("unresolved:")
    ):
        raise MissingFields(path + ".source.identity_evidence")
    roots = []
    if source.kind == "memory":
        if state.source_level is None:
            raise MissingFields(path + ".source_level")
        matches = [m for m in setup.loadout.memories if m.instance_id == source.instance_id]
        if len(matches) > 1:
            raise ProtocolError("duplicate memory instance")
        if not matches or matches[0].ability_ids is None or matches[0].ability_levels is None:
            raise MissingFields(
                f"run_setup.loadout.memories.{source.instance_id}.ability_ids_and_levels"
            )
        memory = matches[0]
        if len(memory.ability_ids) != len(memory.ability_levels):
            raise ProtocolError("memory ability IDs/levels mismatch")
        if (source.definition_id, state.source_level) not in zip(
            memory.ability_ids, memory.ability_levels
        ):
            raise ProtocolError("memory ability not equipped")
        ability = next(
            (
                a
                for a in repository.load_table("MemoryAbility").all(source.definition_id)
                if a.get("level") == state.source_level
            ),
            None,
        )
        if ability is None:
            raise ProtocolError("unknown memory ability level")
        skill = next(
            (
                s
                for s in repository.load_table("ProduceSkill").all(ability["skillId"])
                if s.get("level") == state.source_level
            ),
            None,
        )
        if skill is None:
            raise ProtocolError("unknown memory skill level")
        roots = [
            repository.load_table("ProduceEffect").first(skill.get(f"produceEffectId{i}", ""))
            for i in (1, 2, 3)
        ]
    elif source.kind == "item":
        inventory = obs.inventories.get("items")
        if inventory is None or inventory.coverage != "complete":
            raise MissingFields("inventories.items.complete")
        matches = [e for e in inventory.entities if e.instance_id == source.instance_id]
        if not matches:
            raise MissingFields(path + ".source.inventory_instance")
        if len(matches) != 1 or _identity(matches[0]) != _identity(source):
            raise ProtocolError("item instance identity conflict")
        item = repository.load_table("ProduceItem").first(source.definition_id)
        if item is None or item.get("originIdolCardId", "") not in ("", setup.loadout.idol_card_id):
            raise ProtocolError("item origin does not match equipped idol")
        roots = [
            repository.load_table("ProduceItemEffect").first(e)
            for e in item.get("produceItemEffectIds", [])
        ]
    elif source.kind == "card":
        matches = [
            e
            for z in ("hand", "deck", "discard", "hold", "lost", "playing")
            if (inv := obs.inventories.get(z)) is not None and inv.coverage == "complete"
            for e in inv.entities
            if e.instance_id == source.instance_id
        ]
        if not matches:
            raise MissingFields(path + ".source.complete_card_zone")
        if len(matches) != 1 or _identity(matches[0]) != _identity(source):
            raise ProtocolError("card instance identity conflict")
        card = card_row(source)
        roots = [
            repository.exam_effect_map.get(e["produceExamEffectId"])
            for e in card.get("playEffects", [])
        ]
    else:
        raise MissingFields("unsupported.exam.passive.source." + source.kind)
    if source.kind != "memory" and state.source_level is not None:
        raise ProtocolError("source_level applies only to memory abilities")
    found = []

    def traverse(effect, seen):
        if not effect or effect.get("id") in seen:
            return
        seen = seen | {effect.get("id")}
        enchant = effect.get("produceExamStatusEnchantId")
        if enchant == state.enchant_id:
            # Both produce and exam tables use effectTurn/effectCount for these sources.
            turn = int(effect.get("effectTurn") or (1 if effect.get("effectType") else -1))
            count = int(effect.get("effectCount") or 0)
            found.append((turn if turn > 0 else None, count if count > 0 else None))
        if enchant:
            row = repository.exam_status_enchant_map.get(enchant, {})
            for key in row.get("produceExamEffectIds", []):
                traverse(repository.exam_effect_map.get(key), seen)
        chain = effect.get("chainProduceExamEffectId")
        if chain:
            traverse(repository.exam_effect_map.get(chain), seen)

    for root in roots:
        traverse(root, set())
    if not found:
        raise ProtocolError("source definition does not produce this enchant")
    return found


def prepare_generic_passives(repository, setup, obs, card_row):
    issues, result = [], []
    raw = obs.facts.get("exam_enchants")
    if raw is None or raw.status != "observed":
        raise MissingFields("facts.exam_enchants")
    if not isinstance(raw.value, list):
        raise MissingFields("contract.facts.exam_enchants.list")
    for name, expected in (("exam_counter_semantics", "arena-exam-counters/1"),):
        fact = obs.facts.get(name)
        if fact is None or fact.status != "observed":
            issues.append("facts." + name)
        elif fact.value != expected:
            issues.append("contract.facts." + name + ".version")
    scheduled = obs.facts.get("exam_scheduled_effects")
    if scheduled is None or scheduled.status != "observed":
        issues.append("facts.exam_scheduled_effects")
    elif not isinstance(scheduled.value, list):
        issues.append("contract.facts.exam_scheduled_effects.list")
    elif scheduled.value:
        issues.append("unsupported.exam.scheduled_effects")
    seen, sources = set(), set()
    for index, payload in enumerate(raw.value):
        path = f"facts.exam_enchants.{index}"
        try:
            state = ExamEnchantState.model_validate(payload)
        except ValidationError as exc:
            for e in exc.errors(include_url=False):
                loc = path + "." + ".".join(map(str, e["loc"]))
                issues.append(loc if e["type"] == "missing" else "contract." + loc)
            continue
        if state.state_id in seen:
            issues.append("contract." + path + ".duplicate_state_id")
        seen.add(state.state_id)
        identity = (state.enchant_id, state.source.instance_id)
        if identity in sources:
            issues.append("unsupported." + path + ".multiple_applications_same_source")
        sources.add(identity)
        for name in ("exam_id", "turn"):
            fact = obs.facts.get(name)
            if fact is None or fact.status != "observed":
                issues.append("facts." + name)
        exam, turn = obs.facts.get("exam_id"), obs.facts.get("turn")
        if exam and exam.status == "observed" and state.exam_id != exam.value:
            issues.append("contract." + path + ".exam_scope")
        if (
            turn
            and turn.status == "observed"
            and type(turn.value) is int
            and (
                state.applied_turn > turn.value
                or (
                    state.last_fired_turn is not None
                    and not max(1, state.applied_turn) <= state.last_fired_turn <= turn.value
                )
            )
        ):
            issues.append("contract." + path + ".application_time")
        if (state.applied_turn == 0 and state.applied_phase != "exam_start") or (
            state.applied_phase == "exam_start" and state.applied_turn > 1
        ):
            issues.append("contract." + path + ".application_phase")
        if state.bound_card_instance_id is not None or state.once_per_turn:
            issues.append("unsupported." + path + ".bound_or_once_per_turn")
        unsupported = inspect_enchant(repository, state.enchant_id, live=True)
        if unsupported:
            issues.extend(
                "unsupported.exam.passive." + i.path + "." + i.mechanism for i in unsupported
            )
            continue
        try:
            limits = source_limits(repository, setup, obs, state, card_row, path)

            def fits(limit, remaining):
                return (
                    remaining is None
                    if limit is None
                    else remaining is not None and remaining <= limit
                )

            if not any(
                fits(t, state.remaining_turns) and fits(c, state.remaining_count) for t, c in limits
            ):
                issues.append("contract." + path + ".duration_or_count")
            if state.last_fired_turn is not None and all(c == 1 for _, c in limits):
                issues.append("contract." + path + ".exhausted_single_use")
            matching_counts = [
                c
                for t, c in limits
                if fits(t, state.remaining_turns) and fits(c, state.remaining_count)
            ]
            if matching_counts and all(c is not None for c in matching_counts):
                if state.last_fired_turn is None and all(
                    state.remaining_count < c for c in matching_counts
                ):
                    issues.append("contract." + path + ".missing_fire_history")
                if state.last_fired_turn is not None and all(
                    state.remaining_count == c for c in matching_counts
                ):
                    issues.append("contract." + path + ".unchanged_count_after_fire")
        except MissingFields as exc:
            issues.extend(exc.fields)
        except ProtocolError:
            issues.append("contract." + path + ".source_chain")
        row = repository.exam_status_enchant_map[state.enchant_id]
        uid = int.from_bytes(
            hashlib.sha256(
                f"{setup.run_id}\0{state.exam_id}\0passive\0{state.state_id}".encode()
            ).digest()[:8],
            "big",
        )
        result.append(
            TriggeredEnchant(
                uid,
                state.enchant_id,
                row["produceExamTriggerId"],
                list(row.get("produceExamEffectIds", [])),
                state.remaining_turns,
                state.remaining_count,
                "produce_item" if state.source.kind == "item" else state.source.kind,
                state.applied_turn - (state.applied_phase == "turn_start"),
                state.source.instance_id,
                last_fired_turn=state.last_fired_turn if state.last_fired_turn is not None else -1,
            )
        )
    from gakumas_rl.simulation.exam.structural_encoding import EFFECT_CAPACITY, PASSIVE_CAPACITY

    if len(result) > PASSIVE_CAPACITY:
        issues.append("unsupported.exam.passive.capacity")
    if sum(len(enchant.effect_ids) for enchant in result) > EFFECT_CAPACITY:
        issues.append("unsupported.exam.passive.effect_capacity")
    if issues:
        raise MissingFields(*dict.fromkeys(issues))
    return result
