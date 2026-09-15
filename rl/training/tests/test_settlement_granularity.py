"""External encoding fidelity probes; existing engine behavior is the golden oracle."""
from copy import deepcopy
from dataclasses import asdict
import shutil
import unittest
from unittest.mock import patch

from gakumas_training.contracts import DecisionContext
from gakumas_training.encoding import BuffContribution, BuffLedger, DecisionEncoder
from gakumas_training.encoding.projection import build_buff_projection
from gakumas_training.encoding.graph import _exam_projection


def exam_decision(values, field='score'):
    actions = [{'type': 'assignment', 'lhs': field, 'op': '+=',
                'rhs': {'type': 'number', 'value': v}} for v in values]
    return DecisionContext('exam_score', 'exam_action', {'exam': {
        'schema_version': 'arena-public-exam/1', 'observation_scope': 'public',
        'state': {}, 'cards': [{'instance_id': 'copy:0', 'definition_id': 647,
            'effective': {'actions': [{'actions': actions}]}}],
        'definitions': {'cards': [{'id': 647, 'type': 'active'}], 'drinks': [], 'p_items': []},
        'drinks': [], 'zones': {'hand': ['copy:0']},
    }}, ({'type': 'play', 'instance_id': 'copy:0'},))


class EncodingGranularityTests(unittest.TestCase):
    def test_action_count_values_and_order_survive_encoding_without_mutation(self):
        encoder = DecisionEncoder()
        for field, pieces, total in [('score', (10, 10), (20,)),
                                     ('goodImpressionTurns', (3, 5), (8,))]:
            with self.subTest(field=field):
                decision = exam_decision(pieces, field)
                original = deepcopy(decision)
                split = encoder.encode(decision)
                combined = encoder.encode(exam_decision(total, field))
                self.assertNotEqual(split, combined)
                self.assertGreater(split.node_count, combined.node_count)
                self.assertEqual(decision, original)
        self.assertNotEqual(encoder.encode(exam_decision((3, 5))),
                            encoder.encode(exam_decision((5, 3))))

    def test_reward_programs_with_one_or_two_grants_are_never_bucketed(self):
        encoder = DecisionEncoder()
        encoded = []
        for count in (1, 2):
            trigger = 'p_trigger-get_produce_drink'
            observation = {'produce': {'support_skills': [{
                'skill_id': 'synthetic', 'trigger_id': trigger, 'effect_ids': ['reward'],
                'fire_limit': 0, 'activation_rate_permille': 0, 'source': 'support_skill'}]},
                'mechanisms': [
                    {'table': 'ProduceTrigger', 'id': trigger,
                     'data': {'id': trigger, 'phaseType': 'ProducePhaseType_GetProduceDrink'}},
                    {'table': 'ProduceEffect', 'id': 'reward', 'data': {
                        'id': 'reward', 'produceEffectType': 'ProduceEffectType_ProduceReward',
                        'produceResourceType': 'ProduceResourceType_ProduceDrink',
                        'pickCountMin': count, 'pickCountMax': count}}]}
            projected, report = build_buff_projection(observation)
            self.assertEqual(report['projected_sources'], 0)
            self.assertEqual(projected, observation)
            encoded.append(encoder.encode(DecisionContext('full_produce', 'outer', observation, ({'type': 'rest'},))))
        self.assertNotEqual(*encoded)


@unittest.skipUnless(shutil.which('node'), 'Node required for pinned native engine')
class NativeGranularityTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        from gakumas_arena.engine.training import close_training_worker
        close_training_worker()

    def opening(self, body):
        from gakumas_arena import TrainingExam, make_training_entry
        return TrainingExam(make_training_entry([647], turn_types=['vocal'],
            stage_effects='at:afterStartOfTurn { ' + body + '; limit:1 }'), seed=17).observe()

    def test_each_score_hit_receives_concentration(self):
        split = self.opening('concentration=3; score+=10; score+=10')
        combined = self.opening('concentration=3; score+=20')
        self.assertEqual(split['state']['score'], 26)
        self.assertEqual(combined['state']['score'], 23)
        repeated = self.opening('concentration=3; scoreTimes=1; score+=10')
        self.assertEqual(repeated['state']['score'], 26)

    def test_good_impression_gains_round_per_action(self):
        prefix = 'setGoodImpressionTurnsBuff(0.1); '
        self.assertEqual(self.opening(prefix + 'goodImpressionTurns+=3; goodImpressionTurns+=5')
                         ['state']['goodImpressionTurns'], 10)
        self.assertEqual(self.opening(prefix + 'goodImpressionTurns+=8')['state']['goodImpressionTurns'], 9)

    def encode_public(self, observation):
        encoder = DecisionEncoder()
        encoded = encoder.encode(DecisionContext('exam_score', 'exam_action',
            {'exam': observation}, tuple(observation['actions'])))
        return encoder, encoded

    def test_external_encoding_keeps_golden_accumulated_good_condition(self):
        observation = self.opening('goodConditionTurns+=2; goodConditionTurns+=2')
        original = deepcopy(observation)
        self.assertEqual(observation['state']['goodConditionTurns'], 4)
        projected = _exam_projection(observation)
        self.assertEqual(projected['state']['goodConditionTurns'], observation['state']['goodConditionTurns'])
        encoder, encoded = self.encode_public(observation)
        token = encoder.vocabulary.lookup['goodConditionTurns:number']
        values = [numeric for features in encoded.features for identity, numeric in features if identity == token]
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0][1], 4 / 1000)
        self.assertEqual(observation, original)

    def test_external_projection_keeps_golden_modifier_buckets_as_reported(self):
        observation = self.opening('setScoreBuff(0.125,2); setScoreBuff(0.25,2); setScoreBuff(0.5,3)')
        original = deepcopy(observation)
        # Golden owns merging and expiry. The external layer must neither
        # split its existing buckets nor collapse its remaining distinct ones.
        expected = deepcopy(observation['state']['scoreBuffs'])
        self.assertTrue(expected)
        self.assertEqual(_exam_projection(observation)['state']['scoreBuffs'], expected)
        self.encode_public(observation)
        self.assertEqual(observation, original)


class ProduceGranularityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gakumas_arena.env import get_repository
        from gakumas_rl.idol_config import build_idol_loadout
        from gakumas_rl.simulation.produce.runtime import ProduceRuntime
        cls.repository = get_repository()
        scenario = cls.repository.build_scenario('produce-008')
        loadout = build_idol_loadout(cls.repository, scenario, 'i_card-amao-1-000', producer_level=35, idol_rank=4)
        cls.runtime = ProduceRuntime(cls.repository, scenario, seed=23, idol_loadout=loadout,
                                     produce_choice_selector=lambda request: 0)
        cls.runtime.reset()

    def prepare(self, limit=0):
        from gakumas_rl.simulation.produce.runtime import ActiveProduceSkillState
        rt = self.runtime
        rt.active_produce_items = []
        rt.active_produce_skills = [ActiveProduceSkillState(
            name, 2, 'p_trigger-get_produce_drink', ('p_effect-dance_addition-0004_0004',),
            fire_limit=limit, source='support_skill') for name in ('source_a', 'source_b')]
        rt.drinks = []
        rt.state['dance'] = 0
        rt._ability_chain_guard_depth = 0
        rt.hif_sampling_kernel = None
        return rt

    def test_two_drinks_finish_each_event_before_next_grant_in_all_reward_paths(self):
        from gakumas_arena.produce.sampling import HifSamplingKernel
        for mode in ('explicit_resources', 'legacy_random', 'hif_pool', 'custom_p_item'):
            with self.subTest(mode=mode):
                rt = self.prepare()
                trace = []
                dispatch = rt._dispatch_produce_item_phase
                def record(phase, **context):
                    result = dispatch(phase, **context)
                    if phase == 'ProducePhaseType_GetProduceDrink':
                        trace.append((len(rt.drinks), rt.state['dance'],
                                      [s.fire_count for s in rt.active_produce_skills]))
                    return result
                effect = {'id': 'synthetic-two-drinks', 'produceEffectType': 'ProduceEffectType_ProduceRewardSet',
                          'produceResourceType': 'ProduceResourceType_ProduceDrink',
                          'pickCountMin': 2, 'pickCountMax': 2}
                if mode == 'explicit_resources':
                    drink_id = rt.repository.produce_drinks.rows[0]['id']
                    effect['produceRewards'] = [{'resourceType': 'ProduceResourceType_ProduceDrink',
                                                'resourceId': drink_id}] * 2
                elif mode == 'hif_pool':
                    rt.hif_sampling_kernel = HifSamplingKernel(rt)
                elif mode == 'custom_p_item':
                    effect['id'] = 'synthetic-p_rd-drink_set-all-random-02_02'
                with patch.object(rt, '_dispatch_produce_item_phase', side_effect=record):
                    if mode == 'custom_p_item':
                        self.assertTrue(rt.customize_items.rewards.apply(effect))
                    else:
                        rt._grant_rewards(effect, source_action_type='event')
                self.assertEqual(trace, [(1, 8.0, [1, 1]), (2, 16.0, [2, 2])])

    def test_independent_limit_and_support_chain_guard_remain_effective(self):
        rt = self.prepare(limit=1)
        drink_id = rt.repository.produce_drinks.rows[0]['id']
        for _ in range(2):
            rt._grant_resource('ProduceResourceType_ProduceDrink', drink_id, 0)
        self.assertEqual([s.fire_count for s in rt.active_produce_skills], [1, 1])
        self.assertEqual(rt.state['dance'], 8)
        rt = self.prepare()
        rt._ability_chain_guard_depth = 1
        try:
            rt._grant_resource('ProduceResourceType_ProduceDrink', drink_id, 0)
        finally:
            rt._ability_chain_guard_depth = 0
        self.assertEqual(len(rt.drinks), 1)
        self.assertEqual(rt.state['dance'], 0)

    def test_safe_bucket_is_gain_per_event_and_does_not_execute_or_mutate_arena(self):
        rt = self.prepare()
        observation = {'produce': {'support_skills': [asdict(s) for s in rt.active_produce_skills]},
            'mechanisms': [{'table': table, 'id': identity,
                            'data': rt.repository.load_table(table).first(identity)} for table, identity in (
                ('ProduceTrigger', 'p_trigger-get_produce_drink'),
                ('ProduceEffect', 'p_effect-dance_addition-0004_0004'))]}
        original = deepcopy(observation)
        projected, report = build_buff_projection(observation)
        ledger = BuffLedger()
        ledger.synchronize(BuffContribution(**c) for c in projected['buff_contributions'])
        self.assertEqual(report['projected_sources'], 2)
        self.assertEqual(ledger.project()[0]['value'], 8)
        self.assertEqual(observation, original)
        self.assertEqual([s.fire_count for s in rt.active_produce_skills], [0, 0])
        self.assertEqual(rt.state['dance'], 0)


if __name__ == '__main__':
    unittest.main()
