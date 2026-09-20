"""Public semantic/identity probes; no simulator, training, CUDA or NPU needed."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'runtime/shared')]

from round2rl.encoding import Encoded, flatten
from draftrl.relational_encoding import (enhance, reconstruct_nodes, Limits,
                                        TYPE_INDEX, SCHEMA, PHASE_ORDER)


def encoded(nodes, actions, submissions=None, phase=2, edges=None):
    atoms = [(i, p, k, t, v) for i, node in enumerate(nodes)
             for p, k, t, v in flatten(node)]
    out = Encoded(atoms, edges or [], len(nodes), list(actions),
                  submissions or [{'method': 'select_card', 'candidate_key': f'option:{i}'} for i in actions])
    out.phase = phase
    return out


def card_definition(card_id=2, actions=None):
    return {'id': card_id, 'name': 'Example+', 'upgraded': True,
            'actions': actions or [], 'conditions': [], 'cost': [], 'effects': []}


def select_card(card_id=2, count=0):
    return {'entity_type': 'candidate', 'action': 'select_card',
            'definition': card_definition(card_id), 'customizations': {},
            'growth': {}, 'bindings': [], 'selected_count': count,
            'zone': 'pre_opening_deck_and_pool' if count else 'candidate_pool'}


class RelationalEncodingTests(unittest.TestCase):
    def test_dynamic_roots_merge_without_losing_static_program(self):
        e = encoded([{'entity_type': 'global', 'capacity': 20}, select_card()], [1])
        for p, k, t, v in flatten({'selected_count': 2, 'zone': 'pre_opening_deck_and_pool'}):
            e.atoms.append((1, p, k, t, v))
        nodes = reconstruct_nodes(e)
        self.assertEqual(nodes[1]['definition']['name'], 'Example+')
        self.assertEqual(nodes[1]['selected_count'], 2)

    def test_legacy_is_unchanged_and_actions_stay_aligned(self):
        e = encoded([{'entity_type': 'global'}, select_card(2), select_card(4)], [2, 1],
                    edges=[(1, 2, 'out:exclusive_form_group')])
        original = copy.deepcopy(e.__dict__)
        side = enhance(e)
        self.assertEqual(e.__dict__, original)
        self.assertEqual(side.submissions, e.submissions)
        self.assertEqual(side.phase, e.phase)
        self.assertEqual(side.relational_schema, SCHEMA)
        self.assertEqual(len(side.node_types), side.entity_count)
        self.assertTrue(all(0 <= value < len(TYPE_INDEX) for value in side.node_types))
        self.assertIn((side.action_entities[0], side.legacy_entity_map[2], 'out:action_subject'), side.edges)

    def test_fixed_coverage_and_candidate_do_not_double_count(self):
        fixed = {'entity_type': 'card', 'zone': 'fixed_pre_opening_deck',
                 'definition': card_definition(), 'customizations': {}, 'bindings': []}
        e = encoded([{'entity_type': 'global'}, fixed, select_card(count=1)], [2])
        rows = reconstruct_nodes(enhance(e))
        self.assertEqual(next(r for r in rows if r.get('zone') == 'owned_pre_opening_deck')['physical_count'], 1)
        self.assertEqual(rows[2]['policy_selected_count'], 0)
        self.assertEqual(next(r for r in rows if r.get('namespace') == 'same_name_family')['owned_physical_count'], 1)
        for p, k, t, v in flatten({'selected_count': 2}):
            e.atoms.append((2, p, k, t, v))
        rows = reconstruct_nodes(enhance(e))
        self.assertEqual(next(r for r in rows if r.get('zone') == 'owned_pre_opening_deck')['physical_count'], 2)

    def test_program_boundaries_and_read_write_scope_are_preserved(self):
        operations = [{'type': 'assignment', 'lhs': 'goodConditionTurns', 'op': '+=',
                       'rhs': {'type': 'number', 'value': 3}},
                      {'type': 'assignment', 'lhs': 'score', 'op': '+=',
                       'rhs': {'type': 'identifier', 'name': 'genki'}}]
        row = select_card(); row['definition']['actions'] = operations
        side = enhance(encoded([{'entity_type': 'global'}, row], [1]))
        rows = reconstruct_nodes(side)
        statements = [r for r in rows if r.get('role') == 'statement']
        self.assertEqual([r['statement'] for r in statements], operations)
        self.assertTrue(any(label == 'out:statement_precedes' for _, _, label in side.edges))
        self.assertTrue(any(label == 'out:reads_before_write' for _, _, label in side.edges))
        self.assertTrue(any(r.get('symbol') == 'genki' and r['value_known'] is False for r in rows))

    def test_opaque_memory_is_unresolved_unless_native_ast_supplied(self):
        dsl = 'at:afterCardUsed[baseId(2)] { drawCard; limit:1 }'
        nodes = [{'entity_type': 'global'}, {'entity_type': 'memory_ability',
                 'selected': False, 'declaration': dsl}]
        e = encoded(nodes, [1], [{'method': 'select_memory', 'ability_id': 'memory:one'}], phase=1)
        side = enhance(e)
        rows = reconstruct_nodes(side)
        self.assertEqual(rows[1]['availability'], 'prospective')
        self.assertEqual(side.diagnostics['unresolved_programs'], 1)
        self.assertFalse(any(r.get('phase') == 'afterCardUsed' for r in rows))
        e.relation_context = {'program_asts': {dsl: [{'phase': 'afterCardUsed', 'limit': 1,
                                                    'actions': [{'type': 'call', 'name': 'drawCard', 'args': []}]}]}}
        side = enhance(e)
        self.assertEqual(side.diagnostics['unresolved_programs'], 0)
        self.assertTrue(any(r.get('phase') == 'afterCardUsed' for r in reconstruct_nodes(side)))

    def test_shared_counter_join_ignores_allocator_names(self):
        effect = {'entity_type': 'effect', 'counter': {'uses': 1}, 'effect':
                  {'phase': 'afterCardUsed', 'limit': 2, 'source': {'type': 'pItem', 'id': 2}}}
        e = encoded([{'entity_type': 'global'}, effect, copy.deepcopy(effect),
                     {'entity_type': 'p_item', 'definition': {'id': 2, 'effects': []}},
                     {'entity_type': 'candidate', 'action': {'type': 'end_turn'}}], [4],
                    [{'method': 'act', 'action': {'type': 'end_turn'}}], phase=0)
        e.relation_context = {'effect_groups': {'1': 'allocator:10000', '2': 'allocator:10000'}}
        side_a = enhance(e)
        e.relation_context['effect_groups'] = {'1': 'renamed', '2': 'renamed'}
        side_b = enhance(e)
        self.assertEqual(side_a.atoms, side_b.atoms)
        self.assertEqual(side_a.edges, side_b.edges)
        self.assertEqual(side_a.node_types.count(TYPE_INDEX['counter']), 1)
        self.assertTrue(any(label == 'out:source_p_item' for _, _, label in side_a.edges))

    def test_runtime_effective_overlay_wins_over_cached_static_program(self):
        runtime = [{'type': 'assignment', 'lhs': 'score', 'op': '+=', 'rhs': {'type': 'number', 'value': 777}}]
        row = {'entity_type': 'card', 'definition_id': 2, 'zone': {'hand': 0},
               'effective': {'actions': runtime}, 'temporary_support': {'active': True}}
        e = encoded([{'entity_type': 'global'}, row], [1], phase=0)
        e.relation_context = {'card_previews': {'1': {'effective': {'actions': []}, 'effective_traits': {'base_trait_should_not_win': True}}}}
        rows = reconstruct_nodes(enhance(e))
        self.assertEqual(next(r['statement'] for r in rows if r.get('role') == 'statement'), runtime[0])
        self.assertIn('temporary_overlay', rows[1])
        self.assertNotIn('effective_traits', rows[1])
        self.assertEqual(next(r for r in rows if r.get('zone') == 'hand')['physical_count'], 1)

    def test_guidance_limit_trait_is_visible_when_ast_does_not_change(self):
        before = {'definition_id': 591, 'effective': {'actions': []},
                  'effective_traits': {'removed_after_use': True, 'effective_limit': 1}}
        after = {**before, 'effective_traits': {'removed_after_use': False, 'effective_limit': 0},
                 'customizations': {'37': 1}}
        e = encoded([{'entity_type': 'global', 'p_remaining': 400},
                     {'entity_type': 'candidate', 'method': 'guide_card'}], [1],
                    [{'method': 'guide_card', 'instance_id': 'arbitrary:44', 'customization_id': '37',
                      'level': 1, 'p_cost': 40, 'free_card_slots_cost': 0}], phase=3)
        e.relation_context = {'guidance_previews': {'0': {'before': before, 'after': after}}}
        rows = reconstruct_nodes(enhance(e))
        previous = next(r for r in rows if r.get('role') == 'guidance_before')
        changed = next(r for r in rows if r.get('role') == 'guidance_after')
        self.assertEqual(previous['effective_traits']['effective_limit'], 1)
        self.assertEqual(changed['effective_traits']['effective_limit'], 0)
        self.assertFalse(any('arbitrary:44' in str(r) for r in rows))

    def test_public_schedule_and_phase_order(self):
        e = encoded([{'entity_type': 'global', 'context': {'turn_types': ['vocal', 'dance', 'visual'],
                           'scoring': {'values': [300, 200, 150]}}}, select_card()], [1])
        rows = reconstruct_nodes(enhance(e))
        self.assertEqual(rows[0]['phase_order'], list(PHASE_ORDER))
        turns = [r for r in rows if r['entity_type'] == 'time']
        self.assertEqual([r['score_percent'] for r in turns], [300, 200, 150])
        self.assertEqual([r['position'] for r in turns], [0, 1, 2])
        for p, k, t, v in flatten({'state': {'turnsElapsed': 1}}):
            e.atoms.append((0, p, k, t, v))
        rows = reconstruct_nodes(enhance(e))
        turns = [r for r in rows if r['entity_type'] == 'time']
        self.assertEqual([r['relative_position'] for r in turns], [-1, 0, 1])
        self.assertTrue(all(r['current_turn_index_base'] == 0 for r in turns))

    def test_nested_allocator_names_do_not_enter_sideview(self):
        e = encoded([{'entity_type': 'global', 'state': {'triggeredEffect':
                      {'effectInstanceId': 1234, 'limit': 2}}}, select_card()], [1])
        first = enhance(e)
        for p, k, t, v in flatten({'state': {'triggeredEffect': {'effectInstanceId': 9999}}}):
            e.atoms.append((0, p, k, t, v))
        second = enhance(e)
        self.assertEqual(first.atoms, second.atoms)
        self.assertFalse(any('effectInstanceId' in str(path) for _, path, _, _, _ in first.atoms))

    def test_native_implicit_dependencies_respect_assignment_operator(self):
        row = select_card()
        row['definition']['actions'] = [
            {'type': 'assignment', 'lhs': 'genki', 'op': '+=', 'rhs': {'type': 'number', 'value': 1}},
            {'type': 'assignment', 'lhs': 'fixedGenki', 'op': '+=', 'rhs': {'type': 'number', 'value': 1}},
            {'type': 'assignment', 'lhs': 'score', 'op': '*=', 'rhs': {'type': 'number', 'value': 2}}]
        side = enhance(encoded([{'entity_type': 'global'}, row], [1]))
        rows = reconstruct_nodes(side)
        statements = [(i, r) for i, r in enumerate(rows) if r.get('role') == 'statement']
        motivation = next(i for i, r in enumerate(rows) if r.get('symbol') == 'motivation')
        self.assertIn((statements[0][0], motivation, 'out:potential_implicit_reads:genki+='), side.edges)
        self.assertNotIn((statements[1][0], motivation, 'out:potential_implicit_reads:fixedGenki+='), side.edges)
        self.assertTrue(statements[2][1]['implicit_dependencies_unresolved'])

    def test_bound_runtime_index_is_a_scoped_join(self):
        effect = {'entity_type': 'effect', 'counter': {}, 'effect': {'phase': 'afterCardUsed',
                  'conditions': [{'type': 'comparison', 'op': '==',
                    'left': {'type': 'identifier', 'name': 'usedCard'},
                    'right': {'type': 'number', 'value': 0}}]}}
        e = encoded([{'entity_type': 'global'}, {'entity_type': 'card', 'definition_id': 2,
                     'zone': {'hand': 0}, 'effective': {}}, effect], [1], phase=0)
        side = enhance(e); rows = reconstruct_nodes(side)
        statement = next(r['statement'] for r in rows if r.get('role') == 'statement')
        self.assertEqual(statement['conditions'][0]['right'], {'type': 'reference', 'namespace': 'card_instance'})
        self.assertTrue(any(dst == side.legacy_entity_map[1] and label == 'out:instance_comparison:usedCard:=='
                            for _, dst, label in side.edges))

    def test_selected_global_memory_is_not_duplicated_as_another_ability(self):
        dsl = 'at:afterCardUsed { drawCard; limit:1 }'
        e = encoded([{'entity_type': 'global', 'memory_abilities': [{'id': 'one', 'effects': dsl, 'counters': {}}]},
                     {'entity_type': 'memory_ability', 'selected': True, 'declaration': dsl}], [1], phase=1)
        side = enhance(e)
        self.assertEqual(side.node_types.count(TYPE_INDEX['memory']), 1)
        self.assertEqual(side.diagnostics['unresolved_programs'], 1)

    def test_explicit_capacity_and_private_guards(self):
        e = encoded([{'entity_type': 'global'}, select_card()], [1])
        with self.assertRaisesRegex(ValueError, 'capacity'):
            enhance(e, limits=Limits(entities=2))
        e.relation_context = {'program_asts': {'some': {'inventory_seed': 55}}}
        with self.assertRaisesRegex(ValueError, 'private'):
            enhance(e)

    def test_concrete_profiles_have_bounded_nonempty_sideviews(self):
        from draftrl.encoding import DraftEncoder
        profiles = json.loads((ROOT / 'setup/profiles.json').read_text(encoding='utf-8'))
        catalog = json.loads((ROOT / 'setup/catalog.json').read_text(encoding='utf-8'))
        for profile in profiles:
            spec = copy.deepcopy(profile['spec']); spec['memory_mode'] = 'hif'
            original = DraftEncoder(profile['entry'], catalog, spec).encode([])
            side = enhance(original)
            self.assertEqual(side.submissions, original.submissions)
            self.assertGreater(side.entity_count, original.entity_count)
            self.assertLess(side.entity_count, Limits().entities)
            self.assertLess(len(side.atoms), Limits().atoms)


if __name__ == '__main__':
    unittest.main()
