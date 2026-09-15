import copy
from dataclasses import replace
import gc
import json
from pathlib import Path
import pickle
import unittest
from unittest.mock import patch
import weakref

import torch
from torch.distributions import Categorical

from gakumas_training.contracts import DecisionContext
from gakumas_training.encoding import DecisionEncoder, collate, SemanticCoverageError
from gakumas_training.encoding import graph
from gakumas_training.models import ModelConfig, PolicyRunner, PolicyValueNet


def context(count=3, value=4):
    return DecisionContext("full_produce", "outer", {"resources": {"hp": value}},
                           tuple({"type": "option", "value": i * value} for i in range(count)))


def reference_collate(examples):
    """Original un-cached packing contract, retained to detect storage drift."""
    columns = {name: [] for name in ("feature_tokens", "feature_numbers", "feature_nodes", "edge_src",
        "edge_dst", "edge_roles", "edge_positions", "tree_src", "tree_dst", "tree_roles", "tree_positions",
        "tree_depths", "node_batches")}
    offset, actions = 0, []
    for batch, example in enumerate(examples):
        for node, features in enumerate(example.features):
            for token, numbers in features:
                columns["feature_tokens"].append(token)
                columns["feature_numbers"].append(numbers)
                columns["feature_nodes"].append(offset + node)
        for prefix, edges in (("edge", example.edges), ("tree", example.tree_edges)):
            for src, dst, role, position in edges:
                columns[prefix + "_src"].append(offset + src)
                columns[prefix + "_dst"].append(offset + dst)
                columns[prefix + "_roles"].append(role)
                columns[prefix + "_positions"].append(position)
                if prefix == "tree":
                    columns["tree_depths"].append(example.depths[src])
        actions.append([offset + node for node in example.action_nodes])
        columns["node_batches"].extend([batch] * example.node_count)
        offset += example.node_count
    result = {name: torch.tensor(values, dtype=torch.float32 if name in
        ("feature_numbers", "edge_positions", "tree_positions") else torch.long) for name, values in columns.items()}
    result.update(action_indices=torch.zeros((len(examples), max(map(len, actions))), dtype=torch.long))
    result["mask"] = torch.zeros_like(result["action_indices"], dtype=torch.bool)
    for batch, values in enumerate(actions):
        result["action_indices"][batch, :len(values)] = torch.tensor(values)
        result["mask"][batch, :len(values)] = True
    result.update(max_depth=max(columns["tree_depths"], default=0), node_count=offset, batch_size=len(examples))
    return result


class BatchPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        torch.manual_seed(7102)
        self.runner = PolicyRunner(DecisionEncoder(), PolicyValueNet(ModelConfig(width=32, vocab_capacity=2048)))
        self.contexts = [context(5, 8), context(1, 2), context(3, 7)]

    def test_order_deterministic_single_batch_and_mask(self):
        with patch.object(self.runner.model, "evaluate", wraps=self.runner.model.evaluate) as evaluate:
            selections = self.runner.act_batch(self.contexts, 17, deterministic=True)
            self.assertEqual(evaluate.call_count, 1)
        singles = [self.runner.act(c, 17, deterministic=True) for c in self.contexts]
        self.assertEqual([x.action_index for x in selections], [x.action_index for x in singles])
        for i, (batch, single) in enumerate(zip(selections, singles)):
            self.assertEqual(batch.policy_version, 17)
            self.assertEqual(batch.encoded, single.encoded)
            self.assertLessEqual(abs(batch.log_prob - single.log_prob), 2e-5)
            self.assertLessEqual(abs(batch.value - single.value), 2e-5)
            self.assertLess(batch.action_index, len(self.contexts[i].candidates))
        self.assertEqual(selections[1].action_index, 0)
        self.assertEqual(selections[1].log_prob, 0.)
        self.assertEqual(self.runner.timing_counters["decisions"], 6)
        self.assertEqual(self.runner.timing_counters["inference_batches"], 4)
        before = dict(self.runner.timing_counters)
        self.assertEqual(self.runner.act_batch([], 17), [])
        self.assertEqual(self.runner.timing_counters, before)

    def test_sampled_log_probs_are_actual_masked_distribution_and_backward(self):
        selected = self.runner.act_batch(self.contexts, 4)
        states, actions = [x.encoded for x in selected], [x.action_index for x in selected]
        evaluation = self.runner.model.evaluate(states, actions)
        exact = Categorical(logits=evaluation.logits).log_prob(torch.tensor(actions))
        torch.testing.assert_close(torch.tensor([x.log_prob for x in selected]), exact, atol=2e-5, rtol=0)
        self.assertTrue(torch.isneginf(evaluation.logits[1, 1:]).all())
        (-evaluation.log_probs.mean() + .01 * evaluation.values.square().mean()).backward()
        gradients = [p.grad for p in self.runner.model.parameters() if p.grad is not None]
        self.assertTrue(all(torch.isfinite(g).all() for g in gradients))
        self.assertGreater(sum(float(g.abs().sum()) for g in gradients), 0.)

    def test_single_act_retains_rng_behavior(self):
        state = torch.get_rng_state()
        one = self.runner.act(self.contexts[0], 1)
        torch.set_rng_state(state)
        batch = self.runner.act_batch([self.contexts[0]], 1)[0]
        self.assertEqual(one, batch)

    def test_cached_collate_is_exact_and_batch_mutations_do_not_poison_cache(self):
        examples = [self.runner.encoder.encode(c) for c in self.contexts]
        reference = reference_collate(examples)
        for packed in (collate(examples), collate(examples), collate([pickle.loads(pickle.dumps(x)) for x in examples])):
            for key, value in reference.items():
                if torch.is_tensor(value):
                    torch.testing.assert_close(packed[key], value, atol=0, rtol=0)
                else:
                    self.assertEqual(packed[key], value)
        damaged = collate(examples)
        damaged["feature_numbers"].fill_(999)
        damaged["edge_src"].zero_()
        fresh = collate(examples)
        torch.testing.assert_close(fresh["feature_numbers"], reference["feature_numbers"], atol=0, rtol=0)
        torch.testing.assert_close(fresh["edge_src"], reference["edge_src"], atol=0, rtol=0)
        with self.assertRaises(SemanticCoverageError):
            collate([replace(examples[0], schema_version="future")])

    def test_cache_weak_ownership_and_byte_budget(self):
        graph._clear_collate_cache()
        example = self.runner.encoder.encode(context())
        ref = weakref.ref(example)
        batch = collate([example])
        self.assertEqual(graph._collate_cache_info()["entries"], 1)
        del example
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(graph._collate_cache_info()["entries"], 0)
        self.assertTrue(torch.isfinite(batch["feature_numbers"]).all())
        with patch.object(graph, "_COLLATE_CACHE_LIMIT_BYTES", 1):
            example = self.runner.encoder.encode(context())
            collate([example])
            self.assertEqual(graph._collate_cache_info()["bytes"], 0)

    def test_precomputed_topology_matches_dynamic_groups_and_gradients(self):
        from gakumas_training.models.policy import _tree_groups
        examples = [self.runner.encoder.encode(c) for c in self.contexts]
        fast = collate(examples)
        legacy = {k: v for k, v in fast.items() if k not in ("tree_levels", "node_slices")}
        old_groups = list(_tree_groups(legacy))
        self.assertEqual(len(fast["tree_levels"]), len(old_groups))
        for current, (mask, children, parents, inverse) in zip(fast["tree_levels"], old_groups):
            expected = (mask.nonzero().flatten(), children, parents, inverse)
            for actual, value in zip(current, expected):
                torch.testing.assert_close(actual, value, atol=0, rtol=0)
        for batch, (start, end) in enumerate(fast["node_slices"]):
            torch.testing.assert_close(torch.arange(start, end), (fast["node_batches"] == batch).nonzero().flatten())
        model = self.runner.model
        old_logits, old_values = model(legacy)
        old_loss = -Categorical(logits=old_logits).log_prob(torch.zeros(len(examples), dtype=torch.long)).mean() + old_values.square().mean()
        old_loss.backward()
        old_gradients = {name: p.grad.clone() for name, p in model.named_parameters() if p.grad is not None}
        model.zero_grad(set_to_none=True)
        logits, values = model(fast)
        loss = -Categorical(logits=logits).log_prob(torch.zeros(len(examples), dtype=torch.long)).mean() + values.square().mean()
        loss.backward()
        torch.testing.assert_close(logits, old_logits, atol=0, rtol=0)
        torch.testing.assert_close(values, old_values, atol=0, rtol=0)
        for name, parameter in model.named_parameters():
            if name in old_gradients:
                torch.testing.assert_close(parameter.grad, old_gradients[name], atol=0, rtol=0)
        # The optimization adds no weights, buffers or checkpoint fields.
        restored = PolicyValueNet(model.config)
        restored.load_state_dict(copy.deepcopy(model.state_dict()), strict=True)
        torch.testing.assert_close(restored(fast)[0], logits, atol=0, rtol=0)

    @unittest.skipUnless(torch.cuda.is_available(), "Requires GPU parity check")
    def test_real_setup_and_exam_batch_four_matches_ppo_microbatch_two(self):
        from gakumas_training.arena_adapter.environment import ensure_arena, close_arena
        ensure_arena()
        from gakumas_arena.env import get_repository
        from gakumas_arena.engine.training import TrainingExam, hif_round2_entry
        from gakumas_training.arena_adapter.setup_observation import prepare_setup_observation
        repository = get_repository()
        config_path = Path(__file__).parents[1] / "colab/configs/full_produce.json"
        if not config_path.is_file():
            config_path = Path(__file__).parents[2] / "configs/full_produce.json"
        cfg = json.loads(config_path.read_text())["task_config"]["loadout"]
        levels = {"SupportCardRarity_Ssr": 60, "SupportCardRarity_Sr": 50, "SupportCardRarity_R": 40}
        supports = [{"id": "setup:support:" + r["id"], "support_card_id": r["id"], "level": levels[r["rarity"]]}
                    for r in repository.support_cards.rows if r["planType"] in ("ProducePlanType_Plan1", "ProducePlanType_Common")]
        contexts = []
        for slot in (0, 1):
            observation = prepare_setup_observation(repository, base_loadout=cfg, support_options=supports,
                memory_options=[], selected_supports=supports[:slot], selected_memories=[], phase="support", slot=slot, rules={})
            contexts.append(DecisionContext("full_produce", "setup_support", observation,
                tuple({"type": "select_support", "support_ref": row["id"]} for row in supports[slot:])))
        try:
            for seed in (719, 720):
                exam = TrainingExam(hif_round2_entry(), seed=seed)
                observation = exam.observe()
                contexts.append(DecisionContext("exam_score", "exam_action", {"exam": observation},
                                               tuple(copy.deepcopy(observation["actions"]))))
            model = PolicyValueNet(ModelConfig()).cuda()
            runner = PolicyRunner(DecisionEncoder(), model)
            chosen = runner.act_batch(contexts, 21)
            self.assertGreater(chosen[0].encoded.node_count, 20000)
            states, indices = [x.encoded for x in chosen], [x.action_index for x in chosen]
            micro = torch.cat([model.evaluate(states[i:i+2], indices[i:i+2]).log_probs
                               for i in (0, 2)])
            recorded = torch.tensor([x.log_prob for x in chosen], device="cuda")
            self.assertLessEqual(float((micro - recorded).abs().max().detach()), 2e-5)
            singles = torch.cat([model.evaluate([state], [index]).log_probs for state, index in zip(states, indices)])
            self.assertLessEqual(float((singles - recorded).abs().max().detach()), 2e-5)
            greedy_batch = runner.act_batch(contexts, 21, deterministic=True)
            greedy_single = [runner.act(c, 21, deterministic=True) for c in contexts]
            self.assertEqual([x.action_index for x in greedy_batch], [x.action_index for x in greedy_single])
            # PPO's actual microbatch shape performs a real backward on large
            # setup graphs with the recorded behavior probabilities unchanged.
            model.zero_grad(set_to_none=True)
            (-micro.mean()).backward()
            self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
            self.assertGreater(float(model.tree_message.weight.grad.abs().sum()), 0.)
        finally:
            close_arena()


if __name__ == "__main__":
    unittest.main()
