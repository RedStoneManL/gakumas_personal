"""Search evidence and warmup regressions; no model or game training required."""
import copy
import json
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE/'runtime/shared'), str(HERE/'runtime/arena')]
from draftrl.public_mcts import Evaluation, search


class SearchEvidenceTests(unittest.TestCase):
    def assert_aligned(self, result):
        for i, visits in enumerate(result['root_visits']):
            for name in ('root_return_samples', 'root_sample_groups',
                         'root_sample_grounded', 'root_sample_path_ids'):
                self.assertEqual(len(result[name][i]), visits, name)
            self.assertEqual(result['root_terminal_counts'][i],
                             sum(result['root_sample_grounded'][i]))
        self.assertEqual(result['terminal_grounded_simulations'],
                         sum(result['root_terminal_counts']))
        json.dumps(result, allow_nan=False)

    def test_unterminated_action_cannot_starve_other_warmup_actions(self):
        attempted = []
        class World:
            def observe(self): return {'stage': 'root'}
            def step(self, action):
                attempted.append(action)
                return {'stage': 'done' if action == 'fast' else 'long'}
        def evaluate(view):
            if view['stage'] == 'done': return Evaluation([], [], 7., 7.)
            if view['stage'] == 'long': return Evaluation(['continue'], [1.], 9.)
            return Evaluation(['slow', 'fast'], [.999999, .000001], 0.)
        result = search({'stage': 'root'}, World, evaluate, simulations=12,
                        max_depth=1, rollout_steps=0, require_terminal=True,
                        root_selection='soft_budget', learning_target={})
        self.assertEqual(attempted[:4], ['slow', 'fast', 'slow', 'fast'])
        self.assertEqual(result['root_attempts'], [10, 2])
        self.assertEqual(result['root_visits'], [0, 2])
        self.assertEqual(result['root_return_samples'], [[], [7., 7.]])
        self.assertEqual(result['cost']['discarded_unterminated'], 10)
        self.assertEqual(result['root_attempted_action_coverage'], 1.)
        self.assertEqual(result['root_action_coverage'], .5)
        self.assertFalse(result['target_budget_eligible'])
        self.assertIsNone(result['learning_target'])
        self.assert_aligned(result)

    def test_all_success_default_matches_frozen_v6_schedule(self):
        # Captured from f5e64df: successful warmup and the allocator RNG must
        # remain unchanged when no attempt is discarded.
        attempted = []
        class World:
            def observe(self): return {'done': False}
            def step(self, action):
                attempted.append(action)
                return {'done': True, 'score': float(action)}
        def evaluate(view):
            if view['done']: return Evaluation([], [], view['score'], view['score'])
            return Evaluation([0, 1, 2], [.7, .2, .1], 0.)
        result = search({'done': False}, World, evaluate, simulations=18,
                        max_depth=1, rollout_steps=0, root_selection='soft_budget',
                        search_seed=43, objective_k=4, require_terminal=True)
        self.assertEqual(attempted, [1, 0, 2, 1, 0, 2, 2, 1, 0, 2, 1, 2, 2, 0, 1, 2, 2, 1])
        self.assertEqual(result['root_visits'], [4, 6, 8])
        self.assertEqual(result['root_priors'], [.7, .2, .1])
        self.assertEqual(result['root_attempts'], result['root_visits'])
        self.assertEqual(result['selected_action'], 1)
        self.assertEqual(result['target_policy'],
                         [0.20128403120644708, 0.3036942478110875, 0.4950217209824654])
        self.assertEqual(result['continuation_contract']['policy'], 'greedy')
        self.assert_aligned(result)

    def test_unknown_identity_never_becomes_fabricated_independent_groups(self):
        class World:
            def observe(self): return {'done': False}
            def step(self, action): return {'done': True}
        def evaluate(view):
            return Evaluation([], [], 3., 3.) if view['done'] else Evaluation(['a'], [1.], 0.)
        result = search({'done': False}, World, evaluate, simulations=4, max_depth=1)
        self.assertEqual(result['root_sample_groups'], [[None] * 4])
        self.assertEqual(result['root_distinct_particles'], [0])
        self.assertEqual(result['root_unknown_particle_samples'], [4])
        self.assertEqual(result['root_distinct_paths'], [1])
        self.assert_aligned(result)

    def test_particle_group_stays_outside_public_evaluation_and_path_key(self):
        seen = []
        serial = iter([0, 1, 0, 1, 0, 1])
        class World:
            def __init__(self): self.particle_index = next(serial)
            def observe(self): return {'done': False}
            def step(self, action): return {'done': True, 'score': 2.}
        def evaluate(view):
            seen.append(copy.deepcopy(view))
            self.assertNotIn('particle_index', view)
            return Evaluation([], [], 2., 2.) if view['done'] else Evaluation(['a'], [1.], 0.)
        result = search({'done': False}, World, evaluate, simulations=6,
                        max_depth=1, root_selection='soft_budget')
        self.assertEqual(result['root_sample_groups'], [[0, 1, 0, 1, 0, 1]])
        self.assertEqual(result['root_distinct_particles'], [2])
        self.assertEqual(result['root_distinct_paths'], [1])
        self.assertEqual(len(seen), 2)
        self.assert_aligned(result)

    def test_trajectory_identity_does_not_depend_on_tree_rollout_boundary(self):
        class World:
            particle_index = 0
            def __init__(self): self.depth = 0
            def observe(self): return {'depth': self.depth}
            def step(self, action): self.depth += 1; return self.observe()
        def evaluate(view):
            if view['depth'] == 4: return Evaluation([], [], 5., 5.)
            return Evaluation(['next'], [1.], 0.)
        result = search({'depth': 0}, World, evaluate, simulations=6,
                        max_depth=4, rollout_steps=5, root_selection='soft_budget')
        self.assertEqual(result['root_distinct_paths'], [1])
        self.assertEqual(result['root_distinct_particles'], [1])
        self.assertEqual(result['root_terminal_counts'], [6])
        self.assert_aligned(result)

    def test_bootstrapped_atoms_are_preserved_but_never_marked_terminal(self):
        atoms = [0.] * 24 + [100.] * 8
        class World:
            def observe(self): return {'depth': 0}
            def step(self, action): return {'depth': 1}
        def evaluate(view): return Evaluation(['a'], [1.], 25., return_atoms=atoms)
        result = search({'depth': 0}, World, evaluate, simulations=4, max_depth=1,
                        rollout_steps=0, objective_k=4, root_selection='soft_budget')
        self.assertEqual(result['root_return_samples'], [[atoms] * 4])
        self.assertEqual(result['root_sample_grounded'], [[False] * 4])
        self.assertEqual(result['terminal_grounded_simulations'], 0)
        self.assertAlmostEqual(result['root_objective_returns'][0], 100 * (1-.75**4))
        self.assertTrue(result['target_budget_eligible'])  # Historical nonterminal mode.
        self.assert_aligned(result)

    def test_mixed_return_metadata_remains_aligned(self):
        class World:
            def observe(self): return {'kind': 'root'}
            def step(self, action): return {'kind': action}
        def evaluate(view):
            if view['kind'] == 'terminal': return Evaluation([], [], 7., 7.)
            if view['kind'] == 'bootstrap': return Evaluation(['later'], [1.], 2.)
            return Evaluation(['terminal', 'bootstrap'], [.5, .5], 0.)
        result = search({'kind': 'root'}, World, evaluate, simulations=4,
                        max_depth=1, rollout_steps=0, root_selection='soft_budget')
        self.assertEqual(result['root_return_samples'], [[7., 7.], [2., 2.]])
        self.assertEqual(result['root_sample_grounded'], [[True, True], [False, False]])
        self.assertEqual(result['terminal_grounded_simulations'], 2)
        self.assert_aligned(result)

    def test_salvage_keeps_attempt_but_not_failed_return(self):
        counter = [0]
        class World:
            particle_index = 0
            def observe(self): return {'done': False}
            def step(self, action):
                counter[0] += 1
                if counter[0] == 5: raise TimeoutError('test budget')
                return {'done': True}
        def evaluate(view):
            return Evaluation([], [], 1., 1.) if view['done'] else Evaluation(['a', 'b'], [.5, .5], 0.)
        result = search({'done': False}, World, evaluate, simulations=8,
                        max_depth=1, root_selection='soft_budget', require_terminal=True,
                        recoverable=lambda error: isinstance(error, TimeoutError))
        self.assertEqual(sum(result['root_attempts']), 5)
        self.assertEqual(result['root_visits'], [2, 2])
        self.assertEqual(result['truncated_reason'], 'test budget')
        self.assertTrue(result['target_budget_eligible'])
        self.assert_aligned(result)

    def test_temperature_sampling_is_seeded_and_can_discover_greedy_blind_spot(self):
        def run(temperature):
            class World:
                particle_index = 0
                def __init__(self): self.depth = 0; self.actions = []
                def observe(self): return {'depth': self.depth, 'actions': self.actions[:]}
                def step(self, action):
                    self.depth += 1; self.actions.append(action)
                    return self.observe()
            def evaluate(view):
                if view['depth'] == 3:
                    value = 10. if view['actions'][1:] == ['rare', 'rare'] else 0.
                    return Evaluation([], [], value, value)
                if view['depth'] == 0: return Evaluation(['start'], [1.], 0.)
                return Evaluation(['common', 'rare'], [.9, .1], 0.)
            return search({'depth': 0, 'actions': []}, World, evaluate,
                          simulations=128, max_depth=1, rollout_steps=2, require_terminal=True,
                          root_selection='soft_budget', rollout_temperature=temperature, search_seed=151)
        greedy = run(0.)
        sampled = run(2.)
        self.assertEqual(sampled, run(2.))
        self.assertEqual(set(greedy['root_return_samples'][0]), {0.})
        self.assertEqual(set(sampled['root_return_samples'][0]), {0., 10.})
        self.assertGreater(sampled['root_distinct_paths'][0], 1)
        self.assertEqual(sampled['root_distinct_particles'], [1])
        self.assertEqual(greedy['root_attempts'], sampled['root_attempts'])
        self.assert_aligned(sampled)

    def test_new_settings_reject_invalid_values_and_allow_bounded_warmup(self):
        class World:
            def observe(self): return {'done': False}
            def step(self, action): return {'done': True}
        def evaluate(view):
            return Evaluation([], [], 1., 1.) if view['done'] else Evaluation(['a', 'b'], [.5, .5], 0.)
        for value in (-1, math.inf, math.nan, True, '1'):
            with self.subTest(temperature=value), self.assertRaises(ValueError):
                search({'done': False}, World, evaluate, rollout_temperature=value)
        for value in (0, 1, 9, True, 2., '4'):
            with self.subTest(minimum=value), self.assertRaises(ValueError):
                search({'done': False}, World, evaluate, soft_min_visits=value)
        result = search({'done': False}, World, evaluate, simulations=8,
                        root_selection='soft_budget', soft_min_visits=4)
        self.assertEqual(result['root_attempts'], [4, 4])
        self.assert_aligned(result)

    def test_auxiliary_evidence_does_not_require_legacy_learning_target(self):
        from draftrl.search_supervision import DEFAULT_AUXILIARY_CREDIT, prepare_auxiliary
        serial = iter(range(32))
        class World:
            def __init__(self): self.particle_index = next(serial) % 3
            def observe(self): return {'done': False}
            def step(self, action): return {'done': True, 'score': float(action)}
        def evaluate(view):
            if view['done']: return Evaluation([], [], view['score'], view['score'])
            return Evaluation([1, 7], [.5, .5], 0.)
        raw = search({'done': False}, World, evaluate, simulations=16, max_depth=1,
                     root_selection='soft_budget', soft_min_visits=4,
                     objective_k=4, require_terminal=True, learning_target=None)
        raw['root_particle_population'] = {'requested': 3, 'distinct': 3, 'duplicate': 0, 'ess': 3.}
        self.assertIsNone(raw['learning_target'])
        self.assertEqual(raw['root_priors'], [.5, .5])
        row = {'encoded': SimpleNamespace(phase=0, submissions=[1, 7]),
               'loss_kind': 'ppo', 'fork_replicas': 4, 'return': 5.,
               'own_terminal_return': 5., 'peer_max_return': 4., 'group_marginal_gain': 1.,
               'search_aux': raw}
        report = prepare_auxiliary([row], {'execution_mode': 'auxiliary',
            'auxiliary_credit': dict(DEFAULT_AUXILIARY_CREDIT)})
        self.assertEqual(report['accepted_roots'], 1)
        self.assertEqual(report['weighted_roots'], 1)
        self.assertEqual(row['search_aux_target']['learning_target']['action_values'], [0., 3.])
        self.assert_aligned(raw)


