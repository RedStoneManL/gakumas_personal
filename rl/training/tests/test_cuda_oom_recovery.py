"""CPU-injected CUDA OOMs test transactions without exhausting any GPU."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import random
import unittest
from unittest.mock import patch

import torch
from torch.distributions import Categorical

from gakumas_training.algorithms import PPOConfig, PPOUpdater
from gakumas_training.contracts import DecisionContext
from gakumas_training.encoding import DecisionEncoder
from gakumas_training.models import ModelConfig, PolicyRunner, PolicyValueNet
from test_ppo import TinyPolicy, make_episode


def consume_then_oom():
    random.random()
    torch.rand(7)
    raise torch.cuda.OutOfMemoryError("injected test allocation failure")


class OOMRecoveryTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(884)
        self.model = TinyPolicy()
        self.episodes = [make_episode(self.model, score=30+i, seed=i) for i in range(8)]
        self.output = io.StringIO()
        capture = redirect_stdout(self.output)
        capture.__enter__()
        self.addCleanup(capture.__exit__, None, None, None)

    def updater(self, model, micro=2):
        return PPOUpdater(model, PPOConfig(epochs=2, minibatch_size=4, microbatch_size=micro,
                                          target_kl=5., learning_rate=1e-4, normalize_advantage=False))

    def run_update(self, updater):
        random.seed(913)
        torch.manual_seed(271)
        result = updater.update(self.episodes, task="exam_score", policy_version=0, score_scale=10)
        return result, random.getstate(), torch.get_rng_state()

    def assert_same_update(self, reference, recovered, result_a, result_b):
        self.assertEqual(result_a["optimizer_steps"], result_b["optimizer_steps"])
        self.assertEqual(result_b["optimizer_steps"], 4)
        for name, value in reference.model.state_dict().items():
            torch.testing.assert_close(recovered.model.state_dict()[name], value, atol=2e-7, rtol=2e-6)
        for parameter, restored in zip(reference.model.parameters(), recovered.model.parameters(), strict=True):
            self.assertEqual(parameter.grad is None, restored.grad is None)
            if parameter.grad is not None:
                torch.testing.assert_close(restored.grad, parameter.grad, atol=2e-7, rtol=2e-6)
        first, second = reference.optimizer.state_dict(), recovered.optimizer.state_dict()
        for identity, values in first["state"].items():
            for name, value in values.items():
                torch.testing.assert_close(second["state"][identity][name], value, atol=2e-7, rtol=2e-6)
        self.assertEqual(result_a["decision_kinds"]["exam"]["optimization_samples"], 16)
        self.assertEqual(result_b["decision_kinds"]["exam"]["optimization_samples"], 16)
        self.assertAlmostEqual(result_a["decision_kinds"]["exam"]["behavior_normalized_entropy"],
                               result_b["decision_kinds"]["exam"]["behavior_normalized_entropy"], places=6)

    def test_parity_oom_shrinks_without_double_count_or_rng_change(self):
        normal = self.updater(deepcopy(self.model), micro=2)
        recovered = self.updater(deepcopy(self.model), micro=4)
        original = recovered.model.evaluate
        failed = False
        def injected(states, action_indices=None):
            nonlocal failed
            if not torch.is_grad_enabled() and len(states) > 2 and not failed:
                failed = True
                consume_then_oom()
            return original(states, action_indices)
        recovered.model.evaluate = injected
        a, python_a, torch_a = self.run_update(normal)
        b, python_b, torch_b = self.run_update(recovered)
        self.assert_same_update(normal, recovered, a, b)
        self.assertEqual(python_a, python_b)
        self.assertTrue(torch.equal(torch_a, torch_b))
        self.assertEqual(b["effective_microbatch_size"], 2)
        self.assertEqual(b["oom_fallback_count"], 1)
        self.assertEqual(b["oom_fallbacks"][0]["stage"], "behavior_parity")

    def test_forward_oom_after_prior_optimizer_step_retries_only_current_minibatch(self):
        normal = self.updater(deepcopy(self.model), micro=1)
        recovered = self.updater(deepcopy(self.model), micro=2)
        original = recovered.model.evaluate
        calls = 0
        def injected(states, action_indices=None):
            nonlocal calls
            if torch.is_grad_enabled():
                calls += 1
                if calls == 4:  # One completed step; one accumulated microbatch.
                    consume_then_oom()
            return original(states, action_indices)
        recovered.model.evaluate = injected
        a, python_a, torch_a = self.run_update(normal)
        b, python_b, torch_b = self.run_update(recovered)
        self.assert_same_update(normal, recovered, a, b)
        self.assertEqual(python_a, python_b)
        self.assertTrue(torch.equal(torch_a, torch_b))
        self.assertEqual(b["effective_microbatch_size"], 1)
        self.assertEqual(b["oom_fallbacks"][0]["minibatch_start"], 4)

    def test_backward_oom_discards_partial_parameter_gradients(self):
        normal = self.updater(deepcopy(self.model), micro=1)
        recovered = self.updater(deepcopy(self.model), micro=2)
        calls = 0
        def fail_backward(gradient):
            nonlocal calls
            calls += 1
            if calls == 4:
                consume_then_oom()
            return gradient
        handle = recovered.model.actor.weight.register_hook(fail_backward)
        self.addCleanup(handle.remove)
        a, python_a, torch_a = self.run_update(normal)
        b, python_b, torch_b = self.run_update(recovered)
        self.assert_same_update(normal, recovered, a, b)
        self.assertEqual(python_a, python_b)
        self.assertTrue(torch.equal(torch_a, torch_b))

    def test_micro_one_non_oom_and_optimizer_errors_are_not_silently_retried(self):
        for error in (torch.cuda.OutOfMemoryError("single graph too large"), RuntimeError("engine/model bug")):
            updater = self.updater(deepcopy(self.model), micro=1)
            with patch.object(updater.model, "evaluate", side_effect=error) as evaluate:
                with self.assertRaises(type(error)):
                    self.run_update(updater)
                self.assertEqual(evaluate.call_count, 1)
            self.assertEqual(len(updater.optimizer.state), 0)
        updater = self.updater(deepcopy(self.model), micro=2)
        with patch.object(updater.optimizer, "step", side_effect=torch.cuda.OutOfMemoryError("optimizer state allocation")) as step:
            with self.assertRaises(torch.cuda.OutOfMemoryError):
                self.run_update(updater)
            self.assertEqual(step.call_count, 1)
        self.assertFalse(updater.last_oom_fallbacks)

    def runners(self):
        model = PolicyValueNet(ModelConfig(width=16, token_dim=8, vocab_capacity=1024))
        return PolicyRunner(DecisionEncoder(), model), PolicyRunner(DecisionEncoder(), deepcopy(model))

    def contexts(self):
        return [DecisionContext("full_produce", "outer", {"resources": {"hp": i + 2}},
                                tuple({"type": "option", "value": j} for j in range(count)))
                for i, count in enumerate((5, 1, 3, 2))]

    def assert_same_sampling(self, normal, recovered):
        random.seed(812); torch.manual_seed(871)
        expected = normal.act_batch(self.contexts(), 19)
        expected_python, expected_torch = random.getstate(), torch.get_rng_state()
        random.seed(812); torch.manual_seed(871)
        actual = recovered.act_batch(self.contexts(), 19)
        self.assertEqual([s.action_index for s in actual], [s.action_index for s in expected])
        torch.testing.assert_close(torch.tensor([s.log_prob for s in actual]),
                                   torch.tensor([s.log_prob for s in expected]), atol=2e-5, rtol=0)
        torch.testing.assert_close(torch.tensor([s.value for s in actual]),
                                   torch.tensor([s.value for s in expected]), atol=2e-5, rtol=0)
        self.assertEqual(random.getstate(), expected_python)
        self.assertTrue(torch.equal(torch.get_rng_state(), expected_torch))
        self.assertTrue(all(0 <= s.action_index < len(c.candidates) for s, c in zip(actual, self.contexts())))

    def test_inference_oom_splits_forward_but_samples_full_wave_once_and_remembers_cap(self):
        normal, recovered = self.runners()
        original = recovered.model.evaluate
        calls = []
        def injected(states, action_indices=None):
            calls.append(len(states))
            if len(states) > 2:
                consume_then_oom()
            return original(states, action_indices)
        recovered.model.evaluate = injected
        self.assert_same_sampling(normal, recovered)
        self.assertEqual(calls, [4, 2, 2])
        self.assertEqual(recovered.effective_inference_batch_size, 2)
        self.assertEqual(recovered.timing_counters["oom_fallbacks"], 1)
        recovered.reset_timings()
        self.assertEqual(recovered.effective_inference_batch_size, 2)
        recovered.act_batch(self.contexts(), 20)
        self.assertEqual(calls[-2:], [2, 2])
        self.assertEqual(recovered.last_oom_fallbacks, [])

    def test_failure_after_one_successful_inference_chunk_does_not_sample_early(self):
        normal, recovered = self.runners()
        recovered.effective_inference_batch_size = 2
        original = recovered.model.evaluate
        calls = 0
        def injected(states, action_indices=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                consume_then_oom()
            return original(states, action_indices)
        recovered.model.evaluate = injected
        self.assert_same_sampling(normal, recovered)
        self.assertEqual(recovered.effective_inference_batch_size, 1)
        self.assertEqual(calls, 6)

    def test_inference_single_graph_and_non_oom_errors_propagate(self):
        _, runner = self.runners()
        for error in (torch.cuda.OutOfMemoryError("too large"), RuntimeError("unrelated bug")):
            with patch.object(runner.model, "evaluate", side_effect=error) as evaluate:
                with self.assertRaises(type(error)):
                    runner.act_batch(self.contexts()[:1])
                self.assertEqual(evaluate.call_count, 1)


if __name__ == "__main__":
    unittest.main()
