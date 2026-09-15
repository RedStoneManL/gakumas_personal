import copy
from collections import Counter
from r1rl.encoding import encode_drinks as base_encode_drinks, encode_exam
from .memory import add_memory_options, ability_node
from .deck_size import counted_size, exempt_count, slot_cost
from .contracts import support_card_count, validate_construction_sources
from .duplicate_limits import family_ids, validate as validate_copy_limit, validate_overrides, family_limit, within_limits
from round2rl.encoding import Encoded, flatten, collate as base_collate, MAX_ATOMS, MAX_ENTITIES

ENCODING = 'arena-generalist-build-exam/3'


class DraftEncoder:
    def __init__(self, entry, catalog, spec):
        self.entry, self.spec = copy.deepcopy(entry), copy.deepcopy(spec)
        self.families = family_ids(catalog)
        self.copy_limit = spec.get('max_same_name')
        self.copy_overrides = validate_overrides(spec.get('max_same_name_overrides'), self.families)
        if self.copy_limit is not None and (type(self.copy_limit) is not int or self.copy_limit < 1):
            raise ValueError('Invalid same-name copy limit')
        self.fixed_family_counts = validate_copy_limit(entry['cards'], self.families, self.copy_limit, self.copy_overrides)
        validate_construction_sources(self.entry['cards'], self.spec)
        self.support_ids = set(spec['support_card_ids'])
        self.support_limit = spec['support_card_limit']
        self.fixed_support_count = support_card_count(self.entry['cards'], spec)
        self.candidates = {r['key']: r for r in spec['candidates']}
        if any(row['card']['definition_id'] in set(spec['banned_card_ids']) for row in self.candidates.values()):
            raise ValueError('banned card in draft candidate pool, including Prima Stella')
        if any(not slot_cost(r['card'],spec) for r in self.candidates.values()):
            raise ValueError('Prima Stella belongs in the unlocked extra fixed-card list, not the ordinary draft pool')
        self.fixed_counted_size = counted_size(entry['cards'],spec)
        self.fixed_exempt_count = exempt_count(entry['cards'],spec)
        self.exclusion_sets = [set(g['candidate_keys']) for g in spec['mutual_exclusions']]
        ids = Counter(c['definition_id'] for c in entry['cards'])
        self.fixed_counts = Counter({r['key']: ids[r['card']['definition_id']] for r in spec['candidates'] if ids[r['card']['definition_id']]})
        self.fixed_keys = set(self.fixed_counts)
        defs = {c['id']: c for c in catalog['cards']}
        customs = {str(c['id']): c for c in catalog['customizations']}
        pitems = {p['id']: p for p in catalog['p_items']}
        nodes = [{'entity_type': 'global', 'phase': 'before_opening_deck_selection',
                  'generalist_task': spec.get('generalist_task', {}),
                  'memory_mode': spec['memory_mode'], 'memory_capacity': spec['memory']['capacity'],
                  'context': entry['context'], 'stamina': entry['resources']['stamina'],
                  'max_stamina': entry['resources']['max_stamina'], 'capacity': spec['max_cards'],
                  'minimum_cards': spec['min_cards'],
                  'max_same_name': self.copy_limit,
                  'support_card_limit': self.support_limit,
                  'deck_size_rule': spec.get('deck_size_rule','all physical cards count'),
                  'extra_prima_stella_count': self.fixed_exempt_count,
                  'memory_abilities': entry['memory_abilities'], 'persistent_effects': entry['persistent_effects'],
                  'guidance_budget': {k: v for k, v in spec['guidance'].items() if k != 'card_rules'}}]
        def payload(card):
            return {'definition': defs[card['definition_id']], 'construction_slot_cost':slot_cost(card,spec),
                    'source_type': 'support' if card['definition_id'] in self.support_ids else 'ordinary',
                    'is_support_card': card['definition_id'] in self.support_ids,
                    'customizations': card['customizations'],
                    'growth': card['growth'], 'bindings': card['bindings'],
                    'customization_definitions': [customs[k] for k in sorted(card['customizations'])]}
        for card in entry['cards']:
            nodes.append({'entity_type': 'card', 'zone': 'fixed_pre_opening_deck', **payload(card)})
        for order, pid in enumerate(entry['p_items']):
            nodes.append({'entity_type': 'p_item', 'resolution_order': order, 'definition': pitems[pid]})
        self.indices = {}
        for key, row in self.candidates.items():
            self.indices[key] = len(nodes)
            rule = spec['guidance']['card_rules'][str(row['card']['definition_id'])]
            nodes.append({'entity_type': 'candidate', 'action': 'select_card', 'supply': row['supply'],
                          'unique': row['unique'],
                          'max_guidance': rule['max_guidance'], **payload(row['card'])})
        self.edges = []
        for group in spec['mutual_exclusions']:
            index = len(nodes)
            nodes.append({'entity_type': 'mutually_exclusive_card_forms',
                          'rule': 'at most one form may appear in the whole deck'})
            for key in group['candidate_keys']:
                self.edges.extend([(index, self.indices[key], 'in:exclusive_form_group'),
                                   (self.indices[key], index, 'out:exclusive_form_group')])
        track_nodes = {}
        for key, row in self.candidates.items():
            rule = spec['guidance']['card_rules'][str(row['card']['definition_id'])]
            for track_id, track in rule['tracks'].items():
                if track_id not in track_nodes:
                    track_nodes[track_id] = len(nodes)
                    nodes.append({'entity_type': 'guidance_option', **track})
                i, j = self.indices[key], track_nodes[track_id]
                self.edges.extend([(j, i, 'in:available_guidance'), (i, j, 'out:available_guidance')])
        self.size_indices = [len(nodes), len(nodes) + 1]
        nodes.extend([{'entity_type': 'candidate', 'action': 'finish_draft'},
                      {'entity_type': 'candidate', 'action': 'continue_draft'}])
        selected_memories = {m['id'] for m in entry['memory_abilities']}
        for memory in spec['memory']['abilities']:
            index = len(nodes)
            nodes.append(ability_node(memory, memory['id'] in selected_memories))
            for key, row in self.candidates.items():
                if row['card']['definition_id'] in (memory['target_base_id'], memory['target_plus_id']):
                    self.edges.extend([(self.indices[key], index, 'in:triggers_memory'), (index, self.indices[key], 'out:trigger_card')])
        # Immutable structural leaves are shared across rollout records. Learned
        # embeddings are recomputed on each update so gradients remain current.
        self.static_atoms = [(i, path, kind, text, number) for i, node in enumerate(nodes)
                             for path, kind, text, number in flatten(node)]
        self.entity_count = len(nodes)
        if self.entity_count > MAX_ENTITIES:
            raise ValueError('draft entity capacity exceeded')
        if len(self.static_atoms) > MAX_ATOMS:
            raise ValueError('draft atom capacity exceeded')

    def support_count(self, selected):
        return self.fixed_support_count + sum(
            self.candidates[key]['card']['definition_id'] in self.support_ids for key in selected)

    def validate_support_selection(self, selected):
        if self.support_count(selected) > self.support_limit:
            raise ValueError('support card total exceeds the physical-copy limit')

    def family_counts(self, selected):
        result = self.fixed_family_counts + Counter(
            self.families[self.candidates[key]['card']['definition_id']] for key in selected)
        if not within_limits(result, self.copy_limit, self.copy_overrides):
            raise ValueError('Same-name construction copy limit exceeded')
        return result

    def legal_commands(self, selected, choose_size=False):
        if len(selected) >= self.spec['max_free_slots'] or not set(selected) <= set(self.candidates):
            raise ValueError('invalid partial draft')
        self.validate_support_selection(selected)
        families = self.family_counts(selected)
        counts = Counter(selected) + self.fixed_counts
        if any(self.candidates[key]['unique'] and count > 1 for key, count in counts.items()):
            raise ValueError('repeated unique card')
        if any(len(group.intersection(counts)) > 1 for group in self.exclusion_sets):
            raise ValueError('mutually exclusive card forms in one deck')
        if choose_size:
            if len(selected) < self.spec['min_free_slots']:
                raise ValueError('cannot decide to finish below the minimum deck size')
            return [{'method': 'finish_draft'}, {'method': 'continue_draft'}]
        blocked = set().union(*(group - set(counts) for group in self.exclusion_sets if group.intersection(counts)))
        return [{'method': 'select_card', 'candidate_key': key} for key, row in self.candidates.items()
                if key not in blocked and (not row['unique'] or not counts[key])
                and (self.copy_limit is None or families[self.families[row['card']['definition_id']]] < family_limit(self.families[row['card']['definition_id']],self.copy_limit,self.copy_overrides))
                and (row['card']['definition_id'] not in self.support_ids
                     or self.support_count(selected) < self.support_limit)]

    def encode(self, selected, choose_size=False):
        commands = self.legal_commands(selected, choose_size)
        counts = Counter(selected) + self.fixed_counts
        families = self.family_counts(selected)
        atoms = list(self.static_atoms)
        for path, kind, text, number in flatten({'slots_remaining': self.spec['max_free_slots'] - len(selected),
                                               'cards_still_required': max(0, self.spec['min_free_slots'] - len(selected)),
                                               'current_deck_size': len(self.entry['cards']) + len(selected),
                                               'counted_deck_size': self.fixed_counted_size + len(selected),
                                               'support_cards_used': self.support_count(selected),
                                               'support_cards_remaining': self.support_limit - self.support_count(selected),
                                               'decision_kind': 'finish_or_continue' if choose_size else 'choose_card'}):
            atoms.append((0, path, kind, text, number))
        for key, index in self.indices.items():
            for path, kind, text, number in flatten({'selected_count': counts[key],
                                                   'same_name_count': families[self.families[self.candidates[key]['card']['definition_id']]],
                                                   'same_name_remaining': None if self.copy_limit is None else family_limit(self.families[self.candidates[key]['card']['definition_id']],self.copy_limit,self.copy_overrides) - families[self.families[self.candidates[key]['card']['definition_id']]],
                                                   'zone': 'pre_opening_deck_and_pool' if counts[key] else 'candidate_pool'}):
                atoms.append((index, path, kind, text, number))
        if len(atoms) > MAX_ATOMS:
            raise ValueError('draft atom capacity exceeded')
        entities = self.size_indices if choose_size else [self.indices[c['candidate_key']] for c in commands]
        e = Encoded(atoms, self.edges, self.entity_count, entities, commands)
        e.phase = 2
        if choose_size:
            e.size_gate_remaining = self.spec['max_free_slots'] - len(selected)
        return e

    def complete(self, selected):
        if not self.spec['min_free_slots'] <= len(selected) <= self.spec['max_free_slots'] or not set(selected) <= set(self.candidates):
            raise ValueError('draft size must satisfy the configured construction bounds')
        self.validate_support_selection(selected)
        self.family_counts(selected)
        counts = Counter(selected)
        totals = counts + self.fixed_counts
        if any(self.candidates[key]['unique'] and count > 1 for key, count in totals.items()):
            raise ValueError('repeated unique card')
        if any(len(group.intersection(totals)) > 1 for group in self.exclusion_sets):
            raise ValueError('mutually exclusive card forms in one deck')
        entry = copy.deepcopy(self.entry)
        # Acquisition order must not become a covert chosen draw order.
        for key in sorted(counts):
            for copy_number in range(1, counts[key] + 1):
                card = copy.deepcopy(self.candidates[key]['card'])
                card['instance_id'] = f'{key}:copy:{copy_number}'
                entry['cards'].append(card)
        if not self.spec['min_cards'] <= counted_size(entry['cards'],self.spec) <= self.spec['max_cards']:
            raise ValueError('wrong final deck size')
        validate_construction_sources(entry['cards'], self.spec)
        validate_copy_limit(entry['cards'], self.families, self.copy_limit, self.copy_overrides)
        return entry


