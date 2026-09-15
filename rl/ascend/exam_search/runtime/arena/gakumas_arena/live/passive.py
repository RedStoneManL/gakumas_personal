"""明确来源的已就绪触发状态；只装配，不重放开场、随机目标或效果。"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import Field, ValidationError

from gakumas_rl.simulation.exam.passive_catalog import PASSIVE_BY_ID
from gakumas_rl.simulation.exam.runtime import TriggeredEnchant

from .contracts import EntityRef, Observation, RunSetup, WireModel
from .session import MissingFields, ProtocolError


class ExamEnchantState(WireModel):
    """每个状态拥有独立身份与作用域；所有可空项也要求调用方明确传入。"""
    state_id: str = Field(min_length=1)
    exam_id: str = Field(min_length=1)
    enchant_id: str = Field(min_length=1)
    source: EntityRef
    source_level: int | None = Field(ge=1, strict=True)
    remaining_turns: int | None = Field(ge=1, strict=True)
    remaining_count: int | None = Field(ge=1, strict=True)
    applied_turn: int = Field(ge=0, strict=True)
    applied_phase: Literal['exam_start', 'turn_start', 'card_resolution', 'drink_resolution']
    last_fired_turn: int | None = Field(ge=1, strict=True)
    bound_card_instance_id: str | None
    once_per_turn: bool = Field(strict=True)


def _identity(entity: EntityRef) -> tuple:
    return (entity.instance_id, entity.kind, entity.definition_id, entity.upgrade_count,
            entity.customize_ids, entity.variant_fingerprint)


def _enchant_reachable(repository, enchant_id: str, target: str, seen=None) -> bool:
    """核验两层 HIF 开场包的定义关系，不执行效果。"""
    seen = set() if seen is None else seen
    if enchant_id == target:
        return True
    if enchant_id in seen:
        return False
    seen.add(enchant_id)
    row = repository.exam_status_enchant_map.get(enchant_id, {})
    return any(_enchant_reachable(repository, repository.exam_effect_map.get(e, {}).get('produceExamStatusEnchantId', ''),
                                  target, seen) for e in row.get('produceExamEffectIds', []))


def _source_matches(repository, setup: RunSetup, obs: Observation, state: ExamEnchantState, card_row, path: str) -> None:
    source = state.source
    if source.definition_id is None or not source.evidence or source.instance_id.startswith('unresolved:'):
        raise MissingFields(f'{path}.source.identity_evidence')
    spec = PASSIVE_BY_ID[state.enchant_id]
    if source.kind != spec.source_kind or source.definition_id != spec.source_definition_id:
        raise ProtocolError(f'{path}.source contradicts enchant definition')
    if source.kind == 'memory':
        if state.source_level is None:
            raise MissingFields(f'{path}.source_level')
        matches = [m for m in setup.loadout.memories if m.instance_id == source.instance_id]
        if len(matches) > 1:
            raise ProtocolError(f'{path}.source memory instance is ambiguous')
        memory = matches[0] if matches else None
        if memory is None or memory.ability_ids is None or memory.ability_levels is None:
            raise MissingFields(f'run_setup.loadout.memories.{source.instance_id}.ability_ids_and_levels')
        if len(memory.ability_ids) != len(memory.ability_levels):
            raise ProtocolError('memory ability IDs and levels length mismatch')
        if (source.definition_id, state.source_level) not in zip(memory.ability_ids, memory.ability_levels, strict=True):
            raise ProtocolError(f'{path}.source does not match equipped memory ability')
        ability = next((a for a in repository.load_table('MemoryAbility').rows
                        if a['id'] == source.definition_id and a['level'] == state.source_level), None)
        if ability is None:
            raise ProtocolError(f'{path}.unknown memory ability level')
        skill = next((s for s in repository.load_table('ProduceSkill').rows
                      if s['id'] == ability['skillId'] and s['level'] == state.source_level), {})
        roots = [repository.load_table('ProduceEffect').first(skill.get(f'produceEffectId{i}', '')) or {}
                 for i in (1, 2, 3)]
        if not ability['isUniqueActivation'] or not any(_enchant_reachable(repository,
                row.get('produceExamStatusEnchantId', ''), state.enchant_id) for row in roots):
            raise ProtocolError('memory master chain does not produce enchant')
    elif source.kind == 'item':
        inventory = obs.inventories.get('items')
        if inventory is None or inventory.coverage != 'complete':
            raise MissingFields('inventories.items.complete')
        if not any(_identity(e) == _identity(source) for e in inventory.entities):
            raise MissingFields(f'{path}.source.inventory_instance')
        item = repository.load_table('ProduceItem').first(source.definition_id)
        if item is None or item.get('originIdolCardId') != setup.loadout.idol_card_id:
            raise ProtocolError(f'{path}.source item does not match idol')
        rows = [repository.load_table('ProduceItemEffect').first(e) or {} for e in item['produceItemEffectIds']]
        if not any(e.get('produceExamStatusEnchantId') == state.enchant_id and e.get('effectCount') == 1 for e in rows):
            raise ProtocolError('item master chain does not produce enchant')
    else:
        found = [e for zone in ('hand', 'deck', 'discard', 'hold', 'lost', 'playing')
                 if (inv := obs.inventories.get(zone)) is not None and inv.coverage == 'complete'
                 for e in inv.entities if e.instance_id == source.instance_id]
        if not found:
            raise MissingFields(f'{path}.source.complete_card_zone')
        if len(found) != 1 or _identity(found[0]) != _identity(source):
            raise ProtocolError(f'{path}.source card identity conflict')
        row = card_row(source)
        if not any(repository.exam_effect_map.get(e['produceExamEffectId'], {}).get('produceExamStatusEnchantId')
                   == state.enchant_id for e in row['playEffects']):
            raise ProtocolError('source card does not produce enchant')
    if source.kind != 'memory' and state.source_level is not None:
        raise ProtocolError('source_level is only for a memory ability')


def prepare_passives(repository, setup: RunSetup, obs: Observation, card_row) -> list[TriggeredEnchant]:
    """同帧聚合被动结构/来源缺项；尚未覆盖的规则用独立 unsupported 路径。"""
    profile = obs.facts.get('exam_passive_version')
    if profile is not None and profile.status == 'observed' and profile.value == 'arena-passive/2':
        from .passive_generic import prepare_generic_passives
        return prepare_generic_passives(repository, setup, obs, card_row)
    fact = obs.facts.get('exam_enchants')
    if fact is None or fact.status != 'observed':
        raise MissingFields('facts.exam_enchants')
    raw = fact.value
    if not isinstance(raw, list):
        raise MissingFields('contract.facts.exam_enchants.list')
    issues = []
    for name, expected in (('exam_passive_version', 'arena-passive/1'), ('exam_counter_semantics', 'arena-exam-counters/1')):
        value = obs.facts.get(name)
        if value is None or value.status != 'observed':
            if raw:
                issues.append(f'facts.{name}')
        elif value.value != expected:
            issues.append(f'contract.facts.{name}.version')
    scheduled = obs.facts.get('exam_scheduled_effects')
    profile = obs.facts.get('exam_passive_version')
    if (raw or (profile is not None and profile.status == 'observed')) and (scheduled is None or scheduled.status != 'observed'):
        issues.append('facts.exam_scheduled_effects')
    if scheduled is not None and scheduled.status == 'observed':
        if not isinstance(scheduled.value, list):
            issues.append('contract.facts.exam_scheduled_effects.list')
        elif scheduled.value:
            issues.append('unsupported.exam.scheduled_effects')
    result, identities, semantics = [], set(), set()
    for index, item in enumerate(raw):
        path = f'facts.exam_enchants.{index}'
        try:
            state = ExamEnchantState.model_validate(item)
        except ValidationError as exc:
            for error in exc.errors(include_url=False):
                detail = '.'.join((path, *map(str, error['loc'])))
                issues.append(detail if error['type'] == 'missing' else 'contract.' + detail + '.' + error['type'])
            continue
        if state.state_id in identities:
            issues.append('contract.' + path + '.duplicate_state_id')
        identities.add(state.state_id)
        spec = PASSIVE_BY_ID.get(state.enchant_id)
        if spec is None:
            issues.append('unsupported.exam.enchant.' + state.enchant_id)
            continue
        if state.enchant_id in semantics:
            issues.append(('contract.' if spec.count == 1 else 'unsupported.') + path + '.duplicate_enchant')
        semantics.add(state.enchant_id)
        exam = obs.facts.get('exam_id')
        turn = obs.facts.get('turn')
        if exam is not None and exam.status == 'observed' and state.exam_id != exam.value:
            issues.append('contract.' + path + '.exam_scope')
        if (turn is not None and turn.status == 'observed' and isinstance(turn.value, int)
                and (state.applied_turn > turn.value or (state.last_fired_turn is not None
                     and not state.applied_turn <= state.last_fired_turn <= turn.value))):
            issues.append('contract.' + path + '.application_time')
        if state.applied_turn == 0 and state.applied_phase != 'exam_start':
            issues.append('contract.' + path + '.application_phase')
        if state.applied_phase == 'exam_start' and state.applied_turn > 1:
            issues.append('contract.' + path + '.application_phase')
        if state.bound_card_instance_id is not None or state.once_per_turn:
            issues.append('unsupported.' + path + '.bound_or_once_per_turn')
        if state.remaining_turns is not None or state.remaining_count != spec.count:
            issues.append('contract.' + path + '.duration_or_count')
        if spec.count == 1 and state.last_fired_turn is not None:
            issues.append('contract.' + path + '.exhausted_single_use')
        row = repository.exam_status_enchant_map.get(state.enchant_id, {})
        if (row.get('produceExamTriggerId') != spec.trigger_id or tuple(row.get('produceExamEffectIds', [])) != spec.effect_ids
                or spec.trigger_id not in repository.exam_trigger_map
                or any(e not in repository.exam_effect_map for e in spec.effect_ids)):
            issues.append('unsupported.exam.passive.master_definition_changed.' + state.enchant_id)
            continue
        try:
            _source_matches(repository, setup, obs, state, card_row, path)
        except MissingFields as exc:
            issues.extend(exc.fields)
        except ProtocolError as exc:
            issues.append('contract.' + str(exc))
        uid = int.from_bytes(hashlib.sha256(f'{setup.run_id}\0{state.exam_id}\0passive\0{state.state_id}'.encode()).digest()[:8], 'big')
        marker = state.applied_turn - (1 if state.applied_phase == 'turn_start' else 0)
        result.append(TriggeredEnchant(uid, state.enchant_id, spec.trigger_id, list(spec.effect_ids),
            state.remaining_turns, state.remaining_count, 'produce_item' if state.source.kind == 'item' else state.source.kind,
            marker, state.source.instance_id, last_fired_turn=state.last_fired_turn if state.last_fired_turn is not None else -1))
    if issues:
        raise MissingFields(*dict.fromkeys(issues))
    return result
