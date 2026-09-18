"""Native semantic compilation, not a second implementation of card rules."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE)]
from draftrl.native_semantics import (
    NativeSemantics, NativeSemanticsError, SemanticCacheMiss, operator_semantics,
)


def card(definition_id, customizations=None, growth=None):
    return {"definition_id": definition_id, "customizations": customizations or {}, "growth": growth or {}}


@unittest.skipUnless(shutil.which("node"), "Node is required for native semantic compilation")
class NativeSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = NativeSemantics()
        cls.dsl = "at:cardUsed { if:usedCard==7 { do:score+=10; do:score+=10 } }"
        cls.cards = [card(591), card(591, {"37": 1}), card(49), card(49, {"36": 1}), card(784)]
        cls.batch = cls.bridge.prepare(cards=cls.cards, programs=[cls.dsl])

    def test_remove_once_customization_is_visible_outside_program_ast(self):
        before, after = self.batch["cards"][:2]
        self.assertEqual(before["effective"], after["effective"])
        self.assertEqual(before["effective_traits"]["normal_post_use_zone"], "removed")
        self.assertEqual(after["effective_traits"]["normal_post_use_zone"], "discarded")
        self.assertEqual(after["effective_traits"]["effective_limit"], 0)
        self.assertEqual(after["effective_traits"]["base_limit"], 1)
        self.assertTrue(after["effective_traits"]["limit_removed_by_customization"])
        self.assertEqual(after["base_id"], 590)

    def test_initial_hand_uses_native_trait_composition(self):
        plain, guided, native = self.batch["cards"][2:]
        self.assertFalse(plain["effective_traits"]["force_initial_hand"])
        self.assertTrue(guided["effective_traits"]["force_initial_hand"])
        self.assertTrue(native["effective_traits"]["force_initial_hand"])

    def test_order_and_typed_binding_scope_are_not_flattened_or_executed(self):
        program = self.bridge.program(self.dsl)
        encoded = json.dumps(program)
        self.assertIn('"usedCard"', encoded)
        self.assertIn('"value": 7', encoded)
        self.assertEqual(encoded.count('"lhs": "score"'), 2)
        reversed_batch = self.bridge.prepare(programs=[
            "do:motivation+=3; do:score+=7",
            "do:score+=7; do:motivation+=3",
        ])["programs"]
        self.assertNotEqual(*reversed_batch)

    def test_batch_rng_and_cache_only_growth_overlay(self):
        self.assertEqual(self.batch["rng_calls_delta"], 0)
        self.assertEqual(self.batch["native_calls"], 1)
        with patch("draftrl.native_semantics.subprocess.run", side_effect=AssertionError("unexpected Node launch")):
            result = self.bridge.prepare(cards=[card(591, {"37": 1}, {"g.score": 17})], programs=[self.dsl])
            self.assertEqual(result["native_calls"], 0)
            self.assertEqual(result["cards"][0]["growth"], {"g.score": 17})
            # Returned structures must not mutate the semantic template cache.
            result["cards"][0]["effective"]["actions"].clear()
            self.assertTrue(self.bridge.card(card(591, {"37": 1}))["effective"]["actions"])

    def test_missing_hot_path_entries_fail_without_node(self):
        cold = NativeSemantics(node="missing-node-on-purpose")
        with patch("draftrl.native_semantics.subprocess.run", side_effect=AssertionError("unexpected Node launch")):
            with self.assertRaises(SemanticCacheMiss):
                cold.card(card(591))
            with self.assertRaises(SemanticCacheMiss):
                cold.program(self.dsl)

    def test_offline_cache_is_source_bound_and_usable_without_node(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "semantic-cache.json"
            self.bridge.dump(target)
            restored = NativeSemantics(node="missing-node-on-purpose", cache_path=target)
            self.assertEqual(restored.card(card(591)), self.bridge.card(card(591)))
            self.assertEqual(restored.program(self.dsl), self.bridge.program(self.dsl))
            data = json.loads(target.read_text(encoding="utf-8"))
            data["source_sha256"] = "stale"
            target.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(NativeSemanticsError, "version mismatch"):
                NativeSemantics(cache_path=target)

    def test_invalid_native_customization_and_unknown_growth_are_rejected(self):
        with self.assertRaisesRegex(NativeSemanticsError, "customization"):
            self.bridge.prepare(cards=[card(591, {"37": 2})])
        with self.assertRaisesRegex(NativeSemanticsError, "growth"):
            self.bridge.card(card(591, growth={"g.invented": 4}))
        with self.assertRaisesRegex(NativeSemanticsError, "temporary support"):
            self.bridge.card({**card(591), "temporary_support": {"level": 2}})

    def test_input_objects_are_not_mutated(self):
        request = card(591, {"37": 1}, {"g.score": 8})
        before = copy.deepcopy(request)
        self.bridge.prepare(cards=[request])
        self.assertEqual(request, before)


class OperatorSemanticTests(unittest.TestCase):
    def test_assignment_operator_and_fixed_resource_semantics_stay_distinct(self):
        score = operator_semantics("score", "+=")
        self.assertIn("concentration", score["reads"])
        self.assertIn("context.multipliers", score["reads"])
        self.assertFalse(operator_semantics("score", "*=")["resolved"])
        self.assertIn("motivation", operator_semantics("genki", "+=")["reads"])
        self.assertNotIn("motivation", operator_semantics("fixedGenki", "+=")["reads"])
        self.assertTrue(operator_semantics("invented", "+=")["unresolved"])


if __name__ == "__main__":
    unittest.main()
