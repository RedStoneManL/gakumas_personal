"""Autoregressive research loadouts, committed before the real Arena reset."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json


INVENTORY_SCHEMA = 'gakumas-setup-inventory/1'
RESEARCH_RULESET = 'hif-research-gold-compositional/1'
START_PHASE = 'ProduceMemoryProduceCardPhaseType_ProduceStart'
RESEARCH_CARD_BUDGET = {'ProduceCardRarity_R': 2, 'ProduceCardRarity_Sr': 1,
                        'ProduceCardRarity_Ssr': 1}


def resolve_setup_inventory(repository, inventory):
    """Validate explicit candidates; never synthesize levels or memory effects."""
    from gakumas_arena.produce.loadout_handoff import _memory_from_wire
    from gakumas_rl.idol_config import (
        _resolve_support_card_level, apply_card_customizations, memory_spec_from_gift)
    if not isinstance(inventory, dict) or inventory.get('schema_version') != INVENTORY_SCHEMA:
        raise ValueError(f'setup_inventory requires schema_version={INVENTORY_SCHEMA}')
    if set(inventory) - {'schema_version', 'supports', 'memories', 'memory_components', 'provenance'}:
        raise ValueError('Unknown setup_inventory fields')
    if not isinstance(inventory.get('supports'), list) or not isinstance(inventory.get('memories'), list):
        raise ValueError('setup_inventory requires supports and memories lists')
    supports, memories, seen_supports, seen_memories = [], [], set(), set()
    for value in inventory['supports']:
        if not isinstance(value, dict) or set(value) != {'support_card_id', 'level'}:
            raise ValueError('Support candidate requires only support_card_id and level')
        identity, level = value['support_card_id'], value['level']
        if not isinstance(identity, str) or not identity or identity in seen_supports:
            raise ValueError('Setup support IDs must be nonempty and unique')
        row = repository.support_cards.first(identity)
        if row is None:
            raise ValueError(f'Unknown setup support: {identity}')
        if type(level) is not int or level != _resolve_support_card_level(row, level):
            raise ValueError(f'Invalid explicit setup support level: {identity}/{level}')
        seen_supports.add(identity)
        supports.append({'id': f'setup:support:{identity}', 'support_card_id': identity, 'level': level})
    for value in inventory['memories']:
        if not isinstance(value, dict) or set(value) not in (
                {'memory_id', 'gift_id'}, {'memory_id', 'spec'}):
            raise ValueError('Memory candidate requires memory_id and exactly one of gift_id/spec')
        identity = value['memory_id']
        if not isinstance(identity, str) or not identity or identity in seen_memories:
            raise ValueError('Setup memory IDs must be nonempty and unique')
        if 'gift_id' in value:
            spec = memory_spec_from_gift(repository, value['gift_id'])
        else:
            if not isinstance(value['spec'], dict):
                raise ValueError('Explicit memory spec must be a complete JSON record')
            if not {'ability_ids', 'ability_levels', 'produce_card'} <= set(value['spec']):
                raise ValueError('Explicit memory spec requires ability IDs, levels and produce_card')
            spec = _memory_from_wire(value['spec'])
        spec = replace(spec, memory_id=identity)
        if spec.idol_card_id and repository.load_table('IdolCard').first(spec.idol_card_id) is None:
            raise ValueError(f'Unknown setup memory source idol: {spec.idol_card_id}')
        if len(spec.ability_ids) != len(spec.ability_levels):
            raise ValueError(f'Memory ability IDs/levels must align: {identity}')
        if len(set(spec.ability_ids)) != len(spec.ability_ids):
            raise ValueError(f'Duplicate ability within one memory: {identity}')
        for ability_id, level in zip(spec.ability_ids, spec.ability_levels, strict=True):
            rows = repository.load_table('MemoryAbility').all(ability_id)
            if type(level) is not int or not any(row.get('level') == level for row in rows):
                raise ValueError(f'Unknown exact memory ability level: {ability_id}/{level}')
        card = spec.produce_card
        if card is not None:
            if type(card.upgrade_count) is not int or card.upgrade_count < 0:
                raise ValueError(f'Invalid memory card upgrade: {identity}')
            row = repository.card_row_by_upgrade(card.card_id, card.upgrade_count, fallback_to_canonical=False)
            if row is None:
                raise ValueError(f'Unknown memory card variant: {identity}')
            if card.phase_type not in ('ProduceMemoryProduceCardPhaseType_ProduceStart',
                                       'ProduceMemoryProduceCardPhaseType_EndAuditionMid'):
                raise ValueError(f'Unknown memory acquisition phase: {identity}')
            apply_card_customizations(repository, row, card.customize_ids)
        seen_memories.add(identity)
        memories.append({'id': f'setup:memory:{identity}', 'memory_id': identity, 'spec': asdict(spec)})
    digest = hashlib.sha256(json.dumps(inventory, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()
    return supports, memories, digest


def resolve_setup_catalog(repository, inventory):
    """Resolve the finite component graph once; never build its Cartesian product."""
    supports, memories, digest = resolve_setup_inventory(repository, inventory)
    components = inventory.get('memory_components')
    result = {'supports': supports, 'memories': memories, 'digest': digest, 'components': None,
              'provenance': deepcopy(inventory.get('provenance', {}))}
    if components is None:
        return result
    if memories:
        raise ValueError('Choose complete memories or memory_components, not both')
    if not isinstance(components, dict) or set(components) != {'cards', 'hif_abilities', 'gold_factors'}:
        raise ValueError('memory_components requires cards, hif_abilities and gold_factors')
    built, all_ids = {}, set()
    for kind, wrappers in components.items():
        _, rows, _ = resolve_setup_inventory(repository, {'schema_version': INVENTORY_SCHEMA,
                                                         'supports': [], 'memories': wrappers})
        for row in rows:
            if row['id'] in all_ids:
                raise ValueError('Memory component IDs must be unique across component tables')
            all_ids.add(row['id'])
            spec = row['spec']
            if kind == 'cards':
                if spec['produce_card'] is None or spec['ability_ids']:
                    raise ValueError('Card components require a card and no abilities')
                card = spec['produce_card']
                master = repository.card_row_by_upgrade(card['card_id'], card['upgrade_count'])
                if inventory.get('provenance', {}).get('ruleset') == RESEARCH_RULESET:
                    budget = RESEARCH_CARD_BUDGET.get(master['rarity'])
                    slots = len(card['customize_ids']) + int(card['phase_type'] == START_PHASE)
                    if card['upgrade_count'] != 1 or budget is None or slots > budget:
                        raise ValueError(f'Research memory card exceeds customization slot budget: {row["memory_id"]}')
                    if master['rarity'] == 'ProduceCardRarity_Ssr' and card['phase_type'] == START_PHASE:
                        raise ValueError('This research ruleset only supplies SSR memory cards after mid audition')
                row['customization_slots_used'] = len(card['customize_ids']) + int(card['phase_type'] == START_PHASE)
                row['produce_start_slot_used'] = card['phase_type'] == START_PHASE
                row['customization_slot_budget'] = RESEARCH_CARD_BUDGET.get(master['rarity'])
            else:
                if spec['produce_card'] is not None or len(spec['ability_ids']) != 1:
                    raise ValueError('Factor/HIF components require exactly one ability and no card')
                ability = next(r for r in repository.load_table('MemoryAbility').all(spec['ability_ids'][0])
                               if r['level'] == spec['ability_levels'][0])
                skill = next((r for r in repository.load_table('ProduceSkill').all(ability['skillId'])
                              if r['level'] == ability['level']), None)
                if skill is None:
                    raise ValueError('Memory component has no exact ProduceSkill definition')
                hif = 'produce_group-003' in (ability.get('produceGroupIds') or [])
                if kind == 'hif_abilities' and not hif:
                    raise ValueError('HIF component must be a real HIF-scoped ability')
                if kind == 'gold_factors' and (hif or str(skill.get('rarity', '')).rsplit('_', 1)[-1].upper() != 'SR'):
                    raise ValueError('Gold factor must be an ordinary gold/SR ProduceSkill')
        built[kind] = rows
    if not built['cards'] or len({r['spec']['ability_ids'][0] for r in built['gold_factors']}) < 3:
        raise ValueError('Component setup needs a card candidate and at least three gold factors')
    groups = {}
    for row in built['cards']:
        groups.setdefault(row['spec']['produce_card']['card_id'], []).append(row)
    for card_id, rows in groups.items():
        plain = [r for r in rows if not r['spec']['produce_card']['customize_ids']]
        if not plain:
            raise ValueError(f'Each card component family needs an uncustomized representative: {card_id}')
    result['components'] = built
    return result


def legal_setup_options(repository, base_loadout, supports, memories):
    idol = repository.load_table('IdolCard').first(base_loadout['idol_card_id'])
    if idol is None:
        raise ValueError('Setup idol does not exist')
    allowed_plans = {'ProducePlanType_Common', idol['planType']}
    supports = [row for row in supports
                if repository.support_cards.first(row['support_card_id'])['planType'] in allowed_plans]
    if len(supports) < 6:
        raise ValueError('Setup inventory has fewer than six distinct legal supports for this idol')
    legal_memories = []
    for row in memories:
        spec = row['spec']
        if spec['allowed_character_ids'] and idol['characterId'] not in spec['allowed_character_ids']:
            continue
        card = spec['produce_card']
        # Research-scope preference: do not offer cross-plan memory cards.
        # This is not a claim that the game forbids equipping such memories.
        if card and repository.card_row_by_upgrade(card['card_id'], card['upgrade_count'])['planType'] not in allowed_plans:
            continue
        legal_memories.append(row)
    return deepcopy(supports), deepcopy(legal_memories)


def select_setup_loadout(base_loadout, inventory, recorder, repository, *, rules,
                         prepare_observation=None, resolved_catalog=None):
    """Return a full kit and provenance; setup actions use the episode's policy."""
    if prepare_observation is None:
        from ...arena_adapter.setup_observation import prepare_setup_observation
        prepare_observation = prepare_setup_observation
    catalog = resolved_catalog if resolved_catalog is not None else resolve_setup_catalog(repository, inventory)
    supports, memories, digest = catalog['supports'], catalog['memories'], catalog['digest']
    supports, memories = legal_setup_options(repository, base_loadout, supports, memories)
    components = None
    if catalog['components'] is not None:
        components = {kind: legal_setup_options(repository, base_loadout, supports, rows)[1]
                      for kind, rows in catalog['components'].items()}
    selected_supports, selected_memories = [], []
    # The displayed base kit must not reveal a supplied support/memory solution.
    base = deepcopy(base_loadout)
    base.update(auto_support_cards=False, support_card_ids=[], support_card_levels=[],
                support_card_level=None, memories=[])

    def observe(phase, slot, *, options=None, partial=None):
        setup_rules = {
            'support_slots': 6, 'support_owned_slots': 5, 'support_rental_slots': 1,
            'memory_max_slots': 4, 'memory_rental_slots': 0, 'memory_stop_allowed': True,
            'remaining_support_slots': 6-len(selected_supports),
            'remaining_memory_slots': 4-len(selected_memories),
            'memory_gold_factors_per_slot': 3 if components is not None else None,
            'memory_hif_abilities_per_slot_max': 1 if components is not None else None,
            'memory_hif_target_independent_of_carried_card': True,
            'card_identity_is_followed_by_variant_choice': components is not None,
            'research_card_customization_budget': RESEARCH_CARD_BUDGET,
            'produce_start_acquisition_consumes_one_slot': True,
            'cross_plan_memory_candidates': 'excluded_by_research_preference',
            'phase': phase, 'current_slot': slot,
            'research_inventory_provenance': deepcopy(catalog['provenance']),
        }
        shown_selected = deepcopy(selected_memories) + ([deepcopy(partial)] if partial is not None else [])
        return prepare_observation(repository, base_loadout=deepcopy(base),
            support_options=deepcopy(supports if phase == 'support' else selected_supports),
            memory_options=deepcopy(memories if options is None else options),
            selected_supports=deepcopy(selected_supports), selected_memories=shown_selected,
            phase=phase, slot=slot, rules={**deepcopy(rules), 'setup_constraints': setup_rules})

    def pick_component(kind, phase, slot, rows, *, partial=None, extra=None):
        candidates = [{'type': 'select_memory', 'memory_ref': row['id']} for row in rows]
        if extra is not None:
            candidates.append({'type': extra})
        action = recorder.select(kind, observe(phase, slot, options=rows, partial=partial), candidates)
        if action['type'] != 'select_memory':
            return None
        return deepcopy(next(row for row in rows if row['id'] == action['memory_ref']))

    def compose(slot, card, hif, factors, *, final=False):
        spec = deepcopy(card['spec'])
        abilities = [*factors, *([hif] if hif is not None else [])]
        spec['ability_ids'] = [a for row in abilities for a in row['spec']['ability_ids']]
        spec['ability_levels'] = [a for row in abilities for a in row['spec']['ability_levels']]
        content = {k: v for k, v in spec.items() if k != 'memory_id'}
        suffix = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False,
            separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()[:16]
        identity = f'research-composed:{slot}:{suffix}' if final else f'research-partial:{slot}'
        spec['memory_id'] = identity
        return {'id': f'setup:memory:{identity}', 'memory_id': identity, 'spec': spec,
                'borrowed': False, 'assembly_complete': final, 'slot': slot,
                'gold_factors_selected': len(factors), 'hif_ability_selected': hif is not None}

    def choose_component_memories():
        groups = {}
        for row in components['cards']:
            groups.setdefault(row['spec']['produce_card']['card_id'], []).append(row)
        representatives = []
        for rows in groups.values():
            row = deepcopy(next(r for r in rows if not r['spec']['produce_card']['customize_ids']))
            row['variant_count'] = len(rows)
            representatives.append(row)
        for slot in range(4):
            identity = pick_component('setup_memory_card', 'card_identity', slot, representatives,
                                      extra='stop_memory')
            if identity is None:
                break
            variants = groups[identity['spec']['produce_card']['card_id']]
            card = pick_component('setup_memory_card_variant', 'card_variant', slot, variants,
                                  partial=compose(slot, identity, None, []))
            hif = pick_component('setup_memory_hif', 'hif', slot, components['hif_abilities'],
                                 partial=compose(slot, card, None, []), extra='no_hif_ability')
            factors = []
            for _ in range(3):
                used_abilities = {row['spec']['ability_ids'][0] for row in factors}
                options = [row for row in components['gold_factors']
                           if row['spec']['ability_ids'][0] not in used_abilities]
                factor = pick_component('setup_memory_factor', 'factor', slot, options,
                                         partial=compose(slot, card, hif, factors))
                factors.append(factor)
            selected_memories.append(compose(slot, card, hif, factors, final=True))

    def choose_all():
        for slot in range(6):
            chosen_ids = {row['id'] for row in selected_supports}
            candidates = [{'type': 'select_support', 'support_ref': row['id']}
                          for row in supports if row['id'] not in chosen_ids]
            action = recorder.select('setup_support', observe('support', slot), candidates)
            row = deepcopy(next(row for row in supports if row['id'] == action['support_ref']))
            row['borrowed'] = slot == 5  # Research inventory: one source per slot, no duplicate choice.
            selected_supports.append(row)
        if components is not None:
            choose_component_memories()
        else:
            for slot in range(4):
                chosen_ids = {row['id'] for row in selected_memories}
                candidates = [{'type': 'select_memory', 'memory_ref': row['id']}
                              for row in memories if row['id'] not in chosen_ids]
                candidates.append({'type': 'stop_memory'})
                action = recorder.select('setup_memory', observe('memory', slot), candidates)
                if action['type'] == 'stop_memory':
                    break
                row = deepcopy(next(row for row in memories if row['id'] == action['memory_ref']))
                row['borrowed'] = False
                selected_memories.append(row)
        result = deepcopy(base)
        result.update(support_card_ids=[row['support_card_id'] for row in selected_supports],
                      support_card_levels=[row['level'] for row in selected_supports],
                      memories=[deepcopy(row['spec']) for row in selected_memories])
        from gakumas_arena.produce.loadout_handoff import thaw_loadout
        from gakumas_rl.interfaces.service import build_loadout_from_config
        build_loadout_from_config('produce-007', thaw_loadout(result))
        return result, {'mode': 'select', 'inventory_sha256': digest,
            'support_sources': selected_supports, 'memory_sources': selected_memories,
            'support_count': len(selected_supports), 'memory_count': len(selected_memories),
            'ownership_model': 'research-unlimited-supports-five-owned-one-rental;explicit-owned-memory-candidates/1'}
    return recorder.transaction(choose_all)
