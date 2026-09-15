"""Finite public drink offers after the deck and memory loadout are fixed.

Sampling assumptions are experimental, not claims about the game's drop rates.
The inventory RNG is local and never enters policy input or Arena's RNG stream.
"""
from collections import Counter
import random

from round2rl.encoding import Encoded, flatten, MAX_ATOMS, MAX_ENTITIES, PRIVATE_KEYS


class DrinkInventory:
    MODES = {'random', 'missing_favorite', 'coverage', 'low_supply', 'unrestricted'}

    def __init__(self, pool, inventory_seed, mode='random', favorite_id=None,
                 coverage_id=None, capacity=4):
        if not isinstance(capacity, int) or isinstance(capacity, bool) or not 0 <= capacity <= 4:
            raise ValueError('drink capacity must be an integer between zero and four')
        raw_pool = list(pool)
        if not raw_pool or any(not isinstance(d, int) or isinstance(d, bool) or d <= 0 for d in raw_pool):
            raise ValueError('drink pool must contain positive integer definition IDs')
        if mode not in self.MODES:
            raise ValueError('unknown drink supply mode')
        if not isinstance(inventory_seed, int) or isinstance(inventory_seed, bool):
            raise ValueError('inventory_seed must be an integer')
        self.pool = tuple(sorted(set(raw_pool)))
        self.capacity, self.inventory_seed, self.supply_mode = capacity, inventory_seed, mode
        if favorite_id is not None and (type(favorite_id) is not int or favorite_id not in self.pool):
            raise ValueError('favorite drink must be in the legal profile pool')
        if coverage_id is not None and (type(coverage_id) is not int or coverage_id not in self.pool):
            raise ValueError('coverage drink must be in the legal profile pool')
        if mode == 'missing_favorite' and favorite_id is None:
            raise ValueError('missing_favorite mode needs a favorite drink')
        if mode == 'coverage' and (coverage_id is None or capacity == 0):
            raise ValueError('coverage mode needs a legal drink and a nonzero capacity')

        rng = random.Random(inventory_seed)
        eligible = [d for d in self.pool if mode != 'missing_favorite' or d != favorite_id]
        if not eligible:
            raise ValueError('supply has no eligible drink definitions')
        self.preassigned_drinks = [coverage_id] if mode == 'coverage' else []
        if mode == 'unrestricted':
            inventory = Counter({d: 4 for d in self.pool})
        else:
            count = rng.randint(2, 3) if mode == 'low_supply' else rng.randint(6, 8)
            inventory = Counter(self.preassigned_drinks)
            inventory.update(rng.choices(eligible, k=count - len(self.preassigned_drinks)))
        self.initial_inventory = {d: inventory[d] for d in self.pool}
        self.remaining_inventory = dict(self.initial_inventory)
        self.selected = list(self.preassigned_drinks)
        for d in self.selected:
            self.remaining_inventory[d] -= 1
        self.done = len(self.selected) == self.capacity
        self.validate()

    def validate(self):
        """Reject over-capacity, unknown drinks, or an inconsistent finite ledger."""
        if not isinstance(self.done, bool):
            raise ValueError('done must be a boolean')
        if len(self.selected) > self.capacity:
            raise ValueError('selected drinks exceed the four-bottle capacity')
        if any(not isinstance(d, int) or isinstance(d, bool) or d not in self.pool for d in self.selected):
            raise ValueError('selected drink is outside the legal profile pool')
        if self.selected[:len(self.preassigned_drinks)] != self.preassigned_drinks:
            raise ValueError('preassigned drink must be retained')
        if set(self.initial_inventory) != set(self.pool) or set(self.remaining_inventory) != set(self.pool):
            raise ValueError('inventory contains missing or illegal drink definitions')
        selected = Counter(self.selected)
        for d in self.pool:
            initial, remaining = self.initial_inventory[d], self.remaining_inventory[d]
            if any(not isinstance(n, int) or isinstance(n, bool) or n < 0 for n in (initial, remaining)):
                raise ValueError('inventory quantities must be nonnegative integers')
            if initial - remaining != selected[d]:
                raise ValueError('inventory quantities do not match the selected bottles')
        if len(self.selected) == self.capacity and not self.done:
            raise ValueError('selection at capacity must be complete')
        return True

    def commands(self):
        self.validate()
        if self.done:
            return []
        return [{'method': 'select_drink', 'drink_id': d}
                for d in self.pool if self.remaining_inventory[d] > 0] + [{'method': 'finish_drinks'}]

    def apply(self, command):
        if not isinstance(command, dict) or (command.get('method') == 'select_drink' and type(command.get('drink_id')) is not int):
            raise ValueError('drink action requires an integer definition ID')
        if command not in self.commands():
            raise ValueError('illegal, exhausted, or over-capacity drink selection')
        if command['method'] == 'finish_drinks':
            self.done = True
        else:
            d = command['drink_id']
            self.remaining_inventory[d] -= 1
            self.selected.append(d)
            self.done = len(self.selected) == self.capacity
        self.validate()

    def public_summary(self):
        self.validate()
        return {'initial_inventory': {str(d): n for d, n in self.initial_inventory.items()},
                'remaining_inventory': {str(d): n for d, n in self.remaining_inventory.items()},
                'preassigned_drinks': list(self.preassigned_drinks),
                'supply_mode': self.supply_mode, 'inventory_seed': self.inventory_seed,
                'selected': list(self.selected), 'capacity': self.capacity, 'done': self.done}

    def encode(self, entry, catalog):
        """Only the fixed public build and observed finite supply reach the policy.

        entry.resources.drinks must be empty or match this selection; the state
        owns all drinks, including environment-provided coverage bottles.
        Selected memory declarations are encoded verbatim, without future options.
        """
        commands = self.commands()
        if self.done:
            raise ValueError('drink selection already complete')
        if entry['resources'].get('drinks', []) not in ([], self.selected):
            raise ValueError('entry drink loadout conflicts with inventory selection')
        cards = {c['id']: c for c in catalog['cards']}
        customs = {str(c['id']): c for c in catalog['customizations']}
        pitems = {p['id']: p for p in catalog['p_items']}
        drinks = {d['id']: d for d in catalog['drinks']}
        if not set(self.pool) <= set(drinks):
            raise ValueError('legal drink pool contains an unknown catalog definition')
        nodes = [{'entity_type': 'global', 'phase': 'before_opening_drink_selection',
                  'context': entry['context'], 'stamina': entry['resources']['stamina'],
                  'max_stamina': entry['resources']['max_stamina'],
                  'slots_remaining': self.capacity - len(self.selected), 'capacity': self.capacity,
                  'available_bottles': sum(self.remaining_inventory.values()),
                  'memory_abilities': entry['memory_abilities'],
                  'persistent_effects': entry['persistent_effects']}]
        for c in entry['cards']:
            nodes.append({'entity_type': 'card', 'zone': 'pre_opening_deck',
                          'definition': cards[c['definition_id']],
                          'customizations': c['customizations'], 'growth': c['growth'],
                          'bindings': c['bindings'],
                          'customization_definitions': [customs[str(k)] for k in sorted(c['customizations'])]})
        for order, pid in enumerate(entry['p_items']):
            nodes.append({'entity_type': 'p_item', 'resolution_order': order, 'definition': pitems[pid]})
        for d in self.selected:
            nodes.append({'entity_type': 'drink', 'zone': 'selected_loadout', 'definition': drinks[d]})
        indices = {}
        for d in self.pool:
            indices[d] = len(nodes)
            nodes.append({'entity_type': 'candidate', 'action': 'select_drink', 'definition': drinks[d],
                          'initial_quantity': self.initial_inventory[d],
                          'remaining_quantity': self.remaining_inventory[d]})
        finish_index = len(nodes)
        nodes.append({'entity_type': 'candidate', 'action': 'finish_drinks'})
        actions = [indices[c['drink_id']] if c['method'] == 'select_drink' else finish_index for c in commands]

        def reject_private(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    if k in PRIVATE_KEYS or k in {'inventory_seed', 'exam_seed', 'shuffle_seed'}:
                        raise ValueError('private input rejected: ' + k)
                    reject_private(v)
            elif isinstance(value, list):
                for v in value:
                    reject_private(v)
        reject_private(nodes)
        atoms = [(i, path, kind, text, number) for i, node in enumerate(nodes)
                 for path, kind, text, number in flatten(node)]
        if len(nodes) > MAX_ENTITIES or len(atoms) > MAX_ATOMS:
            raise ValueError('finite drink supply exceeds explicit encoder capacity')
        encoded = Encoded(atoms, [], len(nodes), actions, commands)
        encoded.phase = 1
        return encoded
