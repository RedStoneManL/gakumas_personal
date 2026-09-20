"""Versioned, public relational side-view; the legacy Encoded is never mutated.

The view does not execute rules. Native, cached semantics may be supplied through
``e.relation_context``. Missing native programs remain explicitly unresolved;
opaque DSL is never parsed by string matching. Physical identity is used only for
joins, and arbitrary instance/counter allocator names never enter neural atoms.

Context keys (all optional): card_previews[legacy_entity], program_asts[DSL],
guidance_previews[action_position]={before,after}, effect_groups[legacy_entity]
and schema/native_semantics_version. Index keys may be decimal strings or ints.
This module has no torch, Node, filesystem or RNG dependency on its hot path.
"""
from __future__ import annotations

import copy
import json
import math
from collections import Counter
from dataclasses import dataclass

from round2rl.encoding import Encoded, flatten, PRIVATE_KEYS
from .native_semantics import operator_semantics

SCHEMA = 'arena-relational-sideview/1'
NODE_TYPES = ('global', 'card', 'p_item', 'drink', 'memory', 'program', 'state',
              'event', 'time', 'zone', 'constraint', 'candidate', 'counter')
TYPE_INDEX = {name: i for i, name in enumerate(NODE_TYPES)}
PHASE_NAMES = ('exam', 'drinks', 'draft', 'guidance', 'memory')
PHASE_ORDER = ('draft', 'guidance', 'drinks', 'memory', 'exam')
PROGRAM_FIELDS = ('conditions', 'cost', 'actions', 'effects')
CONTEXT_KEYS = {'schema', 'native_semantics_version', 'card_previews', 'program_asts',
                'guidance_previews', 'effect_groups'}
# These names are exact native state identifiers, not hand-written card ratings.
# Unlisted symbols stay in their AST and are marked unresolved, never guessed.
RESOURCE_NAMES = frozenset('''stamina fixedStamina maxStamina genki fixedGenki
motivation concentration goodConditionTurns goodConditionTurnsUp goodImpression
goodImpressionTurns excellentConditionTurns positiveImpressionTurns score
cardUsesRemaining cardsUsed activeCardsUsed mentalCardsUsed turnCardsUsed
turnsRemaining turnNumber fullPowerCharge enthusiasm preservation stance
costReduction costReductionTurns costIncrease costIncreaseTurns halfCostTurns
doubleCardEffectCards doubleCardEffectTurns nextCardEffectMultiplier
lifeConsumption reductionLifeConsumption vitality block energy'''.split())
CONSTRAINT_FIELDS = frozenset('''capacity minimum_cards max_same_name
support_card_limit support_cards_used support_cards_remaining slots_remaining
cards_still_required current_deck_size counted_deck_size extra_prima_stella_count
memory_capacity memory_slots_remaining p_spent p_remaining free_first_used
free_first_remaining free_guidance_steps_used guided_cards guided_cards_remaining
same_name_count same_name_remaining initial_quantity remaining_quantity supply
max_guidance guidance_count free_card_slots_cost p_cost list_price
min_cards max_cards p_budget free_first_cards max_guided_cards'''.split())


@dataclass(frozen=True)
class Limits:
    entities: int = 8192
    atoms: int = 400000
    edges: int = 100000


