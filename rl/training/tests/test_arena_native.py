"""Real pinned Arena integration; no score, rival, or turn overrides."""
from collections import Counter
from copy import deepcopy
import math
import unittest

from gakumas_training.contracts import PolicySelection
from gakumas_training.tasks import ExamScoreTask, FullProduceTask


def first_play_accept(context):
    index = 0
    if context.kind == 'outer':
        for kind in ('special_finish', 'interval_finish', 'consult_finish', 'audition_accept'):
            match = next((i for i, candidate in enumerate(context.candidates)
                          if candidate.get('action_type') == kind), None)
            if match is not None:
                index = match
                break
    elif context.kind == 'exam_action':
        index = next((i for i, candidate in enumerate(context.candidates) if candidate['type'] == 'play'), 0)
    return PolicySelection(index, 0, 0, 0)  # deterministic diagnostic behavior


class NativeTests(unittest.TestCase):
    def test_exam_raw_score_episode(self):
        task = ExamScoreTask()
        try:
            episode = task.run_episode(first_play_accept, seed=910123, policy_version=0)
        finally:
            task.close()
        self.assertEqual(episode.raw_score, episode.metadata['result']['final_score'])
        self.assertGreater(len(episode.transitions), 0)
        self.assertTrue(all(t.decision.task == 'exam_score' for t in episode.transitions))
        self.assertTrue(all(t.decision.observation['produce'] is None for t in episode.transitions))

    def test_natural_selection_failure_is_retained(self):
        task = FullProduceTask()
        try:
            episode = task.run_episode(first_play_accept, seed=910123, policy_version=0)
        finally:
            task.close()
        self.assertEqual(episode.termination, 'failed')
        self.assertEqual(episode.metadata['completed_scenarios'], ['hif_selection'])
        self.assertTrue(episode.metadata['rating_provenance']['early_terminal_mapping'])
        kinds = Counter(t.decision.kind for t in episode.transitions)
        self.assertTrue({'outer', 'produce_choice', 'exam_action'} <= set(kinds))
        self.assertTrue(all(t.decision.task == 'full_produce' for t in episode.transitions))
        exam = next(t.decision.observation for t in episode.transitions if t.decision.kind == 'exam_action')
        self.assertIn('selection_schedule', exam['produce']['rules'])
        self.assertIn('state', exam['produce'])
        self.assertNotIn('rng', exam)
        self.assertNotIn('seed', exam)

    def test_live_context_has_paid_cost_and_stable_rng_and_effect_frames(self):
        task = FullProduceTask()
        from gakumas_arena.produce import create_hif_training_produce
        from gakumas_arena.produce.public_state import live_public_state
        seen = []
        run = create_hif_training_produce(scenario='hif_selection', seed=81,
            loadout=task.config.loadout, exam_policy=lambda _: None,
            produce_choice_selector=lambda request: (seen.append(request) or 0))
        cached = run.observe()
        run.runtime.state['stamina'] -= 3
        before = deepcopy(run.runtime.np_random.bit_generator.state)
        live = live_public_state(run.runtime)
        self.assertEqual(live['state']['stamina'], cached['state']['stamina'] - 3)
        self.assertEqual(before, run.runtime.np_random.bit_generator.state)
        self.assertEqual(live, live_public_state(run.runtime))
        original = run.runtime._apply_produce_effect
        run.runtime._apply_produce_effect = lambda *a, **k: run.runtime.choose_produce_option('test', [0, 1])
        effect_id = run.runtime.produce_effects.rows[0]['id']
        try:
            run.runtime._apply_effect_rows([effect_id], source_action_type='support_skill')
        finally:
            run.runtime._apply_produce_effect = original
            task.close()
        resolution = seen[-1]['public_state']['resolution']
        self.assertEqual(resolution['frames'][-1]['effect_index'], 0)
        self.assertEqual(resolution['frames'][-1]['effect_ids'], [effect_id])
        self.assertEqual(resolution['blocked_source_classes'], ['support_skill', 'memory_skill'])
        self.assertEqual(live_public_state(run.runtime)['resolution']['frames'], [])


if __name__ == '__main__':
    unittest.main()
