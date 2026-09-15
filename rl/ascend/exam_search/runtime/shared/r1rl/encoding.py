"""Public pre-opening drink construction, plus unchanged public exam encoding."""
from round2rl.encoding import Encoded, flatten, encode as exam_encode, collate as exam_collate, MAX_ATOMS, MAX_ENTITIES

ENCODING = 'arena-typed-tree-entities-with-drink-prefix/1'


def encode_exam(obs):
    e = exam_encode(obs)
    e.phase = 0
    return e


def encode_drinks(entry, selected, catalog, pool, capacity=4):
    if len(selected) >= capacity or any(d not in pool for d in selected):
        raise ValueError('invalid active drink selection')
    # This function cannot receive an exam, observation, seed, shuffled deck or hand.
    # Definitions and explicit customization layers describe the fixed public deck.
    nodes = [{'entity_type': 'global', 'phase': 'before_opening_drink_selection',
              'context': entry['context'], 'stamina': entry['resources']['stamina'],
              'max_stamina': entry['resources']['max_stamina'],
              'slots_remaining': capacity - len(selected), 'capacity': capacity,
              'memory_abilities': entry['memory_abilities'],
              'persistent_effects': entry['persistent_effects']}]
    definitions = {c['id']: c for c in catalog['cards']}
    customs = {str(c['id']): c for c in catalog['customizations']}
    for c in entry['cards']:
        nodes.append({'entity_type': 'card', 'zone': 'pre_opening_deck',
                      'definition': definitions[c['definition_id']],
                      'customizations': c['customizations'], 'growth': c['growth'],
                      'bindings': c['bindings'],
                      'customization_definitions': [customs[k] for k in sorted(c['customizations'])]})
    p_items = {p['id']: p for p in catalog['p_items']}
    for order, pid in enumerate(entry['p_items']):
        nodes.append({'entity_type': 'p_item', 'resolution_order': order, 'definition': p_items[pid]})
    drink_defs = {d['id']: d for d in catalog['drinks']}
    for d in selected:
        nodes.append({'entity_type': 'drink', 'definition': drink_defs[d]})
    actions, commands = [], []
    for d in pool:
        actions.append(len(nodes))
        commands.append({'method': 'select_drink', 'drink_id': d})
        nodes.append({'entity_type': 'candidate', 'action': 'select_drink', 'definition': drink_defs[d]})
    actions.append(len(nodes))
    commands.append({'method': 'finish_drinks'})
    nodes.append({'entity_type': 'candidate', 'action': 'finish_drinks'})
    atoms = [(i, path, kind, text, num) for i, node in enumerate(nodes)
             for path, kind, text, num in flatten(node)]
    if len(nodes) > MAX_ENTITIES or len(atoms) > MAX_ATOMS:
        raise ValueError('drink prefix exceeds explicit encoder capacity')
    e = Encoded(atoms, [], len(nodes), actions, commands)
    e.phase = 1
    return e


def collate(examples, device='cpu'):
    import torch
    b = exam_collate(examples, device)
    b['drink_phase'] = torch.tensor([e.phase == 1 for e in examples], dtype=torch.bool, device=device)
    return b
