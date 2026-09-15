import unittest

from gakumas_training.arena_adapter.environment import ensure_arena
from gakumas_training.tasks.full_produce import terminal_rating


class RatingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_arena()

    def test_final_uses_rating_not_combined_or_generic_reward(self):
        artifact = {'normal_terminal': True, 'summary': {'reward': 123,
                    'produce_result': {'score': 27182, 'combined_score': 999999,
                        'formula_detail': {'rating': 27182}, 'formula_source': 'test'}}}
        score, provenance = terminal_rating(artifact, scenario='hif_final', early_terminal_policy='unused')
        self.assertEqual(score, 27182)
        self.assertFalse(provenance['early_terminal_mapping'])

    def test_selection_failure_mapping_is_explicit_and_keeps_negative_rating(self):
        artifact = {'normal_terminal': True, 'summary': {'produce_result': {'score': 7777}},
                    'state': {'vocal': 0, 'dance': 0, 'visual': 0, 'star_quality': 0,
                              'hif_selection_scores': [999999]}}
        score, provenance = terminal_rating(artifact, scenario='hif_selection',
                                early_terminal_policy='final_formula_zero_unplayed_v1')
        self.assertEqual(score, -2000)
        self.assertTrue(provenance['early_terminal_mapping'])
        self.assertFalse(provenance['game_awarded_rating_verified'])
        with self.assertRaisesRegex(ValueError, 'explicit'):
            terminal_rating(artifact, scenario='hif_selection', early_terminal_policy='unknown')

    def test_engine_fault_never_becomes_reward(self):
        with self.assertRaisesRegex(ValueError, 'faults'):
            terminal_rating({'normal_terminal': False}, scenario='hif_final', early_terminal_policy='unused')


if __name__ == '__main__':
    unittest.main()
