"""CPU-only mathematical/evidence contracts; no engine or training launch."""
import copy
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from draftrl.search_supervision import (
    DEFAULT_AUXILIARY_CREDIT, prepare_auxiliary, validate_training_config,
)


def search_config(**overrides):
    return {'execution_mode': 'auxiliary', 'enabled': True, 'require_terminal': True,
            'auxiliary_credit': {**DEFAULT_AUXILIARY_CREDIT, **overrides}}


def record(samples=None, groups=None, peer=0., prior=None):
    samples = samples or [[1., 1., 1., 1.], [4., 4., 4., 4.]]
    groups = groups or [list(range(len(values))) for values in samples]
    actions = [{'pick': i} for i in range(len(samples))]
    union = set(g for values in groups for g in values if g is not None)
    population = max(3, len(union))
    raw = {'actions': actions, 'target_budget_eligible': True, 'root_action_coverage': 1., 'require_terminal': True,
           'root_return_samples': copy.deepcopy(samples), 'root_sample_groups': copy.deepcopy(groups),
           'root_sample_grounded': [[True]*len(values) for values in samples],
           'root_particle_population': {'requested': population, 'distinct': population,
                                        'duplicate': 0, 'ess': float(population)},
           'learning_target': {'prior_policy': prior or [.5]*len(samples)}, 'objective_k': 4}
    return {'encoded': SimpleNamespace(phase=0, submissions=copy.deepcopy(actions)),
            'loss_kind': 'ppo', 'action': 0, 'old_logp': -.5, 'old_value': 1.1,
            'old_return_atoms': [1.]*32, 'return': 2., 'own_terminal_return': 2.,
            'peer_max_return': peer, 'group_marginal_gain': max(2.-peer, 0.),
            'fork_replicas': 4, 'policy_advantage': -3., 'policy_version': 'test:0',
            'search_aux': raw}


def prepare(row, **settings):
    diagnostic = prepare_auxiliary([row], search_config(**settings))
    return row.get('search_aux_target'), diagnostic