class DraftState:
    """The public size gate precedes each optional extra-card selection."""
    def __init__(self, encoder):
        self.encoder = encoder
        self.selected = []
        self.choose_size = False
        self.done = False
        self.history = []
        self.finish_reason = None

    def commands(self):
        return [] if self.done else self.encoder.legal_commands(self.selected, self.choose_size)

    def encode(self):
        if self.done:
            raise ValueError('draft already complete')
        return self.encoder.encode(self.selected, self.choose_size)

    def apply(self, command):
        if command not in self.commands():
            raise ValueError('illegal draft or deck-size action')
        record = dict(command)
        if command['method'] == 'select_card':
            key = command['candidate_key']
            self.selected.append(key)
            record['instance_id'] = f'{key}:copy:{self.selected.count(key)}'
            self.choose_size = len(self.selected) >= self.encoder.spec['min_free_slots']
            if len(self.selected) == self.encoder.spec['max_free_slots']:
                self.done, self.finish_reason = True, 'maximum'
        elif command['method'] == 'continue_draft':
            self.choose_size = False
        else:
            self.done, self.finish_reason = True, 'policy'
        record['card_count'] = self.encoder.fixed_counted_size + len(self.selected)
        record['physical_card_count'] = len(self.encoder.entry['cards']) + len(self.selected)
        record['exempt_card_count'] = self.encoder.fixed_exempt_count
        self.history.append(record)

    def complete(self):
        if not self.done:
            raise ValueError('draft has not chosen to finish')
        return self.encoder.complete(self.selected)