def _integer(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value or value < minimum:
        raise ValueError(f'{label} must be an integer >= {minimum}')
    return int(value)


def reconstruct_nodes(encoded):
    """Losslessly rebuild typed public trees, merging later dynamic atom roots.

    Dynamic draft atoms repeat a dictionary's container marker. Reinitializing
    that dictionary would silently erase the static definition, so existing
    compatible containers are retained and only repeated leaves are replaced.
    """
    roots = [None] * encoded.entity_count
    for entity, path, kind, text, number in encoded.atoms:
        entity = _integer(entity, 'entity')
        if entity >= len(roots):
            raise ValueError('atom entity outside declared entities')
        if kind == 0:
            value = {}
        elif kind == 1:
            value = [None] * _integer(number, 'list length')
        elif kind == 2:
            value = None
        elif kind == 3:
            value = bool(number)
        elif kind == 4:
            if not math.isfinite(number):
                raise ValueError('non-finite atom')
            value = int(number) if float(number).is_integer() else float(number)
        elif kind == 5:
            if not text.startswith('value:'):
                raise ValueError('unknown lexical atom representation')
            value = text[len('value:'):]
        else:
            raise ValueError('unknown typed atom kind')
        if not path:
            if isinstance(value, (dict, list)) and isinstance(roots[entity], type(value)):
                continue
            roots[entity] = value
            continue
        parent = roots[entity]
        for offset, component in enumerate(path):
            last = offset == len(path) - 1
            if component.startswith('key:'):
                if not isinstance(parent, dict):
                    raise ValueError('dictionary atom path has no dictionary parent')
                key = component[4:]
            elif component.startswith('index:'):
                if not isinstance(parent, list):
                    raise ValueError('list atom path has no list parent')
                key = _integer(int(component[6:]), 'list index')
                if key >= len(parent):
                    raise ValueError('list atom index exceeds container length')
            else:
                raise ValueError('unknown typed path component')
            if last:
                existing = parent.get(key) if isinstance(parent, dict) else parent[key]
                if isinstance(value, (dict, list)) and isinstance(existing, type(value)):
                    if isinstance(value, list) and len(existing) != len(value):
                        raise ValueError('conflicting duplicate list container')
                else:
                    parent[key] = value
            else:
                parent = parent[key]
    if any(not isinstance(node, dict) for node in roots):
        raise ValueError('every public entity must be a typed dictionary')
    return roots


def _reject_private(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PRIVATE_KEYS or key in {'inventory_seed', 'exam_seed', 'shuffle_seed', 'private_snapshot'}:
                raise ValueError(f'private relational input rejected: {key}')
            _reject_private(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_private(child)


def _get(mapping, index, default=None):
    return mapping.get(str(index), mapping.get(index, default))


def _without_allocators(value):
    if isinstance(value, dict):
        return {key: _without_allocators(child) for key, child in value.items()
                if key not in {'effectInstanceId', 'currentEffectInstanceId'}}
    if isinstance(value, list):
        return [_without_allocators(child) for child in value]
    return value


def _definition(row):
    return row.get('definition', row.get('definition_metadata', {}))


def _card_id(row):
    return row.get('definition_id', _definition(row).get('id'))


def _is_card(row):
    return row.get('entity_type') == 'card' or (row.get('entity_type') == 'candidate' and row.get('action') == 'select_card')


def _identity(domain, value):
    return None if value is None else f'{domain}:{value}'


class _Builder:
    def __init__(self, encoded, limits):
        self.original = encoded
        self.raw = reconstruct_nodes(encoded)
        _reject_private(self.raw)
        self.context = getattr(encoded, 'relation_context', None) or {}
        if not isinstance(self.context, dict) or set(self.context) - CONTEXT_KEYS:
            raise ValueError('unknown relational context fields')
        if self.context.get('schema', SCHEMA) != SCHEMA:
            raise ValueError('unsupported relational context schema')
        _reject_private(self.context)
        self.phase = _integer(getattr(encoded, 'phase', 0), 'phase')
        if self.phase >= len(PHASE_NAMES):
            raise ValueError('unknown relational phase')
        self.phase_name = PHASE_NAMES[self.phase]
        self.limits = limits
        self.nodes, self.types, self.edges = [], [], []
        self.legacy_map, self.resources, self.zones = {}, {}, {}
        self.constraints, self.card_by_definition, self.card_by_base = {}, {}, {}
        self.preview_templates = {}
        self.owned_weights = {}
        self.diagnostics = {'unresolved_programs': 0, 'unresolved_card_semantics': 0,
                            'unresolved_symbols': 0, 'unknown_entity_types': 0}

    def node(self, kind, payload):
        if len(self.nodes) >= self.limits.entities:
            raise ValueError('relational entity capacity exceeded; no truncation allowed')
        if kind not in TYPE_INDEX:
            raise ValueError('unknown relational node type')
        index = len(self.nodes)
        self.nodes.append({'entity_type': kind, **payload})
        self.types.append(TYPE_INDEX[kind])
        return index

    def link(self, source, target, relation, reverse=True):
        if len(self.edges) + (2 if reverse else 1) > self.limits.edges:
            raise ValueError('relational edge capacity exceeded; no truncation allowed')
        self.edges.append((source, target, 'out:' + relation))
        if reverse:
            self.edges.append((target, source, 'in:' + relation))

    def resource(self, name, value=None, known=False, scope='engine_state', owner=None):
        key = (scope, name, owner)
        if key not in self.resources:
            self.resources[key] = self.node('state', {'namespace': scope, 'symbol': name,
                'value_known': known, 'value': copy.deepcopy(value) if known else None})
            if owner is not None:
                self.link(owner, self.resources[key], 'scoped_resource:' + scope)
        elif known:
            self.nodes[self.resources[key]].update(value_known=True, value=copy.deepcopy(value))
        return self.resources[key]

    def zone(self, name):
        if name not in self.zones:
            self.zones[name] = self.node('zone', {'zone': name, 'physical_count': 0})
        return self.zones[name]

    def constraint(self, owner, name, value):
        key = (owner, name)
        if key not in self.constraints:
            self.constraints[key] = self.node('constraint', {'namespace': 'construction',
                'name': name, 'value': copy.deepcopy(value), 'phase': self.phase_name})
            self.link(owner, self.constraints[key], 'subject_to:' + name)
        return self.constraints[key]

    def _normalize_metadata(self, payload, kind):
        """Namespace catalog keys; never treat arbitrary instance names as magnitude."""
        result = copy.deepcopy(payload)
        result.pop('entity_type', None)
        result.pop('instance_id', None)
        for key in ('effectInstanceId', 'currentEffectInstanceId'):
            result.pop(key, None)
        for key in ('definition', 'definition_metadata'):
            if isinstance(result.get(key), dict):
                definition = result[key]
                if 'id' in definition:
                    definition['id'] = _identity(kind + '_definition', definition['id'])
                if 'pIdolId' in definition:
                    definition['pIdolId'] = _identity('idol_definition', definition['pIdolId'])
        for key, domain in (('definition_id', 'card_definition'), ('base_id', 'card_base'),
                            ('target_base_id', 'card_base'), ('target_plus_id', 'card_definition')):
            if key in result:
                result[key] = _identity(domain, result[key])
        return result

    def create_entities(self):
        fixed_counts = Counter(_card_id(row) for row in self.raw
                               if row.get('entity_type') == 'card' and row.get('zone') == 'fixed_pre_opening_deck')
        for legacy, row in enumerate(self.raw):
            original_kind = row.get('entity_type', 'unknown')
            kind = {'memory_ability': 'memory', 'effect': 'event', 'guidance_option': 'program',
                    'mutually_exclusive_card_forms': 'constraint'}.get(original_kind, original_kind)
            if _is_card(row):
                kind = 'card'
            if kind not in TYPE_INDEX:
                kind = 'state'
                self.diagnostics['unknown_entity_types'] += 1
            payload = self._normalize_metadata(row, kind)
            if original_kind != kind:
                payload['source_entity_type'] = original_kind
            # The AST lives in explicit program nodes, never silently discarded.
            for key in ('definition', 'definition_metadata', 'effective'):
                if isinstance(payload.get(key), dict):
                    payload[key] = {k: v for k, v in payload[key].items() if k not in PROGRAM_FIELDS}
            for key in ('effect', 'declaration', 'bindings'):
                payload.pop(key, None)
            if legacy == 0:
                payload.pop('state', None)
                for key in ('memory_abilities', 'persistent_effects', 'configured_abilities'):
                    payload.pop(key, None)
                payload['phase'] = self.phase_name
                payload['phase_order'] = list(PHASE_ORDER)
                payload['sideview_schema'] = SCHEMA
            if kind == 'memory':
                payload['availability'] = 'selected_declaration' if row.get('selected') else ('prospective' if self.phase_name in PHASE_ORDER[:4] else 'not_selected')
            if kind == 'card':
                definition_id = _card_id(row)
                if original_kind == 'candidate':
                    total = _integer(row.get('selected_count', 0), 'candidate total count')
                    selected = total - fixed_counts[definition_id]
                    if selected < 0:
                        raise ValueError('candidate ownership smaller than fixed ownership')
                    payload.update(fixed_physical_count=fixed_counts[definition_id],
                                   policy_selected_count=selected, owned_view_weight=selected)
                    weight = selected
                else:
                    weight = 1
                    payload['owned_view_weight'] = 1
                self.owned_weights[legacy] = weight
                preview = _get(self.context.get('card_previews', {}), legacy)
                if preview is not None and not row.get('temporary_support'):
                    payload['effective_traits'] = copy.deepcopy(preview.get('effective_traits', {}))
                    payload['native_semantics'] = 'compiled'
                elif row.get('effective') is not None:
                    payload['native_semantics'] = 'public_runtime_program_traits_unresolved'
                elif row.get('customizations') or row.get('growth'):
                    payload['native_semantics'] = 'unresolved'
                    self.diagnostics['unresolved_card_semantics'] += 1
                else:
                    payload['native_semantics'] = 'catalog_program'
                if row.get('temporary_support'):
                    payload['temporary_overlay'] = 'public_runtime_effective_program_authoritative'
                index = self.node(kind, payload)
                self.card_by_definition.setdefault(definition_id, []).append(index)
                base = row.get('base_id', (preview or {}).get('base_id', _definition(row).get('baseId')))
                if base is not None:
                    self.card_by_base.setdefault(base, []).append(index)
            else:
                index = self.node(kind, payload)
            self.legacy_map[legacy] = index
        # Keep every original relation, but in a completely independent graph.
        for source, target, label in self.original.edges:
            if source not in self.legacy_map or target not in self.legacy_map:
                raise ValueError('legacy edge outside public entity set')
            self.link(self.legacy_map[source], self.legacy_map[target], 'legacy:' + label, reverse=False)

    def compile_program(self, value):
        if not isinstance(value, str):
            return copy.deepcopy(value), False
        programs = self.context.get('program_asts', {})
        if value in programs:
            return copy.deepcopy(programs[value]), False
        self.diagnostics['unresolved_programs'] += 1
        return {'opaque_dsl': value, 'unresolved': True}, True

    def dependencies(self, ast, statement, owner):
        """Exact syntax dependencies only; no interpretation of unknown calls."""
        def resource_ref(name, relation, scope_owner=None):
            if name in RESOURCE_NAMES or ('engine_state', name, None) in self.resources:
                self.link(statement, self.resource(name), relation)
            elif isinstance(name, str) and name.startswith('g.'):
                self.link(statement, self.resource(name[2:], scope='card_growth', owner=owner), relation)
            elif name == 'cost':
                self.link(statement, self.resource(name, scope='local_program', owner=owner), relation)
            else:
                self.diagnostics['unresolved_symbols'] += 1

        def visit(value):
            if isinstance(value, list):
                for part in value:
                    visit(part)
            elif isinstance(value, dict):
                typ = value.get('type')
                if typ == 'assignment':
                    op = value.get('op', '=')
                    resource_ref(value.get('lhs'), 'writes:' + str(op))
                    if op != '=':
                        resource_ref(value.get('lhs'), 'reads_before_write')
                    implicit = operator_semantics(value.get('lhs'), op)
                    if implicit.get('resolved'):
                        for direction in ('reads', 'writes'):
                            for name in implicit[direction]:
                                scope_owner = None
                                if name.startswith('context.'):
                                    namespace, symbol = 'public_context', name[8:]
                                elif name.startswith('card.'):
                                    namespace, symbol, scope_owner = 'card_runtime', name[5:], owner
                                else:
                                    namespace, symbol = 'engine_state', name
                                target = self.resource(symbol, scope=namespace, owner=scope_owner)
                                self.link(statement, target, 'potential_implicit_' + direction + ':' + implicit['operator'])
                        self.nodes[statement].setdefault('native_resolvers', []).append(implicit['resolver'])
                    else:
                        self.nodes[statement]['implicit_dependencies_unresolved'] = True
                if typ == 'identifier':
                    resource_ref(value.get('name'), 'reads')
                if typ == 'comparison' and value.get('op') == '==':
                    left, right = value.get('left', {}), value.get('right', {})
                    if left.get('type') == 'number':
                        left, right = right, left
                    if left.get('type') == 'identifier' and right.get('type') == 'number':
                        name, number = left.get('name'), right.get('value')
                        targets = self.card_by_base.get(number, []) if name == 'usedCardBaseId' else self.card_by_definition.get(number, []) if name == 'usedCardId' else []
                        for target in targets:
                            self.link(statement, target, 'compares:' + name)
                for part in value.values():
                    if isinstance(part, (dict, list)):
                        visit(part)
        visit(ast)

    def scoped_references(self, ast):
        """Runtime card indices are joins, never general numeric card features."""
        targets = []
        def visit(value):
            if isinstance(value, list):
                return [visit(item) for item in value]
            if not isinstance(value, dict):
                return value
            result = {key: visit(item) for key, item in value.items()}
            if self.phase == 0 and value.get('type') == 'comparison' and value.get('op') in ('==', '!='):
                left_key, right_key = 'left', 'right'
                left, right = value.get(left_key, {}), value.get(right_key, {})
                if left.get('type') == 'number':
                    left_key, right_key, left, right = right_key, left_key, right, left
                number = right.get('value')
                if (left.get('type') == 'identifier' and left.get('name') in ('usedCard', 'lastUsedCard', 'movedCard')
                        and right.get('type') == 'number' and isinstance(number, (int, float))
                        and number >= 0 and int(number) == number):
                    legacy = int(number) + 1
                    if legacy not in self.legacy_map or not _is_card(self.raw[legacy]):
                        raise ValueError('runtime program card reference outside public card map')
                    result[right_key] = {'type': 'reference', 'namespace': 'card_instance'}
                    targets.append((self.legacy_map[legacy], left['name'] + ':' + value['op']))
            return result
        return visit(ast), targets

    def program(self, owner, field, value, scope='native', status='declared'):
        if value is None or value == []:
            return
        ast, opaque = self.compile_program(value)
        block = self.node('program', {'role': 'ordered_block', 'field': field,
            'scope': scope, 'status': status, 'unresolved': opaque})
        self.link(owner, block, 'has_program:' + field)
        statements = ast if isinstance(ast, list) else [ast]
        previous = None
        for position, statement in enumerate(statements):
            stored_statement, referenced_cards = self.scoped_references(statement)
            index = self.node('program', {'role': 'statement', 'field': field, 'scope': scope,
                'position': position, 'statement': stored_statement, 'unresolved': opaque})
            self.link(block, index, 'contains_statement')
            for target, label in referenced_cards:
                self.link(index, target, 'instance_comparison:' + label)
            if previous is not None:
                self.link(previous, index, 'statement_precedes')
            previous = index
            if not opaque:
                self.dependencies(statement, index, owner)
                if isinstance(statement, dict) and statement.get('phase'):
                    event = self.node('event', {'phase': statement['phase'],
                        'scope': scope, 'potential_trigger': status != 'runtime',
                        'limit': statement.get('limit'), 'delay': statement.get('delay'),
                        'ttl': statement.get('ttl'), 'group': statement.get('group')})
                    self.link(index, event, 'trigger_phase')

    def attach_programs(self):
        for legacy, row in enumerate(self.raw):
            owner = self.legacy_map[legacy]
            preview = _get(self.context.get('card_previews', {}), legacy)
            # A public runtime program includes temporary overlays. Never replace
            # it with the cached static card, even when the definition is shared.
            programs = row.get('effective', (preview or {}).get('effective', _definition(row)))
            if isinstance(programs, dict):
                for field in PROGRAM_FIELDS:
                    if field in programs:
                        self.program(owner, field, programs[field], status='runtime' if 'effective' in row else 'declared')
            for declaration in row.get('bindings', []):
                self.program(owner, 'effects', declaration.get('effects'), scope='instance_binding')
            if row.get('declaration') is not None:
                self.program(owner, 'effects', row['declaration'], scope='global_memory')
            if row.get('effect') is not None:
                self.program(owner, 'effects', row['effect'], scope='runtime_trigger', status='runtime')
            # guidance_option nodes are native patch definitions, not executable
            # card programs. Preserve their patch AST and their option role.
            if row.get('entity_type') == 'guidance_option':
                for field in PROGRAM_FIELDS:
                    if field in row:
                        self.program(owner, field, row[field], scope='customization_patch')
        global_row = self.raw[0]
        stage_program = global_row.get('context', {}).get('stage', {}).get('effects')
        if stage_program:
            self.program(self.legacy_map[0], 'effects', stage_program, scope='stage')
        declarations = global_row.get('configured_abilities', global_row)
        represented_memories = {row.get('declaration') for row in self.raw
                                if row.get('entity_type') == 'memory_ability' and row.get('selected')
                                and isinstance(row.get('declaration'), str)}
        for field in ('memory_abilities', 'persistent_effects'):
            for declaration in declarations.get(field, []):
                if field == 'memory_abilities' and isinstance(declaration.get('effects'), str) and declaration['effects'] in represented_memories:
                    continue
                node = self.node('memory' if field == 'memory_abilities' else 'event',
                                 {'availability': 'selected_declaration', 'scope': field})
                self.link(self.legacy_map[0], node, 'configured:' + field)
                self.program(node, 'effects', declaration.get('effects'), scope=field)

    def attach_public_context(self):
        root = self.legacy_map[0]
        global_row = self.raw[0]
        for name, value in global_row.get('state', {}).items():
            resource = self.resource(name, value, True)
            self.link(root, resource, 'public_state')
        resources = global_row.get('resources', {})
        for original, native in (('stamina', 'stamina'), ('max_stamina', 'maxStamina')):
            value = global_row.get(original, resources.get(original))
            if value is not None:
                self.link(root, self.resource(native, value, True), 'public_resource')
        context = global_row.get('context', {})
        task = global_row.get('generalist_task', {})
        for name in ('multipliers', 'turn_types'):
            if context.get(name) is not None:
                self.link(root, self.resource(name, context[name], True, scope='public_context'), 'public_context:' + name)
        if context.get('scoring') is not None and 'multipliers' not in context:
            # Percent scoring values are labelled as such, never silently retyped
            # into the native multiplier vector consumed by a resolver.
            self.link(root, self.resource('scoring', context['scoring'], True, scope='public_context'), 'public_context:scoring')
        turns = context.get('turn_types', task.get('turn_types'))
        if turns is not None:
            values = context.get('scoring', {}).get('values', task.get('score_percents'))
            colors = ('vocal', 'dance', 'visual')
            # Golden TurnManager indexes turn_types with zero-based turnsElapsed.
            # Pre-opening stages have no current turn; do not invent one.
            current = global_row.get('state', {}).get('turnsElapsed')
            if current is not None:
                current = _integer(current, 'public turnsElapsed')
            previous = None
            for position, color in enumerate(turns):
                score = values[colors.index(color)] if isinstance(values, list) and len(values) == 3 and color in colors else None
                node = self.node('time', {'position': position, 'color': color,
                    'score_percent': score, 'public': True, 'current_turn_raw': current,
                    'current_turn_index_base': 0,
                    'relative_position': None if current is None else position - current,
                    'relative_position_unresolved': current is None})
                self.link(root, node, 'public_turn')
                if previous is not None:
                    self.link(previous, node, 'turn_precedes')
                previous = node
        for legacy, row in enumerate(self.raw):
            owner = self.legacy_map[legacy]
            if _is_card(row):
                self.resource('growth', row.get('growth', {}), True, scope='card_runtime', owner=owner)
            for key, value in row.items():
                if key in CONSTRAINT_FIELDS:
                    self.constraint(owner, key, value)
            for budget_name in ('guidance_budget', 'free_rule'):
                for key, value in (row.get(budget_name) or {}).items():
                    self.constraint(owner, budget_name + ':' + key, value)

    def attach_ownership(self):
        root = self.legacy_map[0]
        for legacy, row in enumerate(self.raw):
            if not _is_card(row):
                continue
            owner, weight = self.legacy_map[legacy], self.owned_weights[legacy]
            zone = row.get('zone')
            if isinstance(zone, dict):
                for name in ('hand', 'held', 'deck', 'discarded', 'removed'):
                    if name in zone and zone[name] is not False:
                        target = self.zone(name)
                        self.nodes[target]['physical_count'] += 1
                        self.link(owner, target, 'in_zone:' + name)
            else:
                owned = self.zone('owned_pre_opening_deck')
                if weight:
                    self.nodes[owned]['physical_count'] += weight
                    self.link(owner, owned, 'owned_member')
                if row.get('entity_type') == 'candidate':
                    self.link(owner, self.zone('candidate_pool'), 'available_candidate')
            family = _definition(row).get('name')
            if family is not None:
                if _definition(row).get('upgraded') and family.endswith(('+', '＋')):
                    family = family[:-1]
                # Family names are exact duplicate-limit keys, distinct from base IDs.
                key = ('card_family', family)
                if key not in self.resources:
                    self.resources[key] = self.node('constraint', {'namespace': 'same_name_family',
                        'family': family, 'owned_physical_count': 0})
                target = self.resources[key]
                self.nodes[target]['owned_physical_count'] += weight
                self.link(owner, target, 'same_name_family')
        for zone in self.zones.values():
            self.link(root, zone, 'zone_summary')

    def attach_effect_sources(self):
        pitems = {}
        for legacy, row in enumerate(self.raw):
            if row.get('entity_type') == 'p_item':
                pitems.setdefault(_definition(row).get('id'), []).append(self.legacy_map[legacy])
        groups = {}
        supplied = self.context.get('effect_groups', {})
        for legacy, row in enumerate(self.raw):
            if row.get('entity_type') != 'effect':
                continue
            effect, owner = row.get('effect', {}), self.legacy_map[legacy]
            source = effect.get('source', {}) if isinstance(effect, dict) else {}
            if source.get('type') == 'pItem':
                targets = pitems.get(source.get('id'), [])
                # Duplicate definitions do not identify a source instance uniquely.
                for target in targets:
                    self.link(owner, target, 'source_definition' if len(targets) != 1 else 'source_p_item')
                self.nodes[owner]['source_instance_unresolved'] = len(targets) != 1
            group = _get(supplied, legacy)
            key = ('shared', str(group)) if group is not None else ('unresolved', legacy)
            count = row.get('counter')
            if key not in groups:
                groups[key] = self.node('counter', {'counter_state': copy.deepcopy(count),
                    'shared_identity_known': group is not None})
            elif self.nodes[groups[key]]['counter_state'] != count:
                raise ValueError('shared effect counter has inconsistent public values')
            self.link(owner, groups[key], 'uses_counter')
            self.nodes[owner]['counter_group_known'] = group is not None

    def attach_actions(self):
        actions = []
        if len(self.original.action_entities) != len(self.original.submissions):
            raise ValueError('action/submission cardinality mismatch')
        for position, (legacy, command) in enumerate(zip(self.original.action_entities, self.original.submissions)):
            if legacy not in self.legacy_map:
                raise ValueError('action refers to missing legacy entity')
            # Reference identity is carried by target edges, not arbitrary strings.
            safe_command = {k: copy.deepcopy(v) for k, v in command.items()
                            if k not in {'instance_id', 'candidate_key', 'ability_id', 'decision_version', 'indices', 'action'}}
            if isinstance(command.get('action'), dict):
                safe_command['native_action'] = {k: copy.deepcopy(v) for k, v in command['action'].items()
                                                 if k not in {'instance_id', 'slot', 'decision_version'}}
            if 'indices' in command:
                safe_command['selection_count'] = len(command['indices'])
            action = self.node('candidate', {'role': 'action_query', 'phase': self.phase_name,
                                             'command': safe_command})
            actions.append(action)
            self.link(action, self.legacy_map[legacy], 'action_subject')
            for zone in self.zones.values():
                self.link(action, zone, 'reads_zone_context')
            for (owner, name), constraint in self.constraints.items():
                if owner in (self.legacy_map[0], self.legacy_map[legacy]):
                    self.link(action, constraint, 'reads_constraint:' + name)
            preview = _get(self.context.get('guidance_previews', {}), position)
            if preview is not None:
                for state in ('before', 'after'):
                    item = preview.get(state)
                    if not isinstance(item, dict):
                        raise ValueError('guidance preview requires before and after semantics')
                    # These are semantic templates, not extra owned physical
                    # cards. Paid/free actions and actions on equal templates
                    # may share them; the original target-instance edge remains.
                    key = (state, json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(',', ':')))
                    card = self.preview_templates.get(key)
                    if card is None:
                        card = self.node('card', {'role': 'guidance_' + state,
                            'hypothetical': True, 'identity_scope': 'semantic_template', 'owned_view_weight': 0,
                            'definition_id': _identity('card_definition', item.get('definition_id')),
                            'customizations': copy.deepcopy(item.get('customizations', {})),
                            'growth': copy.deepcopy(item.get('growth', {})),
                            'effective_traits': copy.deepcopy(item.get('effective_traits', {}))})
                        self.preview_templates[key] = card
                        self.resource('growth', item.get('growth', {}), True, scope='card_runtime', owner=card)
                        for field, value in item.get('effective', {}).items():
                            if field in PROGRAM_FIELDS:
                                self.program(card, field, value, scope='guidance_preview', status='hypothetical')
                    self.link(action, card, 'guidance_' + state)
        return actions

    def finish(self):
        self.create_entities()
        self.attach_public_context()
        self.attach_ownership()
        self.attach_programs()
        self.attach_effect_sources()
        actions = self.attach_actions()
        atoms = []
        for entity, node in enumerate(self.nodes):
            for path, kind, text, number in flatten(_without_allocators(node)):
                atoms.append((entity, path, kind, text, number))
                if len(atoms) > self.limits.atoms:
                    raise ValueError('relational atom capacity exceeded; no truncation allowed')
        result = Encoded(atoms, self.edges, len(self.nodes), actions,
                         copy.deepcopy(self.original.submissions))
        result.phase = self.phase
        result.node_types = list(self.types)
        result.relational_schema = SCHEMA
        result.legacy_entity_map = dict(self.legacy_map)
        result.diagnostics = {**self.diagnostics, 'entity_count': len(self.nodes),
                              'atom_count': len(atoms), 'edge_count': len(self.edges)}
        return result


def enhance(encoded, *, limits=None):
    """Return an independent Encoded, preserving action order and legacy inputs."""
    return _Builder(encoded, limits or Limits()).finish()