class SearchSupervisionTests(unittest.TestCase):
    def test_real_targets_likelihoods_actions_and_raw_evidence_unchanged(self):
        row = record()
        original = copy.deepcopy(row)
        target, diagnostic = prepare(row)
        self.assertEqual(diagnostic['weighted_roots'], 1)
        self.assertGreater(target['target_policy'][1], target['target_policy'][0])
        for key, value in original.items():
            self.assertEqual(row[key], value, key)
        self.assertEqual(target['learning_target']['mode'], 'peer_marginal')
        self.assertFalse(target['learning_target']['independent_heldout_validation'])

    def test_positive_excess_mean_not_per_action_best_four(self):
        row = record([[1.]*4, [0., 0., 0., 2.]])
        target, _ = prepare(row, noise_floor=.00001, uncertainty_multiplier=0.)
        self.assertEqual(target['learning_target']['action_values'], [1., .5])
        self.assertGreater(target['target_policy'][0], target['target_policy'][1])
        # Same root outcomes, but a different REAL peer score reverses the
        # marginal contribution preference. No peer is inserted into the input.
        changed = record([[1.]*4, [0., 0., 0., 2.]], peer=1.)
        other, _ = prepare(changed, noise_floor=.00001, uncertainty_multiplier=0.)
        self.assertEqual(other['learning_target']['action_values'], [0., .25])
        self.assertGreater(other['target_policy'][1], other['target_policy'][0])
        self.assertEqual(changed['encoded'], row['encoded'])

    def test_terminal_mean_retains_posterior_sampling_frequency(self):
        samples = [[0.]*9+[10., 20.], [1., 1., 1.]]
        row = record(samples, [[0]*9+[1, 2], [0, 1, 2]])
        target, _ = prepare(row)
        values = target['learning_target']['action_values']
        self.assertAlmostEqual(values[0], 30./11)
        self.assertNotAlmostEqual(values[0], 10.)  # Wrong equal-cluster measure.
        self.assertEqual(target['learning_target']['distinct_root_particles'], [3, 3])

    def test_repeating_all_clones_cannot_shrink_uncertainty(self):
        row = record([[1., 4., 8., 9.], [4., 7., 8., 15.]])
        other = copy.deepcopy(row)
        for key in ('root_return_samples', 'root_sample_groups', 'root_sample_grounded'):
            other['search_aux'][key] = [values*19 for values in other['search_aux'][key]]
        target, _ = prepare(row)
        repeated, _ = prepare(other)
        for key in ('clustered_delta_noise', 'clustered_action_noise', 'action_values', 'distinct_root_particles'):
            for actual, expected in zip(repeated['learning_target'][key], target['learning_target'][key]):
                self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(repeated['weight'], target['weight'])
        self.assertEqual(repeated['learning_target']['root_exploration_counts'], [76, 76])

    def test_hundreds_of_clones_of_one_particle_are_not_independent_evidence(self):
        row = record([[1.]*100, [9.]*100], [[0]*100, [0]*100])
        target, diagnostic = prepare(row)
        self.assertIsNone(target)
        self.assertEqual(diagnostic['rejected_reasons'], {'insufficient_distinct_root_particles': 1})

    def test_shared_particles_preserve_paired_noise_cancellation(self):
        row = record([[10., 20., 30.], [14., 24., 34.]])
        target, _ = prepare(row)
        self.assertEqual(target['learning_target']['clustered_delta_noise'], [0., 0.])
        self.assertTrue(all(v > 0 for v in target['learning_target']['clustered_action_noise']))
        unpaired = record([[10., 20., 30.], [14., 24., 34.]], [[0, 1, 2], [3, 4, 5]])
        other, _ = prepare(unpaired)
        self.assertTrue(all(v > 0 for v in other['learning_target']['clustered_delta_noise']))

    def test_noisy_small_gap_keeps_prior_and_zero_weight(self):
        row = record([[0., 10., 20.], [10., 20., 0.]], prior=[.9, .1])
        target, _ = prepare(row)
        self.assertEqual(target['target_policy'], [.9, .1])
        self.assertEqual(target['weight'], 0.)

    def test_missing_or_invalid_samples_reject_not_zero_fill(self):
        mutations = [
            lambda raw: raw.pop('root_return_samples'),
            lambda raw: raw['root_return_samples'][0].__setitem__(0, float('nan')),
            lambda raw: raw['root_return_samples'][0].__setitem__(0, True),
            lambda raw: raw['root_return_samples'][0].__setitem__(0, [1.]*32),
            lambda raw: raw['root_sample_groups'][0].pop(),
            lambda raw: raw['root_sample_grounded'][0].__setitem__(0, 1),
            lambda raw: raw.__setitem__('root_action_coverage', .5),
            lambda raw: raw.__setitem__('target_budget_eligible', False),
            lambda raw: raw.__setitem__('actions', list(reversed(raw['actions']))),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                row = record(); mutate(row['search_aux'])
                target, diagnostic = prepare(row)
                self.assertIsNone(target)
                self.assertEqual(diagnostic['rejected_roots'], 1)
                self.assertEqual(row['return'], 2.)

    def test_bootstrap_unknown_identity_or_contract_missing_reject_entire_root(self):
        for kind in ('bootstrap', 'unknown', 'contract'):
            row = record([[1.]*5, [3.]*5])
            if kind == 'bootstrap':
                row['search_aux']['root_return_samples'][0][3] = [900.]*32
                row['search_aux']['root_sample_grounded'][0][3] = False
            elif kind == 'unknown': row['search_aux']['root_sample_groups'][0][4] = None
            else: row['search_aux'].pop('require_terminal')
            target, diagnostic = prepare(row)
            self.assertIsNone(target)
            self.assertEqual(diagnostic['rejected_roots'], 1)

    def test_population_missing_duplicates_or_insufficient_ess_fail_closed(self):
        variants = [None,
                    {'requested': 4, 'distinct': 3, 'duplicate': 1, 'ess': 4.},
                    {'requested': 4, 'distinct': 4, 'duplicate': 0, 'ess': 2.},
                    {'requested': 4, 'distinct': 3, 'duplicate': 0, 'ess': 4.}]
        for population in variants:
            row = record(); row['search_aux']['root_particle_population'] = population
            target, diagnostic = prepare(row)
            self.assertIsNone(target)
            self.assertEqual(diagnostic['rejected_roots'], 1)

    def test_stale_target_removed_when_evidence_no_longer_valid(self):
        row = record(); prepare(row)
        self.assertIn('search_aux_target', row)
        row['search_aux']['root_sample_groups'] = [[None]*4, [None]*4]
        prepare(row)
        self.assertNotIn('search_aux_target', row)
        row['search_aux_target'] = {'stale': True}; row.pop('search_aux')
        prepare(row)
        self.assertNotIn('search_aux_target', row)

    def test_raw_priors_allowed_conflicts_and_zero_support_checked(self):
        row = record(prior=[1., 0.]); row['search_aux']['root_priors'] = [1., 0.]
        target, _ = prepare(row)
        self.assertEqual(target['target_policy'], [1., 0.])
        row['search_aux']['root_priors'] = [.5, .5]
        target, diagnostic = prepare(row)
        self.assertIsNone(target)
        self.assertEqual(diagnostic['rejected_reasons'], {'conflicting_root_priors': 1})

    def test_inconsistent_real_four_game_credit_rejected(self):
        for key, value in [('fork_replicas', 2), ('peer_max_return', 3.),
                           ('own_terminal_return', 4.), ('loss_kind', 'search')]:
            row = record(); row[key] = value
            self.assertIsNone(prepare(row)[0])

    def test_config_validation_is_opt_in_and_legacy_unchanged(self):
        old = {'search': {'learning_target': {'mode': 'prior_advantage'}}}
        self.assertEqual(validate_training_config(old), {'enabled': False})
        row = {'old': 1}
        self.assertFalse(prepare_auxiliary([row], old['search'])['enabled'])
        self.assertEqual(row, {'old': 1})
        config = {'search': search_config(), 'gamma': 1, 'sample_efficiency': {'advantage_mode': 'mc'},
                  'practice': {'forks': {'enabled': True, 'replicas': 4,
                                         'objective': 'best_of_k', 'exam_credit': 'leave_one_out_max'}}}
        self.assertTrue(validate_training_config(config)['enabled'])
        for change in ('terminal', 'replicas', 'gamma', 'mode'):
            invalid = copy.deepcopy(config)
            if change == 'terminal': invalid['search']['require_terminal'] = False
            elif change == 'replicas': invalid['practice']['forks']['replicas'] = 2
            elif change == 'gamma': invalid['gamma'] = .99
            else: invalid['sample_efficiency']['advantage_mode'] = 'gae'
            with self.assertRaises(ValueError): validate_training_config(invalid)

    def test_bad_settings_fail_before_mutation(self):
        row = record(); row['search_aux_target'] = {'existing': True}
        invalid = search_config(min_distinct_particles=2)
        with self.assertRaises(ValueError): prepare_auxiliary([row], invalid)
        self.assertEqual(row['search_aux_target'], {'existing': True})
        for value in (float('nan'), 0., -1., True):
            with self.assertRaises(ValueError): prepare_auxiliary([row], search_config(temperature=value))


if __name__ == '__main__':
    unittest.main()