class AdapterParticleEvidenceTests(unittest.TestCase):
    def test_sampler_global_diversity_and_slot_provenance_are_separate(self):
        from draftrl import search_adapter
        public_root = {'observation': {'result': {'truncated': False, 'terminated': False}},
                       'partial_selection': [], 'actions': [{'type': 'take'}]}
        allocated = []
        class Native:
            def __init__(self, slot):
                self.slot = slot; self.released = False
                allocated.append(self)
            def observe(self, **kwargs): return copy.deepcopy(public_root)
            def clone(self, **kwargs): return Native(self.slot)
            def step(self, action, **kwargs):
                return {'status': 'terminal', 'view': {
                    'observation': {'result': {'truncated': False, 'terminated': True,
                                               'final_score': 100. + self.slot}},
                    'partial_selection': [], 'actions': []}}
            def release(self): self.released = True
        class Client:
            total_cost = {}
            version = {'fixture': 1}
            def sample_public_worlds(self, *args, **kwargs):
                return {'status': 'ok', 'valid_for_search': True,
                        'worlds': [Native(i) for i in range(4)],
                        'weights': [.25] * 4, 'effective_sample_size': 4.,
                        'distinct_particles': 2, 'duplicate_particles': 2}
        def encode(view):
            self.assertNotIn('particle_index', json.dumps(view))
            return SimpleNamespace(submissions=[{'method': 'act', 'action': {'type': 'take'}}])
        with patch.object(search_adapter, 'encoded_view', encode):
            result = search_adapter.root_search(None, {},
                {'steps': [], 'initial': {'observation': public_root['observation']}},
                score_scale=100., policy_version='test', search_seed=83,
                simulations=12, particles=4, max_depth=1, rollout_steps=0,
                predictor=lambda encoded, deadline: ([1.], 0.), shared_client=Client(),
                root_selection='soft_budget', require_terminal=True, rollout_temperature=1.)
        self.assertTrue(result['valid_training_target'])
        report = result['search']
        self.assertEqual(report['root_particle_population'],
                         {'requested': 4, 'distinct': 2, 'duplicate': 2, 'ess': 4.})
        self.assertEqual(set(report['root_sample_groups'][0]), {0, 1, 2, 3})
        self.assertEqual(report['root_distinct_particles'], [4])  # Slots, not independent hidden states.
        self.assertEqual(report['continuation_contract']['temperature'], 1.)
        self.assertTrue(all(world.released for world in allocated))


if __name__ == '__main__':
    unittest.main()
