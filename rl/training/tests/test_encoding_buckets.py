from dataclasses import replace
from dataclasses import asdict
from copy import deepcopy
import unittest

from gakumas_training.encoding import BuffContribution, BuffLedger, DecisionEncoder, SemanticCoverageError
from gakumas_training.encoding.projection import build_buff_projection
from gakumas_training.contracts import DecisionContext


def contribution(identity, value, **kwargs):
    return BuffContribution(identity, {"phase": "GetCard"}, "add", "vocal", value,
                            equivalent_settlement=True, **kwargs)


class BucketTests(unittest.TestCase):
    def test_unrecognized_effect_or_source_fields_cannot_bypass_projection_checks(self):
        trigger = 'p_trigger-get_produce_drink'
        observation = {'produce': {'support_skills': [{
            'skill_id': 'source', 'trigger_id': trigger, 'effect_ids': ['gain'],
            'fire_limit': 0, 'activation_rate_permille': 0, 'source': 'support_skill'}]},
            'mechanisms': [
                {'table': 'ProduceTrigger', 'id': trigger,
                 'data': {'id': trigger, 'phaseType': 'ProducePhaseType_GetProduceDrink'}},
                {'table': 'ProduceEffect', 'id': 'gain', 'data': {'id': 'gain',
                    'produceEffectType': 'ProduceEffectType_DanceAddition',
                    'effectValueMin': 4, 'effectValueMax': 4}}]}
        for value in (0, 1):
            changed = deepcopy(observation)
            changed['mechanisms'][1]['data']['futurePerEventRule'] = value
            projected, report = build_buff_projection(changed)
            self.assertEqual(report['projected_sources'], 0)
            self.assertEqual(projected, changed)
            with self.assertRaises(SemanticCoverageError):
                DecisionEncoder().encode(DecisionContext('full_produce', 'outer', changed, ({'type': 'rest'},)))
        changed = deepcopy(observation)
        changed['produce']['support_skills'][0]['cooldown_remaining'] = 2
        projected, report = build_buff_projection(changed)
        self.assertEqual(report['projected_sources'], 0)
        self.assertEqual(projected, changed)

    def test_sum_upgrade_remove_and_expiry(self):
        ledger = BuffLedger()
        ledger.upsert(contribution("a", 3)); ledger.upsert(contribution("b", 16))
        self.assertEqual([x["value"] for x in ledger.project()], [19])
        self.assertNotIn("source_ref", ledger.project()[0])
        ledger.upsert(contribution("a", 5))
        self.assertEqual(ledger.project()[0]["value"], 21)
        ledger.remove("b"); self.assertEqual(ledger.project()[0]["value"], 5)
        ledger.synchronize([]); self.assertEqual(ledger.project(), [])

    def test_probability_counts_and_freshness_do_not_collapse(self):
        cases = [dict(probability=.5), dict(probability=None), dict(remaining_uses=1),
                 dict(counter_group="shared"), dict(source_sensitive=True), dict(emits_per_contribution=True)]
        for args in cases:
            ledger = BuffLedger(); ledger.synchronize([contribution("a", 3, **args), contribution("b", 16, **args)])
            self.assertEqual(len(ledger.project()), 2, args)
        ledger = BuffLedger()
        ledger.synchronize([contribution("a", 3, lifetime={"turns": 2, "fresh": True}),
                            contribution("b", 16, lifetime={"turns": 2, "fresh": False})])
        self.assertEqual(len(ledger.project()), 2)

    def test_multiply_and_max_use_their_own_operator(self):
        for operation, expected in [("multiply", 6), ("max", 3)]:
            ledger = BuffLedger()
            ledger.synchronize([replace(contribution("a", 2), operation=operation),
                                replace(contribution("b", 3), operation=operation)])
            self.assertEqual(ledger.project()[0]["value"], expected)

    def test_projection_does_not_depend_on_previous_episode_insertion_order(self):
        a, b = contribution("a", 3), replace(contribution("b", 16), target="dance")
        left, right = BuffLedger(), BuffLedger()
        left.synchronize([a, b]); right.synchronize([b, a])
        self.assertEqual(left.project(), right.project())
        left.synchronize([b]); left.synchronize([b, a])
        self.assertEqual(left.project(), right.project())

    def test_real_support_contract_projection_replaces_sources(self):
        trigger = "p_trigger-get_produce_card-0000_0000-p_card_search-deck_all"
        def effect(identity, value):
            return {"table": "ProduceEffect", "id": identity,
                    "data": {"id": identity, "produceEffectType": "ProduceEffectType_VocalAddition",
                             "effectValueMin": value, "effectValueMax": value}}
        observation = {"produce": {"support_skills": [
            {"skill_id": identity, "trigger_id": trigger, "effect_ids": [effect_id],
             "fire_limit": 0, "activation_rate_permille": 0, "source": "support_skill"}
            for identity, effect_id in [("support_a", "effect_a"), ("support_b", "effect_b")]]},
            "mechanisms": [effect("effect_a", 3), effect("effect_b", 16),
                {"table": "ProduceTrigger", "id": trigger, "data": {"id": trigger, "phaseType": "ProducePhaseType_GetProduceCard"}}]}
        projected, report = build_buff_projection(observation)
        self.assertEqual(report["projected_sources"], 2)
        self.assertEqual(projected["produce"]["support_skills"], [])
        self.assertEqual(projected["mechanisms"], [])
        encoder = DecisionEncoder()
        encoder.encode(DecisionContext("full_produce", "outer", observation, ({"type": "rest"},)))
        self.assertEqual(encoder._ledger.project()[0]["value"], 19)
        self.assertEqual(len(observation["produce"]["support_skills"]), 2)

    def test_real_arena_dispatch_matches_projected_bucket_across_other_phase(self):
        try:
            from gakumas_arena.env import get_repository
            from gakumas_rl.idol_config import build_idol_loadout
            from gakumas_rl.simulation.produce.runtime import ProduceRuntime, ActiveProduceSkillState
        except ImportError:
            self.skipTest("Arena integration dependencies are not installed")
        repository = get_repository()
        scenario = repository.build_scenario("produce-008")
        loadout = build_idol_loadout(repository, scenario, "i_card-amao-1-000", producer_level=35, idol_rank=4)
        runtime = ProduceRuntime(repository, scenario, seed=23, idol_loadout=loadout)
        runtime.reset()
        trigger_id = "p_trigger-get_produce_drink"
        effect_id = "p_effect-dance_addition-0004_0004"
        effect = repository.load_table("ProduceEffect").first(effect_id)
        trigger = repository.load_table("ProduceTrigger").first(trigger_id)
        other_id = "p_trigger-start_refresh"
        other_trigger = repository.load_table("ProduceTrigger").first(other_id)
        self.assertIsNotNone(other_trigger)
        # Two controlled sources of one real definition, not a claim that the
        # current catalogue contains two different natural cards with this skill.
        runtime.active_produce_skills = [
            ActiveProduceSkillState("source_a", 2, trigger_id, (effect_id,), source="support_skill"),
            ActiveProduceSkillState("other_phase", 2, other_id, (effect_id,), source="support_skill"),
            ActiveProduceSkillState("source_b", 2, trigger_id, (effect_id,), source="memory_skill")]
        observation = {"produce": {"support_skills": [asdict(x) for x in runtime.active_produce_skills]},
                       "mechanisms": [{"table": table, "id": row["id"], "data": row}
                        for table, row in [("ProduceEffect", effect), ("ProduceTrigger", trigger),
                                           ("ProduceTrigger", other_trigger)]]}
        projected, report = build_buff_projection(observation)
        ledger = BuffLedger(); ledger.synchronize(BuffContribution(**x) for x in projected["buff_contributions"])
        self.assertEqual(report["projected_sources"], 2)
        self.assertEqual(len(ledger.project()), 1)
        self.assertEqual(ledger.project()[0]["value"], 8)
        runtime.active_produce_items = []
        for start in (0., runtime._parameter_growth_limit() - 3):
            runtime.state["dance"] = start
            runtime._dispatch_produce_item_phase("ProducePhaseType_GetProduceDrink")
            individual = runtime.state["dance"]
            runtime.state["dance"] = start
            aggregate = {**effect, "effectValueMin": 8, "effectValueMax": 8}
            runtime._apply_produce_effect(aggregate, source_action_type="support_skill")
            self.assertEqual(runtime.state["dance"], individual)


if __name__ == "__main__":
    unittest.main()
