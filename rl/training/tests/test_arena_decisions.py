import math
import unittest

from gakumas_training.arena_adapter.decisions import DecisionRecorder, choose_exam
from gakumas_training.contracts import PolicySelection


class RecorderTests(unittest.TestCase):
    def test_forced_actions_never_call_policy(self):
        recorder = DecisionRecorder('exam_score', lambda _: self.fail('forced policy call'), 4)
        self.assertEqual(recorder.select('exam_action', {}, [{'x': 1}]), {'x': 1})
        self.assertEqual(recorder.transitions, [])

    def test_snapshot_isolated_from_policy_mutation(self):
        def policy(context):
            context.observation['x']['hp'] = 999
            context.candidates[1]['slot'] = 999
            return PolicySelection(1, -math.log(2), 0, 4)
        recorder = DecisionRecorder('exam_score', policy, 4)
        observation = {'x': {'hp': 8}}
        selected = recorder.select('exam_action', observation, [{'slot': 0}, {'slot': 1}])
        self.assertEqual(selected['slot'], 1)
        self.assertEqual(recorder.transitions[0].decision.observation['x']['hp'], 8)
        observation['x']['hp'] = 0
        self.assertEqual(recorder.transitions[0].decision.observation['x']['hp'], 8)

    def test_fault_rolls_back_all_nested_decisions(self):
        recorder = DecisionRecorder('full_produce', lambda _: PolicySelection(0, -math.log(2), 0, 2), 2)
        recorder.select('outer', {}, [{}, {}])
        def execute():
            recorder.select('outer', {}, [{}, {}])
            recorder.select('produce_choice', {}, [{}, {}])
            raise RuntimeError('native failure')
        with self.assertRaisesRegex(RuntimeError, 'native failure'):
            recorder.transaction(execute)
        self.assertEqual(len(recorder.transitions), 1)

    def test_behavior_version_mismatch_is_rejected(self):
        recorder = DecisionRecorder('exam_score', lambda _: PolicySelection(0, 0, 0, 2), 1)
        with self.assertRaisesRegex(ValueError, 'version'):
            recorder.select('exam_action', {}, [{}, {}])
        self.assertEqual(recorder.transitions, [])

    def test_ordered_native_choice_preserves_order_without_permutations(self):
        recorder = DecisionRecorder('exam_score', lambda _: PolicySelection(1, -math.log(2), 0, 0), 0)
        exam = {'choice': {'type': 'use_selected', 'min': 2, 'max': 2, 'ordered': True,
                           'allow_duplicates': False, 'candidates': [{'index': 0}, {'index': 1}]}}
        answer = choose_exam(recorder, exam, lambda resolution: {'resolution': resolution})
        self.assertEqual(answer, [1, 0])
        self.assertEqual(len(recorder.transitions), 1)  # second pick is forced

    def test_optional_choice_can_stop_and_records_selected_context(self):
        def policy(context):
            return PolicySelection(len(context.candidates)-1, -math.log(len(context.candidates)), 0, 0)
        recorder = DecisionRecorder('exam_score', policy, 0)
        exam = {'choice': {'type': 'hold', 'min': 0, 'max': 2,
                           'candidates': [{'index': 0}, {'index': 1}]}}
        self.assertEqual(choose_exam(recorder, exam, lambda x: {'resolution': x}), [])
        self.assertEqual(recorder.transitions[0].decision.observation['resolution']['selected_indices'], [])


if __name__ == '__main__':
    unittest.main()
