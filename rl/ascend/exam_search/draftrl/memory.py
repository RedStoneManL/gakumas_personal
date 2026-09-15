"""Public pre-exam memory choices, with per-exam global ability identity."""
import copy
from round2rl.encoding import Encoded, flatten, MAX_ATOMS, MAX_ENTITIES


def ability_node(row, selected=False):
    return {'entity_type': 'memory_ability', 'target_base_id': row['target_base_id'],
        'target_plus_id': row['target_plus_id'], 'family': row['family'],
        'uses_per_exam': row['uses_per_exam'], 'selected': selected,
        'trigger': 'after_use_of_any_matching_copy', 'remove_zones': ['deck', 'discarded'] if row['family'] == 'remove_sleepiness' else [],
        'declaration': row['declaration']['effects']}


def add_memory_options(encoded, entry, spec, *, card_nodes=None):
    """Expose prospective choices to earlier phases; never expose random state."""
    selected = {r['id'] for r in entry['memory_abilities']}
    atoms, edges = list(encoded.atoms), list(encoded.edges)
    n = encoded.entity_count
    for row in spec['memory']['abilities']:
        atoms.extend((n, p, k, t, v) for p, k, t, v in flatten(ability_node(row, row['id'] in selected)))
        for cid in {row['target_base_id'], row['target_plus_id']}:
            for node in (card_nodes or {}).get(cid, []):
                edges.extend([(node, n, 'in:triggers_memory'), (n, node, 'out:trigger_card')])
        n += 1
    atoms.extend((0, p, k, t, v) for p, k, t, v in flatten({
        'memory_mode': spec['memory_mode'], 'memory_capacity': spec['memory']['capacity'],
        'memory_slots_remaining': spec['memory']['capacity'] - len(selected)}))
    if n > MAX_ENTITIES or len(atoms) > MAX_ATOMS:
        raise ValueError('memory options exceed encoder capacity')
    result = Encoded(atoms, edges, n, encoded.action_entities, encoded.submissions)
    result.phase = encoded.phase
    return result


class MemoryState:
    def __init__(self, entry, catalog, spec):
        self.entry, self.catalog, self.spec = copy.deepcopy(entry), catalog, spec
        self.abilities = {r['id']: r for r in spec['memory']['abilities']}
        self.selected = [r['id'] for r in entry['memory_abilities']]
        self.capacity = spec['memory']['capacity']
        self.mode = spec['memory_mode']
        if self.mode not in ('none', 'hif') or self.capacity != (0 if self.mode == 'none' else 4):
            raise ValueError('invalid public HIF memory availability')
        if self.mode == 'none' and (self.abilities or self.selected):
            raise ValueError('memory-disabled scene contains HIF memory options or declarations')
        if len(self.selected) > self.capacity or len(set(self.selected)) != len(self.selected) or not set(self.selected) <= self.abilities.keys():
            raise ValueError('invalid preset memory abilities')
        self.done = len(self.selected) == self.capacity
        self.history = []

    def commands(self):
        if self.done:
            return []
        return [{'method': 'select_memory', 'ability_id': k} for k in self.abilities if k not in self.selected] + [{'method': 'finish_memory'}]

    def apply(self, command):
        if command not in self.commands():
            raise ValueError('illegal, duplicate, or over-capacity memory selection')
        self.history.append(dict(command))
        if command['method'] == 'finish_memory':
            self.done = True
        else:
            self.selected.append(command['ability_id'])
            self.done = len(self.selected) == self.capacity
        self.entry['memory_abilities'] = [copy.deepcopy(self.abilities[k]['declaration']) for k in sorted(self.selected)]

    def encode(self):
        if self.done:
            raise ValueError('memory selection already finished')
        defs = {r['id']: r for r in self.catalog['cards']}
        customs = {str(r['id']): r for r in self.catalog['customizations']}
        drinks = {r['id']: r for r in self.catalog['drinks']}
        pitems = {r['id']: r for r in self.catalog['p_items']}
        nodes = [{'entity_type': 'global', 'phase': 'before_opening_memory_selection',
            'memory_mode': self.mode, 'memory_capacity': self.capacity,
            'context': self.entry['context'], 'stamina': self.entry['resources']['stamina'],
            'max_stamina': self.entry['resources']['max_stamina'], 'slots_remaining': self.capacity - len(self.selected),
            'capacity': self.capacity, 'persistent_effects': self.entry['persistent_effects']}]
        card_nodes = {}
        for card in self.entry['cards']:
            card_nodes.setdefault(card['definition_id'], []).append(len(nodes))
            nodes.append({'entity_type': 'card', 'zone': 'pre_opening_deck', 'definition': defs[card['definition_id']],
                'customizations': card['customizations'], 'growth': card['growth'], 'bindings': card['bindings'],
                'customization_definitions': [customs[k] for k in sorted(card['customizations'])]})
        for pid in self.entry['p_items']:
            nodes.append({'entity_type': 'p_item', 'definition': pitems[pid]})
        for did in self.entry['resources']['drinks']:
            nodes.append({'entity_type': 'drink', 'definition': drinks[did]})
        edges, indices = [], {}
        for key, row in self.abilities.items():
            index = len(nodes)
            indices[key] = index
            nodes.append(ability_node(row, key in self.selected))
            for cid in (row['target_base_id'], row['target_plus_id']):
                for node in card_nodes.get(cid, []):
                    edges.extend([(node, index, 'in:triggers_memory'), (index, node, 'out:trigger_card')])
        stop = len(nodes)
        nodes.append({'entity_type': 'candidate', 'action': 'finish_memory'})
        commands = self.commands()
        actions = [indices[c['ability_id']] if c['method'] == 'select_memory' else stop for c in commands]
        atoms = [(i, p, k, t, v) for i, node in enumerate(nodes) for p, k, t, v in flatten(node)]
        if len(nodes) > MAX_ENTITIES or len(atoms) > MAX_ATOMS:
            raise ValueError('memory decision capacity exceeded')
        encoded = Encoded(atoms, edges, len(nodes), actions, commands)
        encoded.phase = 4
        return encoded
