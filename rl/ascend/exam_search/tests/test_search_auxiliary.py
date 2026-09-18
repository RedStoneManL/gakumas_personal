"""Auxiliary search must never replace an actual policy sample or duplicate its value loss."""
import copy
import math
import random
import unittest
from collections import Counter
from concurrent.futures import Future
from unittest.mock import patch

import torch
from test_joint_search import DraftPolicy, example, config, groups
from test_signed_learning import credit_rows
from draftrl.search_router import SearchRouter
from draftrl.practice import auxiliary_controller, validate_auxiliary_records, make_fork_tasks, apply_fork_returns
from draftrl.ppo import update, aggregate_auxiliary_diagnostics
from draftrl.bank_rollout import rollout_bank
from draftrl.learning_settings import SIGNED
from draftrl.search_supervision import DEFAULT_AUXILIARY_CREDIT


def router_config(mode='auxiliary'):
    return {'execution_mode': mode, 'parallel_roots': 1, 'inference_batch': 2,
            'trajectory_every': 1, 'simulations': 16, 'particles': 4, 'seconds': 10,
            'sampling_ms': 1000, 'max_depth': 4, 'rollout_steps': 4, 'seed_base': 71}


def result_for(e):
    return {'valid_training_target': True, 'status': 'ok', 'elapsed_seconds': .01,
            'search_version': 'test', 'search_seed': 72,
            'search': {'actions': copy.deepcopy(e.submissions),
                       'selected_action': e.submissions[1], 'target_policy': [.1, .9],
                       'target_budget_eligible': True, 'root_action_coverage': 1.,
                       'cost': {'terminal_evaluations': 16, 'bootstrap_evaluations': 0}}}


def item_for(e):
    return {'encoded': e, 'profile': 'same', 'episode_id': 'joint:1', 'worker': 0,
            'enabled': True, 'entry': {}, 'observation': {'decision_version': 1},
            'partial_selection': [], 'score_scale': 1.}


def labelled_rows(model):
    rows = credit_rows(model)
    controller = auxiliary_controller({'search': {'execution_mode': 'auxiliary'}})
    for row in rows:
        row['controller_contract'] = copy.deepcopy(controller)
    row = rows[0]
    raw = result_for(row['encoded'])['search']
    raw.update(root_visits=[4, 4], root_return_samples=[[0.] * 4, [20.] * 4],
               root_sample_groups=[[0, 1, 2, 3], [0, 1, 2, 3]],
               root_sample_grounded=[[True] * 4, [True] * 4], require_terminal=True,
               learning_target={'prior_policy': [.5, .5]}, behavior_policy=[.5, .5],
               root_particle_population={'requested': 4, 'distinct': 4, 'duplicate': 0, 'ess': 4.})
    row['search_aux'] = raw
    return rows


class AuxiliaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def test_success_preserves_policy_action_probability_and_record_kind(self):
        e = example(0)
        with patch('draftrl.search_router.SearchService'):
            router = SearchRouter(None, 'cpu', router_config())
        payload = result_for(e)
        before = copy.deepcopy(payload)
        action, logp, extra = router.finish(item_for(e), payload, 0, -.75)
        self.assertEqual((action, logp, extra['loss_kind']), (0, -.75, 'ppo'))
        self.assertIn('search_aux', extra)
        self.assertNotIn('search', extra)
        self.assertNotIn('diagnostic_distribution', extra)
        self.assertEqual(payload, before)
        self.assertEqual(router.counts['auxiliary_targets'], 1)

    def test_legacy_default_still_takes_search_action_without_fake_probability(self):
        e = example(0)
        cfg = router_config(); cfg.pop('execution_mode')
        with patch('draftrl.search_router.SearchService'):
            router = SearchRouter(None, 'cpu', cfg)
        action, logp, extra = router.finish(item_for(e), result_for(e), 0, -.75)
        self.assertEqual((action, logp, extra['loss_kind']), (1, None, 'search'))
        self.assertNotIn('search_aux', extra)

    def test_failed_auxiliary_search_remains_real_policy_only(self):
        with patch('draftrl.search_router.SearchService'):
            router = SearchRouter(None, 'cpu', router_config())
        result = {'valid_training_target': False, 'status': 'deadline', 'elapsed_seconds': .1}
        action, logp, extra = router.finish(item_for(example(0)), result, 0, -.75)
        self.assertEqual((action, logp), (0, -.75))
        self.assertEqual(extra, {'loss_kind': 'ppo', 'search_fallback_reason': 'deadline'})

    def test_minimum_visits_budget_is_checked_before_opening_a_root(self):
        cfg = router_config(); cfg.update(soft_min_visits=4, simulations=7)
        with patch('draftrl.search_router.SearchService'):
            router = SearchRouter(None, 'cpu', cfg)
        tasks, positions, extras = router.prepare(None, [item_for(example(0))], 'x')
        self.assertEqual((tasks, positions), ([], []))
        self.assertEqual(extras[0]['search_fallback_reason'], 'insufficient_search_budget')
        for bad in (True, 1, 9, 3.5):
            with self.assertRaises(ValueError), patch('draftrl.search_router.SearchService'):
                SearchRouter(None, 'cpu', {**cfg, 'soft_min_visits': bad})

    def test_action_order_mismatch_and_mixed_behavior_rejected(self):
        e = example(0)
        with patch('draftrl.search_router.SearchService'):
            router = SearchRouter(None, 'cpu', router_config())
        payload = result_for(e); payload['search']['actions'].reverse()
        with self.assertRaises(ValueError):
            router.finish(item_for(e), payload, 0, -.75)
        cfg = {'search': {'execution_mode': 'auxiliary'}}
        row = {'loss_kind': 'ppo', 'old_logp': -.5, 'controller_contract': auxiliary_controller(cfg)}
        validate_auxiliary_records([row], cfg)
        for change in ({'old_logp': None}, {'loss_kind': 'search'}, {'controller_contract': None}, {'search': {}}):
            with self.assertRaises(ValueError):
                validate_auxiliary_records([{**row, **change}], cfg)
        with self.assertRaises(ValueError):
            validate_auxiliary_records([{**row, 'search_aux': {}}], {'search': {}})

    def test_four_branches_share_controller_even_when_only_parent_has_shadow_search(self):
        cfg = {'search': {'execution_mode': 'auxiliary', 'fork_episodes': False},
               'practice': {'forks': {'enabled': True, 'replicas': 4, 'every_n_per_profile': 1}},
               '_policy_version': 'x', '_profiles': [{}], 'train_seed_base': 100}
        parent = {'seed': 100, 'profile': 'test', 'sampling_source': 'joint', 'policy_version': 'x',
                  'normalized_score': 2., 'action_rng_seed': 200, 'score': 2., 'entry': {'cards': []},
                  'entry_sha256': 'same', 'score_scale': 1., 'search_enabled': True,
                  'controller_contract': auxiliary_controller(cfg)}
        tasks, next_seed = make_fork_tasks([parent], cfg, 101)
        self.assertEqual(next_seed, 104)
        self.assertEqual(len(tasks), 3)
        self.assertTrue(all(t['metadata']['search_enabled'] is False for t in tasks))
        self.assertTrue(all(t['metadata']['controller_contract'] == parent['controller_contract'] for t in tasks))
        branches = [{**parent, 'seed': 100+i, 'action_rng_seed': 200+i, 'prefix_id': 'joint:100',
                     'branch_id': i, 'fork_replicas': 4, 'normalized_score': 3.*i} for i in range(1, 4)]
        rows = [{'encoded': example(2), 'episode_id': 'joint:100', 'return': 2.}]
        apply_fork_returns(rows, [parent], [], branches, objective='best_of_k')
        self.assertEqual(rows[0]['return'], 9.)
        for member in (parent, branches[0]):
            old = member.pop('controller_contract')
            before = rows[0]['return']
            with self.assertRaises(ValueError):
                apply_fork_returns(rows, [parent], [], branches, objective='best_of_k')
            self.assertEqual(rows[0]['return'], before)
            member['controller_contract'] = old

    def test_auxiliary_zero_coefficient_preserves_exact_ppo_and_single_critic_update(self):
        torch.manual_seed(81)
        model = DraftPolicy(width=16, lexical=8, quantiles=32)
        baseline = copy.deepcopy(model)
        rows = labelled_rows(model)
        plain = copy.deepcopy(rows); plain[0].pop('search_aux')
        raw_before = copy.deepcopy(rows[0]['search_aux'])
        cfg = config(); cfg['signed_exam_credit'] = SIGNED
        cfg['search'].update(execution_mode='auxiliary', loss_coefficient=0.)
        cfg['search']['auxiliary_credit'] = copy.deepcopy(DEFAULT_AUXILIARY_CREDIT)
        def run(m, records):
            random.seed(517)
            optimizer = groups(m, dict.fromkeys(('exam', 'drink', 'draft', 'guidance', 'memory'), .0001))
            return update(m, optimizer, records, cfg, 'cpu')
        result = run(model, rows); reference = run(baseline, plain)
        self.assertEqual(len(rows), 4)
        self.assertEqual(result['ppo_records'], 4)
        self.assertEqual(result['search_records'], 0)
        self.assertEqual(result['auxiliary_search_records'], 1)
        self.assertGreater(result['search_loss'], 0.)
        self.assertEqual(result['value_loss'], reference['value_loss'])
        self.assertEqual(result['policy_loss'], reference['policy_loss'])
        self.assertEqual(rows[0]['search_aux'], raw_before)
        for key, value in model.state_dict().items():
            torch.testing.assert_close(value, baseline.state_dict()[key], rtol=0, atol=0)

    def test_auxiliary_label_keeps_its_real_ppo_credit_and_changes_actor(self):
        torch.manual_seed(82)
        model = DraftPolicy(width=16, lexical=8, quantiles=32)
        baseline = copy.deepcopy(model)
        rows = labelled_rows(model); plain = copy.deepcopy(rows); plain[0].pop('search_aux')
        cfg = config(); cfg['signed_exam_credit'] = SIGNED
        cfg['search'].update(execution_mode='auxiliary', loss_coefficient=.1)
        cfg['search']['auxiliary_credit'] = copy.deepcopy(DEFAULT_AUXILIARY_CREDIT)
        for m, data in ((model, rows), (baseline, plain)):
            random.seed(10)
            update(m, groups(m, dict.fromkeys(('exam', 'drink', 'draft', 'guidance', 'memory'), .0001)), data, cfg, 'cpu')
        self.assertEqual(rows[0]['loss_kind'], 'ppo')
        self.assertIsNotNone(rows[0]['old_logp'])
        self.assertLess(rows[0]['policy_advantage'], 0.)
        self.assertEqual(rows[0]['return'], 1.)
        self.assertTrue(any(not torch.equal(v, baseline.state_dict()[k]) for k, v in model.state_dict().items()
                            if k.startswith('actor.')))

    def test_bank_real_trace_is_identical_with_shadow_search_on_or_off(self):
        e = example(0)
        class Service:
            def __init__(self, *args, **kwargs):
                self.stats = Counter(); self.pending = set()
            def submit(self, tasks):
                futures = []
                for task in tasks:
                    future = Future(); future.set_result(result_for(e)); futures.append(future); self.pending.add(future)
                return futures
            def pump(self, **kwargs): pass
            def take(self, future):
                self.pending.remove(future); return future.result()
        class Pool:
            def __init__(self): self.steps = 0; self.score = 0; self.commands = []
            def send(self, worker, method, payload):
                if method == 'reset': self.steps = 0; self.score = 0
                else:
                    self.commands.append(copy.deepcopy(payload)); self.steps += 1; self.score += payload['pick']
            def observation(self):
                return {'decision_version': self.steps, 'result': {'terminated': self.steps == 3,
                    'truncated': False, 'final_score': self.score if self.steps == 3 else None},
                    'context': {'turn_types': ['vocal']}, 'zones': {'removed': []},
                    'state': {'turnsElapsed': self.steps, 'stamina': 30}}
            def receive(self, worker): return {'observation': self.observation(), 'encoded': e}
            def public_history(self, worker): return {'initial': {'observation': self.observation()}, 'steps': []}
        def choose(model, examples, device, greedy, driver, rngs, exploration, **kwargs):
            actions = [int(rng.random() >= .5) for rng in rngs]
            return actions, [math.log(.5)]*len(actions), [0.]*len(actions), [{} for _ in actions], [{} for _ in actions]
        cfg = {'search': router_config(), 'workers': 1, '_policy_version': 'x:1', 'max_episode_decisions': 10}
        meta = {'profile': 'test', 'plan': 'logic', 'course_id': 'test', 'drink_capacity': 0,
                'memory_mode': 'none', 'memory_capacity': 0, 'condition_cell': 'test', 'score_scale': 1.,
                'search_enabled': True, 'controller_contract': auxiliary_controller(cfg)}
        task = {'entry': {'cards': []}, 'metadata': meta, 'key': 'x', 'replay_seed': 12}
        with patch('draftrl.bank_rollout.keycard_focus.tracker', return_value={}), \
             patch('draftrl.bank_rollout.keycard_focus.observe'), \
             patch('draftrl.bank_rollout.keycard_focus.finish', return_value={}), \
             patch('draftrl.search_router.SearchService', Service):
            plain_pool = Pool(); plain, plain_summary, _ = rollout_bank(plain_pool, None, None, cfg, 'cpu', 1, None, choose, tasks=[task])
            router = SearchRouter(None, 'cpu', router_config())
            aux_pool = Pool(); aux, aux_summary, _ = rollout_bank(aux_pool, None, None, {**cfg, '_search_router': router}, 'cpu', 1, None, choose, tasks=[task])
        self.assertEqual(plain_pool.commands, aux_pool.commands)
        self.assertEqual(plain_summary, aux_summary)
        self.assertEqual(len(aux), 3)
        for left, right in zip(plain, aux):
            self.assertIn('search_aux', right)
            for key in ('action', 'old_logp', 'return', 'loss_kind', 'controller_contract'):
                self.assertEqual(left[key], right[key])

    def test_auxiliary_diagnostics_use_global_counts_and_weighted_mean(self):
        local = {'enabled': True, 'roots': 2, 'accepted_roots': 1, 'weighted_roots': 1,
                 'rejected_roots': 1, 'exploration_samples': 8, 'distinct_particle_action_pairs': 8,
                 'mean_weight': .25, 'rejected_reasons': {'left': 1}}
        remote = {'roots': 3, 'accepted_roots': 2, 'weighted_roots': 2, 'rejected_roots': 1,
                  'exploration_samples': 16, 'distinct_particle_action_pairs': 16, 'weight_sum': 1.5}
        class Mesh:
            size = 2
            def gather_lists(self, values): return list(values) + ['right']
            def sum_values(self, values):
                other = remote if 'roots' in values else {'right': 1}
                return {key: value + other.get(key, 0) for key, value in values.items()}
        result = aggregate_auxiliary_diagnostics(local, Mesh())
        self.assertEqual(result['roots'], 5)
        self.assertEqual(result['accepted_roots'], 3)
        self.assertAlmostEqual(result['mean_weight'], 1.75/3)
        self.assertEqual(result['rejected_reasons'], {'left': 1., 'right': 1.})
        self.assertEqual(local['roots'], 2)


if __name__ == '__main__':
    unittest.main()
