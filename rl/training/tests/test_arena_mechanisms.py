import unittest

from gakumas_training.arena_adapter.environment import ensure_arena
from gakumas_training.arena_adapter.mechanisms import MasterMechanisms


class MechanismClosureTests(unittest.TestCase):
    def test_active_skill_uses_bound_effects_not_all_master_levels(self):
        ensure_arena()
        from gakumas_arena.env import get_repository
        repository = get_repository()
        identity = 'p_support_skill-common-p_trigger-get_produce_card-0000_0000-p_card_search-deck_all-vocal_addition-02-001'
        rows = repository.load_table('ProduceSkill').all(identity)
        active = [{'skill_id': identity, 'level': row['level'],
                   'trigger_id': row['produceTriggerId1'], 'effect_ids': [row['produceEffectId1']]}
                  for row in rows]
        closure = MasterMechanisms(repository).closure({'support_skills': active})
        self.assertFalse(any(row['table'] == 'ProduceSkill' and row['id'] == identity for row in closure))
        effect_ids = {row['id'] for row in closure if row['table'] == 'ProduceEffect'}
        self.assertTrue({row['produceEffectId1'] for row in rows} <= effect_ids)
        self.assertEqual({x['level'] for x in active}, {1, 2})

    def test_custom_item_closure_contains_reachable_successors_only(self):
        ensure_arena()
        from gakumas_arena.env import get_repository
        repository = get_repository()
        relation = repository.load_table('ProduceCustomizeItemRelationship').rows[0]
        parent, child = relation['parentProduceCustomizeItemId'], relation['childProduceCustomizeItemId']
        closure = MasterMechanisms(repository).closure({'customize_item': {'item_id': parent}})
        item_ids = {row['id'] for row in closure if row['table'] == 'ProduceCustomizeItem'}
        self.assertIn(parent, item_ids)
        self.assertIn(child, item_ids)
        self.assertLess(len(item_ids), len(repository.load_table('ProduceCustomizeItem').rows))
        self.assertTrue(any(row['table'] == 'ProduceCustomizeItemRelationship' for row in closure))


if __name__ == '__main__':
    unittest.main()
