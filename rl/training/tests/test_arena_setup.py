from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from gakumas_training.arena_adapter.decisions import DecisionRecorder
from gakumas_training.contracts import PolicySelection
from gakumas_training.tasks import FullProduceConfig, FullProduceTask
from gakumas_training.tasks.full_produce.setup import (
    INVENTORY_SCHEMA, legal_setup_options, resolve_setup_catalog, resolve_setup_inventory,
    select_setup_loadout)


class SetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gakumas_training.arena_adapter.environment import ensure_arena
        ensure_arena()
        from gakumas_arena.env import get_repository
        cls.repo = get_repository()

    def inventory(self):
        from gakumas_rl.idol_config import _resolve_support_card_level
        rows = [r for r in self.repo.support_cards.rows
                if r['planType'] in ('ProducePlanType_Common', 'ProducePlanType_Plan1')][:8]
        return {'schema_version': INVENTORY_SCHEMA,
            'supports': [{'support_card_id': row['id'], 'level': _resolve_support_card_level(row, None)}
                         for row in rows],
            'memories': [{'memory_id': 'sense-gift', 'gift_id': 'memory_gift-20260516-hif-plan1-1'},
                         {'memory_id': 'logic-gift', 'gift_id': 'memory_gift-20260516-hif-plan2-1'}]}

    def base(self):
        return {'idol_card_id': 'i_card-shro-3-018', 'producer_level': 76,
                'idol_rank': 6, 'auto_support_cards': False}

    @staticmethod
    def research_inventory():
        return json.loads((Path(__file__).resolve().parents[1] / 'colab/configs/research_inventory.json')
                          .read_text(encoding='utf8'))

    @staticmethod
    def observation(repository, **kwargs):
        return {'context': kwargs}

    def test_setup_selects_real_kit_once_before_initial_effects(self):
        inv, base = self.inventory(), self.base()
        original = deepcopy((inv, base))
        recorder = DecisionRecorder('full_produce', lambda c: PolicySelection(0, 0., 0., 7), 7)
        loadout, metadata = select_setup_loadout(base, inv, recorder, self.repo,
            rules={}, prepare_observation=self.observation)
        self.assertEqual((inv, base), original)
        self.assertEqual(len(set(loadout['support_card_ids'])), 6)
        self.assertEqual(metadata['memory_count'], 1)
        self.assertEqual([r['borrowed'] for r in metadata['support_sources']], [False] * 5 + [True])
        self.assertEqual(loadout['memories'][0]['memory_id'], 'sense-gift')
        self.assertEqual([t.decision.kind for t in recorder.transitions], ['setup_support'] * 6 + ['setup_memory'])
        self.assertTrue(all(t.selection.policy_version == 7 for t in recorder.transitions))
        # Real Arena reset: a gift grants its own card and three +15 initial
        # abilities; contest snapshot stats must not be added to the idol.
        from gakumas_arena.produce import create_hif_training_produce
        from gakumas_arena.produce.loadout_handoff import thaw_loadout
        plain = deepcopy(loadout)
        plain['memories'] = []
        def start(cfg):
            return create_hif_training_produce(scenario='hif_selection', loadout=thaw_loadout(cfg),
                seed=19, exam_policy=lambda o: o['actions'][0], produce_choice_selector=lambda q: 0)
        with_memory, baseline = start(loadout), start(plain)
        for color in ('vocal', 'dance', 'visual'):
            self.assertEqual(with_memory.runtime.state[color] - baseline.runtime.state[color], 15)
        carried = [r for r in with_memory.runtime.deck if r.get('sourceMemoryId') == 'sense-gift']
        self.assertEqual(len(carried), 1)
        self.assertEqual((carried[0]['id'], carried[0]['upgradeCount']), ('p_card-01-act-2_001', 1))

    def test_stop_memory_is_policy_decision_and_setup_failure_rolls_back(self):
        def stop(c):
            index = next((i for i, a in enumerate(c.candidates) if a['type'] == 'stop_memory'), 0)
            return PolicySelection(index, 0., 0., 0)
        recorder = DecisionRecorder('full_produce', stop, 0)
        loadout, _ = select_setup_loadout(self.base(), self.inventory(), recorder, self.repo,
            rules={}, prepare_observation=self.observation)
        self.assertEqual(loadout['memories'], [])
        def bad(c):
            if c.kind == 'setup_memory':
                raise RuntimeError('policy failed')
            return PolicySelection(0, 0., 0., 0)
        recorder = DecisionRecorder('full_produce', bad, 0)
        with self.assertRaisesRegex(RuntimeError, 'policy failed'):
            select_setup_loadout(self.base(), self.inventory(), recorder, self.repo,
                rules={}, prepare_observation=self.observation)
        self.assertEqual(recorder.transitions, [])

    def test_invalid_or_fabricated_levels_duplicate_ids_and_missing_specs_fail(self):
        from gakumas_rl.idol_config import memory_spec_from_gift
        cases = []
        inv = self.inventory(); inv['supports'][0]['level'] = 999; cases.append(inv)
        inv = self.inventory(); inv['supports'].append(deepcopy(inv['supports'][0])); cases.append(inv)
        inv = self.inventory(); inv['memories'].append(deepcopy(inv['memories'][0])); cases.append(inv)
        inv = self.inventory(); spec = asdict(memory_spec_from_gift(self.repo, inv['memories'][0]['gift_id']))
        spec['ability_levels'] = (999,) * len(spec['ability_ids'])
        inv['memories'] = [{'memory_id': 'invalid-level', 'spec': spec}]; cases.append(inv)
        inv = self.inventory(); inv['memories'] = [{'memory_id': 'missing', 'spec': {}}]; cases.append(inv)
        for inv in cases:
            with self.subTest(inventory=inv), self.assertRaises(ValueError):
                resolve_setup_inventory(self.repo, inv)

    def test_no_more_than_four_memories_and_no_duplicate_selection(self):
        inv = self.inventory()
        inv['memories'] = [{'memory_id': row['id'], 'gift_id': row['id']}
                           for row in self.repo.load_table('MemoryGift').rows]
        recorder = DecisionRecorder('full_produce', lambda c: PolicySelection(0, 0., 0., 0), 0)
        loadout, meta = select_setup_loadout(self.base(), inv, recorder, self.repo,
            rules={}, prepare_observation=self.observation)
        self.assertEqual(len(loadout['memories']), 4)
        self.assertEqual(len({m['memory_id'] for m in loadout['memories']}), 4)
        self.assertEqual(meta['memory_count'], 4)

    def test_mixed_cycles_balance_every_idol_and_given_default_has_no_setup(self):
        pool = [{'name': str(i), 'loadout': self.base()} for i in range(5)]
        task = FullProduceTask(FullProduceConfig(loadout_pool=pool, setup_mode='mixed',
                                               setup_inventory=self.inventory()))
        self.assertEqual([task.select_setup_mode(s) for s in range(10)], ['given'] * 5 + ['select'] * 5)
        self.assertEqual([task.select_profile(s)[0] for s in range(10)], [str(i) for i in range(5)] * 2)
        self.assertEqual(FullProduceTask().select_setup_mode(3), 'given')
        with self.assertRaises(ValueError):
            FullProduceTask(FullProduceConfig(setup_mode='select'))

    def test_research_components_assemble_real_memories_in_bounded_stages(self):
        inventory = self.research_inventory()
        catalog = resolve_setup_catalog(self.repo, inventory)
        self.assertEqual(len(catalog['supports']), 201)
        self.assertEqual(len(catalog['components']['gold_factors']), 10)
        self.assertEqual(len(catalog['components']['hif_abilities']), 105)
        calls = []
        def policy(context):
            calls.append(context)
            return PolicySelection(0, 0., 0., 5)
        recorder = DecisionRecorder('full_produce', policy, 5)
        loadout, meta = select_setup_loadout(self.base(), inventory, recorder, self.repo,
            rules={}, resolved_catalog=catalog, prepare_observation=self.observation)
        self.assertEqual(len(loadout['memories']), 4)
        self.assertEqual([c.kind for c in calls], ['setup_support'] * 6 +
            (['setup_memory_card', 'setup_memory_card_variant', 'setup_memory_hif'] +
             ['setup_memory_factor'] * 3) * 4)
        self.assertEqual(len({m['memory_id'] for m in loadout['memories']}), 4)
        # Identical compositions and repeated unique HIF abilities are allowed;
        # their actual non-stacking semantics remain visible to the policy.
        self.assertEqual(len({tuple(m['ability_ids']) for m in loadout['memories']}), 1)
        for memory in loadout['memories']:
            self.assertEqual(len(memory['ability_ids']), 4)
            self.assertEqual(len(set(memory['ability_ids'][:3])), 3)
        first_identity = next(c for c in calls if c.kind == 'setup_memory_card')
        first_variant = next(c for c in calls if c.kind == 'setup_memory_card_variant')
        first_factor = next(c for c in calls if c.kind == 'setup_memory_factor')
        self.assertLess(len(first_identity.candidates), 150)
        card_ids = {m['spec']['produce_card']['card_id'] for m in first_variant.observation['context']['memory_options']}
        self.assertEqual(len(card_ids), 1)
        for context in (first_identity, first_variant, first_factor):
            self.assertEqual(len(context.observation['context']['support_options']), 6)
        partial = first_factor.observation['context']['selected_memories'][0]
        self.assertFalse(partial['assembly_complete'])
        self.assertTrue(partial['hif_ability_selected'])
        self.assertEqual(partial['gold_factors_selected'], 0)
        self.assertEqual(meta['memory_count'], 4)

    def test_research_slot_budget_counts_produce_start_acquisition(self):
        inventory = self.research_inventory()
        for rarity, custom_count in [('ProduceCardRarity_R', 2), ('ProduceCardRarity_Sr', 1)]:
            invalid = deepcopy(inventory)
            wrapper = next(row for row in invalid['memory_components']['cards']
                if len(row['spec']['produce_card']['customize_ids']) == custom_count
                and self.repo.card_row_by_upgrade(row['spec']['produce_card']['card_id'], 1)['rarity'] == rarity)
            wrapper['spec']['produce_card']['phase_type'] = 'ProduceMemoryProduceCardPhaseType_ProduceStart'
            with self.subTest(rarity=rarity), self.assertRaisesRegex(ValueError, 'slot budget'):
                resolve_setup_catalog(self.repo, invalid)
        # Existing given/explicit memories do not acquire a new research-only constraint.
        generic = {'schema_version': INVENTORY_SCHEMA, 'supports': inventory['supports'],
                   'memories': [wrapper]}
        self.assertEqual(len(resolve_setup_inventory(self.repo, generic)[1]), 1)

    def test_component_stop_and_none_are_explicit_and_no_partial_commit_on_failure(self):
        inventory = self.research_inventory()
        def stop(context):
            index = next((i for i, a in enumerate(context.candidates) if a['type'] == 'stop_memory'), 0)
            return PolicySelection(index, 0., 0., 0)
        recorder = DecisionRecorder('full_produce', stop, 0)
        loadout, _ = select_setup_loadout(self.base(), inventory, recorder, self.repo,
            rules={}, prepare_observation=self.observation)
        self.assertEqual(loadout['memories'], [])
        self.assertEqual(recorder.transitions[-1].decision.kind, 'setup_memory_card')
        def no_hif(context):
            index = next((i for i, a in enumerate(context.candidates) if a['type'] == 'no_hif_ability'), 0)
            return PolicySelection(index, 0., 0., 0)
        recorder = DecisionRecorder('full_produce', no_hif, 0)
        loadout, _ = select_setup_loadout(self.base(), inventory, recorder, self.repo,
            rules={}, prepare_observation=self.observation)
        self.assertTrue(all(len(m['ability_ids']) == 3 for m in loadout['memories']))
        def fail(context):
            if context.kind == 'setup_memory_factor':
                raise RuntimeError('factor-policy-failed')
            return PolicySelection(0, 0., 0., 0)
        recorder = DecisionRecorder('full_produce', fail, 0)
        with self.assertRaisesRegex(RuntimeError, 'factor-policy-failed'):
            select_setup_loadout(self.base(), inventory, recorder, self.repo,
                rules={}, prepare_observation=self.observation)
        self.assertEqual(recorder.transitions, [])

    def test_setup_and_play_form_one_real_full_episode(self):
        task = FullProduceTask(FullProduceConfig(loadout=self.base(), setup_mode='select',
                                               setup_inventory=self.inventory()))
        before = deepcopy(asdict(task.config))
        def policy(context):
            index = next((i for i, row in enumerate(context.candidates)
                          if row.get('type') == 'play' or row.get('action_type') == 'audition_accept'), 0)
            return PolicySelection(index, 0., 0., 3)
        def prepared(*args, **kwargs):
            return select_setup_loadout(*args, **kwargs, prepare_observation=self.observation)
        try:
            # Isolate the setup-state renderer from the real collection/control
            # test; separate encoder integration tests use its actual graph.
            with patch('gakumas_training.tasks.full_produce.setup.select_setup_loadout', prepared):
                episode = task.run_episode(policy, seed=910123, policy_version=3)
        finally:
            task.close()
        self.assertEqual(asdict(task.config), before)
        self.assertEqual(episode.metadata['setup_mode'], 'select')
        self.assertEqual(episode.metadata['selected_memory_ids'], ['sense-gift'])
        self.assertEqual(episode.metadata['selected_memory_specs'][0]['memory_id'], 'sense-gift')
        self.assertEqual(len(episode.metadata['selected_memory_specs'][0]['ability_ids']), 3)
        self.assertEqual(len(episode.metadata['selected_support_ids']), 6)
        self.assertEqual([t.decision.kind for t in episode.transitions[:6]], ['setup_support'] * 6)
        self.assertTrue(all(t.decision.task == 'full_produce' for t in episode.transitions))
        self.assertTrue(all(t.selection.policy_version == 3 for t in episode.transitions))
        self.assertGreater(episode.metadata['accepted_exam_count'], 0)


if __name__ == '__main__':
    unittest.main()
