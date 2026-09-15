"""Meaningful learning/likelihood boundaries, using a tiny deterministic task."""
from dataclasses import replace
import math
from types import SimpleNamespace
import unittest

import torch
from torch import nn

from gakumas_training.algorithms import PPOConfig, PPOUpdater
from gakumas_training.contracts import DecisionContext, Episode, PolicySelection, Transition


class TinyPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.actor = nn.Linear(2, 2)
        self.critic = nn.Linear(2, 1)

    def evaluate(self, encoded_list, action_indices=None):
        x = torch.tensor(encoded_list, device=self.actor.weight.device, dtype=torch.float32)
        logits = self.actor(x)
        dist = torch.distributions.Categorical(logits=logits)
        actions = None if action_indices is None else torch.as_tensor(action_indices, device=x.device)
        return SimpleNamespace(logits=logits, values=self.critic(x).squeeze(-1),
            log_probs=None if actions is None else dist.log_prob(actions), entropy=dist.entropy())


def make_episode(model, task="exam_score", version=0, score=30., seed=0):
    encoded = [1., float(seed % 3)]
    ev = model.evaluate([encoded], [1])
    context = DecisionContext(task, "exam", {"public": seed % 3}, ({"a": 0}, {"a": 1}))
    selection = PolicySelection(1, float(ev.log_probs.detach()[0]), float(ev.values.detach()[0]), version, encoded)
    return Episode(task, seed, [Transition(context, selection)], score, "failed")


class PPOTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(31)
        self.model = TinyPolicy()

    def test_policy_and_value_update_on_failed_episode_with_raw_score_target(self):
        episode = make_episode(self.model, score=30.)
        cfg = PPOConfig(epochs=1, learning_rate=.005, normalize_advantage=False,
                        entropy_coefficient=0, value_coefficient=.5)
        before = {k: v.clone() for k, v in self.model.state_dict().items()}
        before_ev = self.model.evaluate([[1., 0.]], [1])
        expected_value_loss = torch.nn.functional.smooth_l1_loss(before_ev.values, torch.tensor([3.])).item()
        result = PPOUpdater(self.model, cfg).update([episode], task="exam_score", policy_version=0, score_scale=10)
        self.assertAlmostEqual(result["value_loss"], expected_value_loss, places=6)
        self.assertGreater(self.model.evaluate([[1., 0.]], [1]).log_probs.item(), before_ev.log_probs.item())
        self.assertTrue(any(not torch.equal(before[k], v) for k, v in self.model.state_dict().items() if k.startswith("critic")))
        self.assertEqual(result["optimizer_steps"], 1)
        self.assertEqual(result["gamma"], 1)

    def test_mixed_task_and_stale_version_rejected_before_mutation(self):
        updater = PPOUpdater(self.model)
        original = {k: v.clone() for k, v in self.model.state_dict().items()}
        for episode in (make_episode(self.model, task="full_produce"), make_episode(self.model, version=1)):
            with self.assertRaises(ValueError):
                updater.update([episode], task="exam_score", policy_version=0, score_scale=10)
        self.assertTrue(all(torch.equal(original[k], v) for k, v in self.model.state_dict().items()))
        self.assertEqual(len(updater.optimizer.state), 0)

    def test_behavior_probability_mismatch_rejected(self):
        episode = make_episode(self.model)
        transition = episode.transitions[0]
        episode.transitions[0] = replace(transition, selection=replace(transition.selection, log_prob=-99.))
        with self.assertRaisesRegex(ValueError, "likelihood mismatch"):
            PPOUpdater(self.model).update([episode], task="exam_score", policy_version=0, score_scale=10)

    def test_nonfinite_scores_are_not_converted_to_zero(self):
        for score in (math.nan, math.inf):
            with self.assertRaises(ValueError):
                PPOUpdater(self.model).update([make_episode(self.model, score=score)],
                    task="exam_score", policy_version=0, score_scale=10)

    def test_microbatch_accumulation_matches_full_minibatch(self):
        import copy
        first, second = copy.deepcopy(self.model), copy.deepcopy(self.model)
        episodes = [make_episode(first, score=30 + i, seed=i) for i in range(4)]
        common = dict(epochs=1, minibatch_size=4, normalize_advantage=False, entropy_coefficient=.01)
        import random
        random.seed(7)
        PPOUpdater(first, PPOConfig(microbatch_size=1, **common)).update(episodes,
            task="exam_score", policy_version=0, score_scale=10)
        random.seed(7)
        PPOUpdater(second, PPOConfig(microbatch_size=4, **common)).update(episodes,
            task="exam_score", policy_version=0, score_scale=10)
        for key, value in first.state_dict().items():
            torch.testing.assert_close(value, second.state_dict()[key], atol=1e-7, rtol=1e-6)

    def test_setup_entropy_bonus_moves_policy_toward_uniform_without_random_actions(self):
        import copy
        with torch.no_grad():
            self.model.actor.weight.zero_()
            self.model.actor.bias.copy_(torch.tensor([2., -2.]))
            self.model.critic.weight.zero_()
            self.model.critic.bias.zero_()
        weak, strong = copy.deepcopy(self.model), copy.deepcopy(self.model)
        episode = make_episode(self.model, score=0.)
        transition = episode.transitions[0]
        episode.transitions[0] = replace(transition,
            decision=replace(transition.decision, kind='setup_support'))
        initial = self.model.evaluate([[1., 0.]]).entropy.item()
        metrics = []
        for model, coefficient in ((weak, .01), (strong, .05)):
            config = PPOConfig(epochs=1, entropy_coefficient=.01,
                setup_entropy_coefficient=coefficient, value_coefficient=0, normalize_advantage=False)
            # SGD makes the relationship between bonus coefficient and entropy
            # gradient magnitude visible without Adam's adaptive normalization.
            optimizer = torch.optim.SGD(model.parameters(), lr=.1)
            metrics.append(PPOUpdater(model, config, optimizer).update([episode],
                task='exam_score', policy_version=0, score_scale=10))
        self.assertGreater(weak.evaluate([[1., 0.]]).entropy.item(), initial)
        self.assertGreater(strong.evaluate([[1., 0.]]).entropy.item(), weak.evaluate([[1., 0.]]).entropy.item())
        self.assertEqual(metrics[1]['policy_loss'], 0.)
        self.assertEqual(metrics[1]['behavior_parity_max_error'], 0.)
        kind = metrics[1]['decision_kinds']['setup_support']
        self.assertEqual(kind['entropy_coefficient'], .05)
        self.assertAlmostEqual(kind['behavior_normalized_entropy'], initial / math.log(2), places=6)
        self.assertEqual(kind['candidate_count_mean'], 2)
        self.assertEqual(kind['rollout_samples'], 1)
        self.assertEqual(kind['optimization_samples'], 1)

    def test_no_setup_updates_are_bitwise_equal_for_different_setup_coefficients(self):
        import copy
        import random
        first, second = copy.deepcopy(self.model), copy.deepcopy(self.model)
        episodes = [make_episode(first, score=30 + i, seed=i) for i in range(4)]
        for model, coefficient in ((first, 0), (second, .5)):
            random.seed(19)
            PPOUpdater(model, PPOConfig(epochs=2, minibatch_size=4,
                setup_entropy_coefficient=coefficient)).update(episodes,
                    task='exam_score', policy_version=0, score_scale=10)
        for key, value in first.state_dict().items():
            torch.testing.assert_close(value, second.state_dict()[key], atol=0, rtol=0)

    def test_setup_behavior_mismatch_and_invalid_entropy_coefficient_rejected(self):
        episode = make_episode(self.model)
        transition = episode.transitions[0]
        episode.transitions[0] = replace(transition, decision=replace(transition.decision, kind='setup_memory'),
            selection=replace(transition.selection, log_prob=-99.))
        with self.assertRaisesRegex(ValueError, 'likelihood mismatch'):
            PPOUpdater(self.model).update([episode], task='exam_score', policy_version=0, score_scale=10)
        for coefficient in (-1., math.nan, math.inf):
            with self.assertRaises(ValueError):
                PPOConfig(setup_entropy_coefficient=coefficient)


if __name__ == "__main__":
    unittest.main()