def encode_guidance(guidance, catalog):
    entry = guidance.entry
    validate_construction_sources(entry['cards'], guidance.spec)
    support_ids = set(guidance.spec['support_card_ids'])
    support_used = support_card_count(entry['cards'], guidance.spec)
    defs = {c['id']: c for c in catalog['cards']}
    pitems = {p['id']: p for p in catalog['p_items']}
    nodes = [{'entity_type': 'global', 'phase': 'before_opening_guidance',
              'generalist_task': guidance.spec.get('generalist_task', {}),
              'support_card_limit': guidance.spec['support_card_limit'],
              'support_cards_used': support_used,
              'support_cards_remaining': guidance.spec['support_card_limit'] - support_used,
              'context': entry['context'], 'resources': {k: v for k, v in entry['resources'].items() if k != 'drinks'},
              'memory_abilities': entry['memory_abilities'], 'persistent_effects': entry['persistent_effects'],
              'free_rule': guidance.rules.get('white_card_free'), **guidance.public_budget()}]
    cards, tracks, edges = {}, {}, []
    for card in entry['cards']:
        cards[card['instance_id']] = len(nodes)
        rule = guidance.rules['card_rules'][str(card['definition_id'])]
        nodes.append({'entity_type': 'card', 'zone': 'pre_opening_deck', 'definition': defs[card['definition_id']],
                      'source_type': 'support' if card['definition_id'] in support_ids else 'ordinary',
                      'is_support_card': card['definition_id'] in support_ids,
                      'customizations': dict(card['customizations']), 'max_guidance': rule['max_guidance'],
                      'guidance_count': sum(card['customizations'].values()), **guidance.card_budget(card),
                      'growth': card['growth'], 'bindings': card['bindings']})
    for order, pid in enumerate(entry['p_items']):
        nodes.append({'entity_type': 'p_item', 'resolution_order': order, 'definition': pitems[pid]})
    for card in entry['cards']:
        rule = guidance.rules['card_rules'][str(card['definition_id'])]
        for key, track in rule['tracks'].items():
            if key not in tracks:
                tracks[key] = len(nodes)
                nodes.append({'entity_type': 'guidance_option', **track})
            i, j = cards[card['instance_id']], tracks[key]
            edges.extend([(j, i, 'in:available_guidance'), (i, j, 'out:available_guidance')])
    commands = guidance.actions()
    action_entities = []
    for command in commands:
        action_entities.append(len(nodes))
        index = len(nodes)
        nodes.append({'entity_type': 'candidate', **{k: v for k, v in command.items() if k != 'instance_id'}})
        if command['method'] == 'guide_card':
            for target, label in ((cards[command['instance_id']], 'target_card'), (tracks[command['customization_id']], 'guidance')):
                edges.extend([(target, index, 'in:' + label), (index, target, 'out:' + label)])
    atoms = [(i, path, kind, text, number) for i, node in enumerate(nodes) for path, kind, text, number in flatten(node)]
    if len(atoms) > MAX_ATOMS or len(nodes) > MAX_ENTITIES:
        raise ValueError('guidance input exceeds explicit capacity')
    e = Encoded(atoms, edges, len(nodes), action_entities, commands)
    e.phase = 3
    by_definition = {}
    for card in entry['cards']:
        by_definition.setdefault(card['definition_id'], []).append(cards[card['instance_id']])
    return add_memory_options(e, entry, guidance.spec, card_nodes=by_definition)


def encode_drinks(entry, selected, catalog, pool, capacity=4, *, spec):
    return add_memory_options(base_encode_drinks(entry, selected, catalog, pool, capacity), entry, spec,
        card_nodes={cid: [i + 1 for i, c in enumerate(entry['cards']) if c['definition_id'] == cid]
                    for cid in {c['definition_id'] for c in entry['cards']}})


def encode_drink_inventory(inventory, entry, catalog, spec):
    """Finite supplies plus public memory availability and prospective effects."""
    return add_memory_options(inventory.encode(entry, catalog), entry, spec,
        card_nodes={cid: [i + 1 for i, c in enumerate(entry['cards']) if c['definition_id'] == cid]
                    for cid in {c['definition_id'] for c in entry['cards']}})


def collate(examples, device='cpu'):
    from .fast_collate import collate as assemble
    return assemble(examples, device)
