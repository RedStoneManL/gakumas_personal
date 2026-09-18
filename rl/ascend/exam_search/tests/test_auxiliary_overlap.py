"""Auxiliary overlap preserves record identity, policy behavior, and bounded queues."""
from collections import Counter
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import patch
import copy
import unittest

from draftrl.async_decisions import AsyncDecisions
from draftrl.search_router import SearchRouter


class ManualService:
    def __init__(self, *args, **kwargs):
        self.pending, self.stats = set(), Counter()
        self.futures = []

    def submit(self, tasks):
        futures = [Future() for task in tasks]
        self.pending.update(futures)
        self.futures.extend(futures)
        return futures

    def pump(self, **kwargs):
        pass

    def take(self, future):
        self.pending.remove(future)
        return future.result()


class AuxiliaryOverlapTests(unittest.TestCase):
    def setup_flow(self, capacity=2, asynchronous=True):
        cfg = dict(execution_mode='auxiliary', auxiliary_async=asynchronous,
                   parallel_roots=capacity, inference_batch=capacity,
                   trajectory_every=1, simulations=16, particles=4, seconds=10,
                   sampling_ms=2000, max_depth=8, rollout_steps=8, seed_base=731,
                   max_roots_per_episode=2, soft_min_visits=4)
        with patch('draftrl.search_router.SearchService', ManualService):
            router = SearchRouter(None, 'cpu', cfg)
        observation = {'decision_version': 1}
        class Pool:
            def public_history(self, worker):
                return {'initial': {'observation': copy.deepcopy(observation)}, 'steps': []}
        encoded = SimpleNamespace(submissions=[{'pick': 0}, {'pick': 1}])
        def decision(worker, episode):
            item = dict(worker=worker, encoded=encoded, enabled=True, entry={},
                        observation=copy.deepcopy(observation), profile='same', score_scale=1.,
                        episode_id=episode, partial_selection=[])
            return item, (worker, encoded, 1, -.75, 2., {}, {})
        return router, AsyncDecisions(router), Pool(), decision

    def bind_ready(self, flow, ready):
        records = []
        for row in ready:
            record = dict(action=row[2], old_logp=row[3], old_value=row[4], **row[-1])
            flow.bind(record, row[-1])
            records.append(record)
        return records

    def result(self, item, seed, valid=True):
        return dict(valid_training_target=valid, status='ok' if valid else 'deadline',
                    elapsed_seconds=.1, search_seed=seed, search_version='fixture',
                    search={'actions': item['encoded'].submissions, 'marker': seed,
                            'selected_action': {'pick': 0},
                            'cost': dict(terminal_evaluations=8, bootstrap_evaluations=0)})

    def test_actions_advance_and_late_results_bind_to_original_reused_worker(self):
        router, flow, pool, decision = self.setup_flow()
        item, proposal = decision(0, 'episode-1')
        ready = flow.submit(pool, [item], [proposal], 'weights:1')
        first = self.bind_ready(flow, ready)[0]
        self.assertFalse(flow.pending)
        self.assertEqual((first['action'], first['old_logp']), (1, -.75))
        item2, proposal2 = decision(0, 'episode-2')
        second = self.bind_ready(flow, flow.submit(pool, [item2], [proposal2], 'weights:1'))[0]
        router.service.futures[1].set_result(self.result(item2, 22))
        self.assertEqual(flow.poll(), [])
        self.assertNotIn('search_aux', first)
        self.assertEqual(second['search_aux']['marker'], 22)
        with self.assertRaisesRegex(RuntimeError, 'boundary'):
            flow.assert_drained()
        router.service.futures[0].set_result(self.result(item, 11))
        flow.drain()
        self.assertEqual(first['search_aux']['marker'], 11)
        for record in (first, second):
            self.assertEqual((record['action'], record['old_logp'], record['old_value'], record['loss_kind']),
                             (1, -.75, 2., 'ppo'))
        self.assertEqual(router.service.stats['peak_auxiliary_roots'], 2)

    def test_backpressure_does_not_stall_behavior_or_consume_root_budget(self):
        router, flow, pool, decision = self.setup_flow(capacity=1)
        item, proposal = decision(0, 'first')
        first = self.bind_ready(flow, flow.submit(pool, [item], [proposal], 'weights:1'))[0]
        other, next_proposal = decision(0, 'next')
        record = self.bind_ready(flow, flow.submit(pool, [other], [next_proposal], 'weights:1'))[0]
        self.assertEqual(record['search_skipped_reason'], 'auxiliary_backpressure')
        self.assertEqual(router.counter, 1)
        self.assertEqual(router.episode_roots['next'], 0)
        self.assertEqual(len(router.service.pending), 1)
        router.service.futures[0].set_result(self.result(item, 1, valid=False))
        flow.drain()
        self.assertEqual(first['search_fallback_reason'], 'deadline')
        self.assertEqual(first['old_logp'], -.75)
        self.assertEqual(router.counts['auxiliary_backpressure_skips'], 1)

    def test_unbound_record_and_wrong_record_are_rejected(self):
        router, flow, pool, decision = self.setup_flow()
        item, proposal = decision(0, 'first')
        ready = flow.submit(pool, [item], [proposal], 'weights:1')
        router.service.futures[0].set_result(self.result(item, 1))
        with self.assertRaisesRegex(RuntimeError, 'no bound'):
            flow.poll()
        self.bind_ready(flow, ready)
        flow.drain()
        flow.assert_drained()


    def test_bank_replays_bind_current_controller_without_reusing_historical_behavior(self):
        from draftrl.best_of import repeat_bank_tasks
        from draftrl.practice import auxiliary_controller
        cfg = {'search': {'execution_mode': 'auxiliary'}}
        source = [{'replay_seed': 123, 'entry': {}, 'metadata': {}}]
        tasks, next_seed = repeat_bank_tasks(source, 1000, config=cfg)
        self.assertEqual(len(tasks), 4)
        self.assertEqual(next_seed, 1003)
        self.assertNotIn('controller_contract', source[0]['metadata'])
        for task in tasks:
            self.assertEqual(task['metadata']['controller_contract'], auxiliary_controller(cfg))
        # A loadout's old controller is not attributed to a fresh acting replay.
        acting, _ = repeat_bank_tasks(tasks[:1], 2000, config={'search': {'execution_mode': 'act'}})
        self.assertNotIn('controller_contract', acting[0]['metadata'])

    def test_synchronous_auxiliary_control_keeps_existing_wait_behavior(self):
        router, flow, pool, decision = self.setup_flow(asynchronous=False)
        item, proposal = decision(0, 'first')
        self.assertEqual(flow.submit(pool, [item], [proposal], 'weights:1'), [])
        self.assertIn(0, flow.pending)
        router.service.futures[0].set_result(self.result(item, 1))
        record = self.bind_ready(flow, flow.poll())[0]
        self.assertEqual(record['old_logp'], -.75)
        self.assertIn('search_aux', record)
        flow.drain()


if __name__ == '__main__':
    unittest.main()
