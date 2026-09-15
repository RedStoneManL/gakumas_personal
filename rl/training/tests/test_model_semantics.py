import copy
import unittest
import torch

from gakumas_training.contracts import DecisionContext
from gakumas_training.encoding import DecisionEncoder, SemanticCoverageError
from gakumas_training.models import ModelConfig, PolicyRunner, PolicyValueNet


def exam_context(values=(3, 90)):
    def card(i, value):
        return {"instance_id": f"copy:{i}", "definition_id": i,
                "effective": {"actions": [{"actions": [{"type": "assignment", "lhs": "score", "op": "+=",
                    "rhs": {"type": "number", "value": value}}]}]}}
    return DecisionContext("exam_score", "exam_action", {"exam": {
        "schema_version": "arena-public-exam/1", "observation_scope": "public",
        "state": {"stamina": 7}, "cards": [card(i, v) for i, v in enumerate(values)],
        "definitions": {"cards": [{"id": i, "type": "active"} for i in range(len(values))],
                        "drinks": [], "p_items": []}, "drinks": [],
        "zones": {"hand": [f"copy:{i}" for i in range(len(values))]},
    }}, tuple({"type": "play", "instance_id": f"copy:{i}"} for i in range(len(values))))


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        torch.manual_seed(20260910)
        self.encoder = DecisionEncoder()
        self.model = PolicyValueNet(ModelConfig(width=32, layers=2, vocab_capacity=2048))

    def test_deep_effect_values_reach_candidate_and_permute(self):
        context = exam_context()
        first = self.encoder.encode(context)
        logits = self.model.evaluate([first]).logits
        self.assertGreater(abs(float((logits[0, 0]-logits[0, 1]).detach())), 1e-7)
        reversed_candidates = DecisionContext(context.task, context.kind, context.observation, context.candidates[::-1])
        reversed_logits = self.model.evaluate([self.encoder.encode(reversed_candidates)]).logits
        torch.testing.assert_close(logits.flip(1), reversed_logits, atol=1e-6, rtol=1e-5)
        # Swapping the complete card mechanisms must swap the corresponding scores,
        # even though the action payloads have not changed.
        swapped = self.model.evaluate([self.encoder.encode(exam_context((90, 3)))]).logits
        # Hand positions are public semantics; erase them for this symmetry check.
        plain_a = exam_context(); plain_b = exam_context((90, 3))
        plain_a.observation["exam"]["zones"] = {}; plain_b.observation["exam"]["zones"] = {}
        a = self.model.evaluate([self.encoder.encode(plain_a)]).logits
        b = self.model.evaluate([self.encoder.encode(plain_b)]).logits
        torch.testing.assert_close(a.flip(1), b, atol=1e-6, rtol=1e-5)

    def test_masked_batch_probabilities_gradients_and_runner_agree(self):
        contexts = [exam_context((3, 90)), exam_context((5,))]
        encoded = [self.encoder.encode(x) for x in contexts]
        result = self.model.evaluate(encoded, [0, 0])
        self.assertTrue(torch.isneginf(result.logits[1, 1]))
        self.assertEqual(float(result.log_probs[1].detach()), 0.)
        (-result.log_probs.mean()+result.values.square().mean()).backward()
        self.assertGreater(float(self.model.tree_message.weight.grad.abs().sum()), 0)
        runner = PolicyRunner(self.encoder, self.model)
        selected = runner.act(contexts[0], policy_version=4)
        reevaluated = self.model.evaluate([selected.encoded], [selected.action_index])
        self.assertAlmostEqual(selected.log_prob, float(reevaluated.log_probs[0].detach()), places=6)
        self.assertEqual(runner.timing_counters["decisions"], 1)

    def test_identity_rename_checkpoint_and_unknown_operation(self):
        context = exam_context()
        original = self.encoder.encode(context)
        renamed = copy.deepcopy(context)
        for i, card in enumerate(renamed.observation["exam"]["cards"]):
            card["instance_id"] = f"renamed:{i}"
            renamed.candidates[i]["instance_id"] = f"renamed:{i}"
        renamed.observation["exam"]["zones"]["hand"] = ["renamed:0", "renamed:1"]
        other = self.encoder.encode(renamed)
        torch.testing.assert_close(self.model.evaluate([original]).logits, self.model.evaluate([other]).logits)
        restored = DecisionEncoder(); restored.load_state_dict(self.encoder.state_dict())
        self.assertEqual(restored.encode(context), original)
        bad = exam_context()
        bad.observation["exam"]["cards"][0]["effective"]["actions"][0]["actions"][0]["type"] = "future_opaque_effect"
        with self.assertRaises(SemanticCoverageError):
            self.encoder.encode(bad)

    def test_missing_zero_null_and_integer_dict_keys(self):
        def encode(resources):
            return self.encoder.encode(DecisionContext("full_produce", "outer", {"resources": resources}, ({"type": "rest"},)))
        self.assertNotEqual(encode({}), encode({"hp": 0}))
        self.assertNotEqual(encode({"hp": None}), encode({"hp": 0}))
        self.assertNotEqual(encode({1: 7}), encode({"1": 7}))
        encode({1: 7, "a": 2})


if __name__ == "__main__":
    unittest.main()
