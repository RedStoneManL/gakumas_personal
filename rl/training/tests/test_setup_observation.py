import copy
from dataclasses import asdict
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import torch

from gakumas_training.arena_adapter.environment import ensure_arena
from gakumas_training.arena_adapter.setup_observation import prepare_setup_observation, _compiler
from gakumas_training.contracts import DecisionContext
from gakumas_training.encoding import DecisionEncoder, SemanticCoverageError
from gakumas_training.encoding.graph import collate
from gakumas_training.models import ModelConfig, PolicyValueNet


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            yield from walk(child)


class SetupObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_arena()
        from gakumas_arena.env import get_repository
        cls.repository = get_repository()
        cls.base = json.loads((Path(__file__).parents[1] / "colab/configs/full_produce.json").read_text())["task_config"]["loadout"]
        torch.set_num_threads(1)

    def support(self, sid="s_card-3-0030", level=60, identity=None):
        return {"id": identity or "setup:support:" + sid, "support_card_id": sid, "level": level}

    def memory(self):
        from gakumas_rl.idol_config import memory_spec_from_gift
        gift = self.repository.load_table("MemoryGift").rows[0]
        spec = memory_spec_from_gift(self.repository, gift["id"])
        return {"id": "setup:memory:fixture", "memory_id": "fixture", "spec": asdict(spec)}

    def observe(self, supports=(), memories=(), **kwargs):
        fields = dict(base_loadout=self.base, support_options=list(supports), memory_options=list(memories),
                      selected_supports=[], selected_memories=[], phase="support", slot=0, rules={})
        fields.update(kwargs)
        return prepare_setup_observation(self.repository, **fields)

    def test_no_runtime_initialization_and_only_exact_current_skills(self):
        from gakumas_rl.simulation.produce.runtime import ProduceRuntime
        with patch.object(ProduceRuntime, "__init__", side_effect=AssertionError("Setup initialized produce")):
            observation = self.observe([self.support()])
        skills = observation["entities"]["support_options"][0]["current_skills"]
        target = next(s for s in skills if "end_lesson-lesson_dance_sp" in s["definition_ref"])
        self.assertEqual(target["level"], 3)
        self.assertEqual(target["listeners"][0]["effect"]["parameters"]["effectValueMin"], 17)
        self.assertEqual(target["listeners"][0]["activation_rate_permille"], 0)
        self.assertEqual(target["listeners"][0]["fire_limit"], 0)
        self.assertEqual(len({s["definition_ref"] for s in skills}), len(skills))
        self.assertEqual(len(observation["entities"]["support_options"][0]["event_sequence"]), 3)
        # Future event P-item/card rewards are bound below the support candidate.
        reward_kinds = {x.get("definition_kind") for x in walk(observation["entities"]["support_options"])
                        if isinstance(x, dict)}
        self.assertIn("ProduceItem", reward_kinds)

    def test_memory_components_partial_state_and_contest_stats_are_separate(self):
        memory = self.memory()
        complete = self.observe(memories=[memory], phase="memory")
        entity = complete["entities"]["memory_options"][0]
        self.assertEqual(entity["contest_only_statistics"]["vocal"], memory["spec"]["vocal"])
        self.assertTrue(entity["abilities"])
        self.assertIsNotNone(entity["inherited_card"]["effective_card"])
        component = copy.deepcopy(memory)
        component["id"] = "setup:memory:component"
        component["spec"]["produce_card"] = None
        component["spec"]["ability_ids"] = component["spec"]["ability_ids"][:1]
        component["spec"]["ability_levels"] = component["spec"]["ability_levels"][:1]
        observed = self.observe(memories=[component], selected_memories=[memory], phase="memory_factor", slot=2)
        self.assertEqual(observed["context"]["selected_memory_refs"], [memory["id"]])
        self.assertEqual(len(observed["entities"]["memory_options"]), 2)
        selected = next(m for m in observed["entities"]["memory_options"] if m["id"] == memory["id"])
        self.assertEqual(selected["inherited_card"], entity["inherited_card"])

    def test_customization_uses_effective_grow_values_and_keeps_order(self):
        memory = self.memory()
        card = next(c for c in self.repository.load_table("ProduceCard").rows
                    if c.get("maxCustomizeCount", 0) >= 2 and c.get("produceCardCustomizeIds"))
        cid = card["produceCardCustomizeIds"][0]
        rows = self.repository.load_table("ProduceCardCustomize").all(cid)
        if not any(r["customizeCount"] == 2 for r in rows):
            self.fail("Pinned customization fixture no longer has level two")
        memory["spec"]["produce_card"] = {"card_id": card["id"], "upgrade_count": card["upgradeCount"],
            "customize_ids": [cid, cid], "phase_type": "ProduceMemoryProduceCardPhaseType_ProduceStart"}
        observed = self.observe(memories=[memory], phase="memory_card")
        inherited = observed["entities"]["memory_options"][0]["inherited_card"]
        self.assertEqual(len(inherited["customize_order"]), 2)
        grows = inherited["effective_card"]["parameters"]["growEffectIds"]
        actual = {x["definition_ref"] for x in walk(grows) if isinstance(x, dict) and "definition_ref" in x}
        level_two = next(r for r in rows if r["customizeCount"] == 2)
        self.assertTrue(all("setup-definition:ProduceCardGrowEffect:" + x in actual
                            for x in level_two["produceCardGrowEffectIds"]))

    def test_history_independence_and_snapshots_do_not_mutate_caches(self):
        support = self.support()
        before = self.observe([support])
        self.observe([self.support("s_card-1-0000", 40)], [self.memory()])
        after = self.observe([support])
        self.assertEqual(before, after)
        after["entities"]["support_options"][0]["current_skills"].clear()
        self.assertEqual(before, self.observe([support]))
        encoder = DecisionEncoder()
        candidates = ({"type": "select_support", "support_ref": support["id"]},)
        encoded = encoder.encode(DecisionContext("full_produce", "setup_support", before, candidates))
        restored = DecisionEncoder(); restored.load_state_dict(encoder.state_dict())
        self.assertEqual(encoded, restored.encode(DecisionContext("full_produce", "setup_support", before, candidates)))
        compiler = _compiler(self.repository)
        memory = self.memory(); compiler.memory(memory)
        cache_size = len(compiler.memory_cache)
        renamed = copy.deepcopy(memory); renamed["id"] = "setup:memory:another"
        renamed["spec"]["memory_id"] = "different-physical-memory"
        compiler.memory(renamed)
        self.assertEqual(len(compiler.memory_cache), cache_size)

    def test_exact_level_and_unknown_effects_fail_loudly(self):
        with self.assertRaises(SemanticCoverageError):
            self.observe([self.support(level=61)])
        compiler = _compiler(self.repository)
        bad = dict(self.repository.produce_effects.rows[0], id="future-setup-effect",
                   produceEffectType="ProduceEffectType_UnknownFutureMechanism")
        with self.assertRaises(SemanticCoverageError):
            compiler.tree("ProduceEffect", bad)
        memory = self.memory(); memory["spec"]["ability_levels"] = (9999, *memory["spec"]["ability_levels"][1:])
        with self.assertRaises(SemanticCoverageError):
            self.observe(memories=[memory])

    def test_gradient_reaches_selected_support_effect_and_candidate_order(self):
        low, high = self.support(level=1, identity="setup:support:low"), self.support(identity="setup:support:high")
        observation = self.observe([low, high])
        candidates = tuple({"type": "select_support", "support_ref": row["id"]} for row in (low, high))
        context = DecisionContext("full_produce", "setup_support", observation, candidates)
        encoder = DecisionEncoder(); encoded = encoder.encode(context)
        torch.manual_seed(601)
        model = PolicyValueNet(ModelConfig(width=32, token_dim=16, layers=2, vocab_capacity=2048))
        batch = collate([encoded]); batch["feature_numbers"].requires_grad_(True)
        logits, _ = model(batch)
        self.assertGreater(abs(float((logits[0, 0] - logits[0, 1]).detach())), 1e-7)
        (logits[0, 1] - logits[0, 0]).backward()
        # Locate the high-level support's +17 effect under its own tree root.
        action = encoded.action_nodes[1]
        role = encoder.vocabulary.lookup["relation:references:support_ref"]
        entity = next(dst for src, dst, rel, _ in encoded.edges if src == action and rel == role)
        parent = {src: dst for src, dst, _, _ in encoded.tree_edges}
        def owned(node):
            while node in parent and node != entity:
                node = parent[node]
            return node == entity
        target_nodes = {i for i, features in enumerate(encoded.features) if owned(i)
                        and any(encoder.vocabulary.tokens[t] == "effectValueMin:number" and abs(n[1] - .017) < 1e-9
                                for t, n in features)}
        self.assertTrue(target_nodes)
        selected_features = torch.tensor([int(n) in target_nodes for n in batch["feature_nodes"]])
        self.assertGreater(float(batch["feature_numbers"].grad[selected_features].abs().sum()), 1e-10)
        swapped = DecisionContext(context.task, context.kind, observation, candidates[::-1])
        torch.testing.assert_close(model.evaluate([encoded]).logits.flip(1),
                                   model.evaluate([encoder.encode(swapped)]).logits, atol=1e-6, rtol=1e-5)

    def test_all_112_plan_one_supports_with_complex_memories_fit_and_backpropagate(self):
        from gakumas_rl.idol_config import memory_spec_from_gift
        levels = {"SupportCardRarity_Ssr": 60, "SupportCardRarity_Sr": 50, "SupportCardRarity_R": 40}
        supports = [self.support(r["id"], levels[r["rarity"]]) for r in self.repository.support_cards.rows
                    if r["planType"] in ("ProducePlanType_Plan1", "ProducePlanType_Common")]
        self.assertEqual(len(supports), 112)
        # Gift rows exercise real complex specimens; they are NOT an owned or
        # generated research inventory. The adapter independently masks plans.
        memories = [{"id": "setup:memory:" + row["id"], "memory_id": row["id"],
                     "spec": asdict(memory_spec_from_gift(self.repository, row["id"]))}
                    for row in self.repository.load_table("MemoryGift").rows]
        observation = self.observe(supports, memories)
        candidates = tuple({"type": "select_support", "support_ref": row["id"]} for row in supports)
        encoder = DecisionEncoder(); encoded = encoder.encode(DecisionContext("full_produce", "setup_support", observation, candidates))
        self.assertLess(encoded.node_count, 32768)
        self.assertEqual(len(encoded.action_nodes), 112)
        torch.manual_seed(604)
        model = PolicyValueNet(ModelConfig(width=16, token_dim=8, layers=2, vocab_capacity=2048))
        result = model.evaluate([encoded], [11])
        (-result.log_probs.mean() + result.values.square().mean() * .001).backward()
        self.assertTrue(torch.isfinite(result.logits).all())
        self.assertGreater(float(model.tree_message.weight.grad.abs().sum()), 0.)

    def test_real_research_components_all_variants_and_hif_choices(self):
        inventory = json.loads((Path(__file__).parents[1] / "colab/configs/research_inventory.json").read_text())
        components = inventory["memory_components"]
        self.assertEqual(len(components["hif_abilities"]), 105)
        self.assertEqual(len(components["gold_factors"]), 10)
        compiler = _compiler(self.repository)
        def record(value):
            return {"id": "setup:memory:" + value["memory_id"], **value}
        # Validate every generated variant's actual customized mechanism, not
        # merely its master ID; no Cartesian product with factors is formed.
        for component in components["cards"]:
            compiler.memory(record(component))
        self.assertLessEqual(len(compiler.memory_cache), 512)
        by_card = {}
        for value in components["cards"]:
            card = value["spec"]["produce_card"]
            row = self.repository.card_row_by_upgrade(card["card_id"], card["upgrade_count"])
            if row["planType"] in ("ProducePlanType_Plan1", "ProducePlanType_Common"):
                by_card.setdefault(card["card_id"], []).append(record(value))
        representatives = [min(rows, key=lambda r: len(r["spec"]["produce_card"]["customize_ids"]))
                           for rows in by_card.values()]
        support_rows = [self.support(sid, level) for sid, level in
                        zip(self.base["support_card_ids"], self.base["support_card_levels"])]
        partial = copy.deepcopy(representatives[0])
        partial.update(id="setup:memory:partial", memory_id="partial", assembly_phase="hif", slot=0)
        partial["spec"]["ability_ids"] = [components["hif_abilities"][0]["spec"]["ability_ids"][0],
                                           *[x["spec"]["ability_ids"][0] for x in components["gold_factors"][:3]]]
        partial["spec"]["ability_levels"] = [1] * 4
        groups = [("memory_card", representatives),
                  ("memory_hif", [record(v) for v in components["hif_abilities"]]),
                  ("memory_factor", [record(v) for v in components["gold_factors"]]),
                  *(('memory_variant', records) for records in by_card.values())]
        encoder, largest = DecisionEncoder(), None
        for phase, options in groups:
            observation = self.observe(support_rows, options, selected_supports=support_rows,
                                       selected_memories=[partial], phase=phase)
            context = DecisionContext("full_produce", "setup_" + phase, observation,
                tuple({"type": "select_memory", "memory_ref": row["id"]} for row in options))
            encoded = encoder.encode(context)
            self.assertLess(encoded.node_count, 32768)
            if largest is None or encoded.node_count > largest.node_count:
                largest = encoded
        torch.manual_seed(605)
        model = PolicyValueNet(ModelConfig(width=16, token_dim=8, layers=2, vocab_capacity=2048))
        result = model.evaluate([largest], [0])
        (-result.log_probs.mean()).backward()
        self.assertTrue(torch.isfinite(result.logits).all())
        self.assertGreater(float(model.tree_message.weight.grad.abs().sum()), 0.)


if __name__ == "__main__":
    unittest.main()
