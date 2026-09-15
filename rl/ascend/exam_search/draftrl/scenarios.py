"""Balanced, exogenous scenario and coverage constraints, not chosen by policy."""
import copy
from .deck_size import counted_size


def make_scenario(entry, spec, scenario_id, *, coverage_card=None, coverage_memory=None):
    rule = next(s for s in spec['scenarios'] if s['id'] == scenario_id)
    entry, spec = copy.deepcopy(entry), copy.deepcopy(spec)
    for i in range(rule['fixed_sleep']):
        entry['cards'].append({'instance_id': f'scenario:sleep:{i + 1}', 'definition_id': 23,
                              'customizations': {}, 'growth': {}, 'bindings': []})
    if not rule['optional_sleep']:
        spec['candidates'] = [r for r in spec['candidates'] if r['card']['definition_id'] != 23]
    if coverage_memory:
        if spec.get('memory', {}).get('capacity', 0) <= 0:
            raise ValueError('memory coverage cannot run when HIF memory is disabled')
        ability = next(r for r in spec['memory']['abilities'] if r['id'] == coverage_memory)
        coverage_card = ability['target_plus_id']
        entry['memory_abilities'] = [copy.deepcopy(ability['declaration'])]
    if coverage_card is not None:
        row = next(r for r in spec['candidates'] if r['card']['definition_id'] == coverage_card)
        card = copy.deepcopy(row['card'])
        card['instance_id'] = f'coverage:card:{coverage_card}'
        entry['cards'].append(card)
    spec['fixed_cards'] = copy.deepcopy(entry['cards'])
    spec['min_free_slots'] = spec['min_cards'] - counted_size(entry['cards'], spec)
    spec['max_free_slots'] = spec['max_cards'] - counted_size(entry['cards'], spec)
    # Scenario identifiers / seed schedules stay outside neural inputs. Actual
    # mandatory cards and available actions fully describe the public constraint.
    return entry, spec, {'id': rule['id'], 'label': rule['label'], 'fixed_sleep': rule['fixed_sleep'],
        'coverage_card': coverage_card, 'coverage_memory': coverage_memory,
        'coverage': coverage_card is not None or coverage_memory is not None,
        'memory_mode': spec.get('memory_mode', 'hif'),
        'memory_capacity': spec.get('memory', {}).get('capacity', 0)}


def assign(entry, spec, episode_index, *, coverage=False):
    scenario = spec['scenarios'][episode_index % len(spec['scenarios'])]['id']
    block = episode_index // len(spec['scenarios'])
    # A memory-mode pair shares one course. Scheduling coverage on the raw
    # parity would put every coverage event in hif and none in the none mode.
    if spec.get('memory_mode') in ('none', 'hif'):
        block //= 2
    kwargs = {}
    if coverage and block % 4 == 3:
        turn = block // 4
        abilities = (spec.get('memory', {}).get('abilities', [])
                     if spec.get('memory', {}).get('capacity', 0) > 0 else [])
        if turn % 2 and abilities:
            kwargs['coverage_memory'] = abilities[(turn // 2) % len(abilities)]['id']
        else:
            candidates = [r for r in spec['candidates'] if r['card']['definition_id'] != 23]
            if candidates:
                kwargs['coverage_card'] = candidates[(turn // 2) % len(candidates)]['card']['definition_id']
    return make_scenario(entry, spec, scenario, **kwargs)
