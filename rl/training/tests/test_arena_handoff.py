"""Software contract fixture for the 3+2 boundary, not natural-game coverage."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gakumas_training.contracts import PolicySelection
from gakumas_training.tasks import FullProduceConfig, FullProduceTask


class HandoffTests(unittest.TestCase):
    def test_selection_clear_continues_same_episode_and_uses_final_rating_once(self):
        config = FullProduceConfig(loadout={'idol_card_id': 'i_card-amao-1-000',
            'auto_support_cards': False, 'support_card_ids': ['s_card-2-0040'], 'support_card_levels': [41]})
        task = FullProduceTask(config)
        sentinel_memory = object()
        constructed = []

        class FixtureRun:
            def __init__(self, kwargs):
                self.normalized_loadout = kwargs['loadout']
                self.scenario = kwargs['scenario']
                self.count = 3 if self.scenario == 'hif_selection' else 2
                self.index = 0
                self.terminated = False
                self.fault = None
                self.exam_policy = kwargs['exam_policy']
                self.inner = kwargs['produce_choice_selector']
                self.runtime = SimpleNamespace(fixture=self,
                    export_hif_selection_memory=lambda: sentinel_memory)
                self.lifecycle = SimpleNamespace(status='active', terminal_artifact=self.artifact)
                if self.scenario == 'hif_final':
                    self.assertion_memory = kwargs['selection_memory']

            def public(self):
                return {'state': {'fixture_stage': self.index}, 'support_skills': [], 'resolution': {}}

            def observe(self):
                return {'terminated': self.terminated, 'sampling_scope': {'fixture': True},
                        'actions': [] if self.terminated else [{'action_type': 'a'}, {'action_type': 'b'}]}

            def act(self, action):
                self.inner({'options': [{'x': 1}, {'x': 2}], 'kind': 'fixture_inner',
                            'context': {}, 'public_state': self.public()})
                self.exam_policy({'choice': None, 'actions': [{'type': 'play'}, {'type': 'end_turn'}]})
                self.index += 1
                self.terminated = self.index == self.count
                if self.terminated:
                    self.lifecycle.status = 'selection_clear' if self.scenario == 'hif_selection' else 'final_clear'

            def artifact(self):
                return {'normal_terminal': True, 'outcome': self.lifecycle.status,
                    'accepted_exams': [{'exam_score': i} for i in range(self.count)],
                    'state': {}, 'summary': {'produce_result': {
                        'score': 45678 if self.scenario == 'hif_final' else 9999999,
                        'formula_detail': {'rating': 45678}, 'combined_score': 123456789}}}

        def create(**kwargs):
            run = FixtureRun(kwargs)
            constructed.append(run)
            return run

        with patch('gakumas_arena.produce.create_hif_training_produce', create), \
             patch('gakumas_arena.produce.public_state.live_public_state', lambda runtime: runtime.fixture.public()), \
             patch('gakumas_training.tasks.full_produce.MasterMechanisms') as mechanisms:
            mechanisms.return_value.closure.return_value = []
            episode = task.run_episode(lambda _: PolicySelection(0, 0, 0, 3), seed=10, policy_version=3)
        self.assertEqual(len(constructed), 2)
        self.assertIs(constructed[1].assertion_memory, sentinel_memory)
        self.assertEqual(constructed[0].normalized_loadout.support_card_ids, ('s_card-2-0040',))
        self.assertEqual(config.loadout['support_card_ids'], ['s_card-2-0040'])
        self.assertEqual(episode.raw_score, 45678)
        self.assertEqual(episode.metadata['accepted_exam_count'], 5)
        self.assertEqual(episode.metadata['completed_scenarios'], ['hif_selection', 'hif_final'])
        self.assertEqual(len(episode.transitions), 15)
        self.assertEqual([t.decision.kind for t in episode.transitions],
                         ['outer', 'produce_choice', 'exam_action'] * 5)
        scenarios = [t.decision.observation['produce']['scenario'] for t in episode.transitions]
        self.assertEqual(scenarios, ['hif_selection'] * 9 + ['hif_final'] * 6)
        self.assertTrue(all(t.decision.task == 'full_produce' for t in episode.transitions))


if __name__ == '__main__':
    unittest.main()
