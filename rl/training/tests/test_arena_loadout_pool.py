from copy import deepcopy
from dataclasses import asdict
import unittest

from gakumas_training.tasks import FullProduceConfig, FullProduceTask


class LoadoutPoolTests(unittest.TestCase):
    def config(self):
        return FullProduceConfig(loadout={'idol_card_id': 'base_not_selected'},
            research_config={'growth_panel_levels': {'01': 999}, 'support_event_probability': 0.7},
            loadout_pool=[
                {'name': 'a', 'loadout': {'idol_card_id': 'i_card-amao-1-000', 'auto_support_cards': False},
                 'research_config': {'support_event_probability': 0.1}},
                {'name': 'b', 'loadout': {'idol_card_id': 'i_card-shro-3-018', 'auto_support_cards': False}}])

    def test_repeated_seed_stable_balanced_and_no_nested_base_merge(self):
        config = self.config()
        task = FullProduceTask(config)
        before = deepcopy(asdict(config))
        self.assertEqual([task.select_profile(seed)[0] for seed in range(10)], ['a', 'b'] * 5)
        self.assertEqual(task.select_profile(100), task.select_profile(100))
        self.assertEqual(task.select_profile(100)[2], {'support_event_probability': 0.1})
        self.assertEqual(task.select_profile(101)[2], {})
        name, loadout, research = task.select_profile(100)
        loadout['idol_card_id'] = 'mutated'
        research['support_event_probability'] = 1.0
        self.assertEqual(asdict(config), before)

    def test_empty_duplicate_or_unknown_pool_entry_is_rejected(self):
        for pool in ([], [{'name': 'x', 'loadout': {}}],
                     [{'name': 'x', 'loadout': {'idol_card_id': 'a'}, 'typo': 1}],
                     [{'name': 'x', 'loadout': {'idol_card_id': 'a'}}] * 2):
            with self.subTest(pool=pool), self.assertRaises(ValueError):
                FullProduceTask(FullProduceConfig(loadout_pool=pool))

    def test_no_pool_preserves_original_single_loadout_behavior(self):
        config = FullProduceConfig()
        task = FullProduceTask(config)
        self.assertEqual(task.select_profile(0), ('single_loadout', config.loadout, config.research_config))
        self.assertEqual(task.select_profile(1), task.select_profile(0))


if __name__ == '__main__':
    unittest.main()
