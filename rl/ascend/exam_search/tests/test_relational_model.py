"""CPU representation/migration checks; no simulator or training job is started."""
import copy
import sys
import unittest
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'runtime' / 'shared')]

from round2rl.encoding import Encoded, flatten, collate as typed_collate
from draftrl.model import DraftPolicy
from draftrl.relational_model import NODE_TYPES, PHASE_NAMES


def encoded(nodes, edges, actions, phase):
    atoms = [(i, path, kind, text, number) for i, node in enumerate(nodes)
             for path, kind, text, number in flatten(node)]
    result = Encoded(atoms, edges, len(nodes), actions,
                     [{'method': 'act', 'test_action': i} for i in range(len(actions))])
    result.phase = phase
    return result


def examples(phase, action_count=2):
    nodes = [{'entity_type': 'global', 'score': 17 + phase},
             {'entity_type': 'card', 'effective': {'actions': [{'op': 'score', 'amount': 3}]}}]
    old_actions = []
    for i in range(action_count):
        old_actions.append(len(nodes))
        nodes.append({'entity_type': 'candidate', 'index': i})
    old = encoded(nodes, [(1, i, 'target') for i in old_actions], old_actions, phase)
    side_nodes = [{'entity_type': name, 'amount': i + phase,
                   'program': {'actions': [{'op': 'increase', 'amount': i},
                                           {'op': 'consume', 'amount': i + 1}]}}
                  for i, name in enumerate(NODE_TYPES)]
    types = list(range(len(NODE_TYPES)))
    side_actions = [11]
    for i in range(action_count - 1):
        side_actions.append(len(side_nodes))
        side_nodes.append({'entity_type': 'candidate', 'index': i + 1})
        types.append(11)
    edges = [(i, (i + 1) % len(side_nodes), 'reads:resource') for i in range(len(side_nodes))]
    edges += [(b, a, 'read_by:resource') for a, b, _ in edges]
    side = encoded(side_nodes, edges, side_actions, phase)
    return old, side, types


def batch(phases=(0, 1, 2, 3, 4), counts=None):
    counts = counts or [2] * len(phases)
    triples = [examples(p, n) for p, n in zip(phases, counts)]
    old = typed_collate([row[0] for row in triples])
    side = typed_collate([row[1] for row in triples])
    for b in (old, side):
        b['phase'] = torch.tensor(phases)
        b['drink_phase'] = b['phase'] == 1
        if len(set(phases)) == 1:
            b['uniform_phase'] = phases[0]
    side['node_types'] = torch.tensor([t for row in triples for t in row[2]])
    old['relational'] = side
    return old, triples


def models(quantiles=32):
    torch.manual_seed(707)
    old = DraftPolicy(width=16, lexical=4, depth=2, quantiles=quantiles)
    new = DraftPolicy(width=16, lexical=4, depth=2, quantiles=quantiles, relational=True)
    result = new.load_state_dict(old.state_dict(), strict=False)
    assert not result.unexpected_keys
    assert all(k.startswith(('actor_relational.', 'critic_relational.')) for k in result.missing_keys)
    return old, new


class RelationalModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_zero_residual_preserves_all_phases_and_legacy_tensors(self):
        old, new = models()
        for name, value in old.state_dict().items():
            self.assertTrue(torch.equal(value, new.state_dict()[name]), name)
        for phases, counts in [((0, 1, 2, 3, 4), [1, 2, 3, 2, 1]), ((0, 0), [2, 3])]:
            b, _ = batch(phases, counts)
            with torch.no_grad():
                old_outputs = old.learning_forward(b)
                new_outputs = new.learning_forward(b)
                for before, after in zip(old_outputs, new_outputs):
                    self.assertTrue(torch.equal(before, after))
                logits, value, atoms = new.search_forward(b)
                self.assertTrue(torch.equal(logits, new_outputs[0]))
                self.assertTrue(torch.equal(value, new_outputs[1]))
                self.assertTrue(torch.equal(atoms, new_outputs[2].sort(-1).values))
                f_logits, f_value = new(b)
                self.assertTrue(torch.equal(f_logits, logits))
                self.assertTrue(torch.equal(f_value, value))

    def test_every_semantic_module_receives_gradient_after_output_warmup(self):
        _, model = models()
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(name.startswith(('actor_relational.', 'critic_relational.')))
        optimizer = torch.optim.SGD([p for p in model.parameters() if p.requires_grad], lr=0.03)
        b, _ = batch()
        for step in range(2):
            optimizer.zero_grad(set_to_none=True)
            logits, values, quantiles = model.learning_forward(b)
            loss = -logits.log_softmax(-1)[:, 0].mean() + (values - 2).square().mean()
            loss = loss + (quantiles - 1).square().mean()
            loss.backward()
            if step == 0:
                for name in PHASE_NAMES:
                    grad = model.actor_relational.policy_heads[name][-1].weight.grad
                    self.assertIsNotNone(grad)
                    self.assertGreater(float(grad.abs().sum()), 0)
                optimizer.step()
        for branch in (model.actor_relational, model.critic_relational):
            stem = branch.encoder.stem
            for name in ('program_encoder', 'state_encoder', 'event_encoder', 'time_encoder',
                         'zone_encoder', 'constraint_encoder'):
                gradients = [p.grad for p in getattr(stem, name).parameters() if p.grad is not None]
                self.assertGreater(sum(float(g.abs().sum()) for g in gradients), 0, name)
            for name, adapter in stem.type_adapters.items():
                gradients = [p.grad for p in adapter.parameters() if p.grad is not None]
                self.assertGreater(sum(float(g.abs().sum()) for g in gradients), 0, name)
            for name, tower in branch.encoder.towers.items():
                grad = tower.blocks[0].gate.weight.grad
                self.assertIsNotNone(grad, name)
                self.assertGreater(float(grad.abs().sum()), 0, name)
        self.assertGreater(float(model.actor_relational.candidate_query.query.weight.grad.abs().sum()), 0)

    def test_forward_paths_call_each_residual_branch_once(self):
        _, model = models()
        b, _ = batch((0,))
        calls = {'actor': 0, 'critic': 0}
        def hook(name):
            def record(*args):
                calls[name] += 1
            return record
        ah = model.actor_relational.register_forward_hook(hook('actor'))
        ch = model.critic_relational.register_forward_hook(hook('critic'))
        try:
            for operation in (model.learning_forward, model.search_forward, model.forward):
                calls.update(actor=0, critic=0)
                operation(b)
                self.assertEqual(calls, {'actor': 1, 'critic': 1})
        finally:
            ah.remove()
            ch.remove()

    def test_parameters_are_independent_and_missing_sideview_fails(self):
        _, model = models()
        old_ids = {id(p) for p in model.actor.parameters()} | {id(p) for p in model.critic.parameters()}
        a_ids = {id(p) for p in model.actor_relational.parameters()}
        c_ids = {id(p) for p in model.critic_relational.parameters()}
        self.assertFalse(old_ids & (a_ids | c_ids))
        self.assertFalse(a_ids & c_ids)
        b, _ = batch((0,))
        del b['relational']
        with self.assertRaisesRegex(ValueError, 'side view'):
            model.policy(b)

    def test_candidate_mask_phase_and_type_checks(self):
        _, model = models()
        b, _ = batch((0,))
        broken = copy.deepcopy(b)
        broken['relational']['mask'][0, 0] = False
        with self.assertRaisesRegex(ValueError, 'mask'):
            model.policy(broken)
        broken = copy.deepcopy(b)
        broken['relational']['phase'][0] = 2
        with self.assertRaisesRegex(ValueError, 'phase'):
            model.value_outputs(broken)
        broken = copy.deepcopy(b)
        broken['relational']['node_types'][0] = len(NODE_TYPES)
        with self.assertRaisesRegex(ValueError, 'node type'):
            model.policy(broken)

    def test_late_quantiles_keep_shape_and_zero_residual(self):
        old, model = models(quantiles=0)
        old.enable_quantiles(32)
        model.enable_quantiles(32)
        b, _ = batch((0,))
        with torch.no_grad():
            before = old.value_outputs(b)
            after = model.value_outputs(b)
        self.assertEqual(after[1].shape, (1, 32))
        for a, z in zip(before, after):
            self.assertTrue(torch.equal(a, z))

    def test_unordered_side_entity_permutation_preserves_output(self):
        _, model = models()
        # Nonzero output projections ensure this checks the new path, not only zeros.
        with torch.no_grad():
            for heads in (model.actor_relational.policy_heads, model.critic_relational.value_heads):
                for head in heads.values():
                    head[-1].weight.normal_(std=0.02)
            model.critic_relational.quantile_head[-1].weight.normal_(std=0.02)
        b, triples = batch((0,))
        _, side, types = triples[0]
        permutation = list(reversed(range(side.entity_count)))
        mapping = {old: new for new, old in enumerate(permutation)}
        remapped = Encoded(
            [(mapping[e], p, k, t, n) for e, p, k, t, n in side.atoms],
            [(mapping[s], mapping[d], w) for s, d, w in side.edges], side.entity_count,
            [mapping[i] for i in side.action_entities], side.submissions)
        other = typed_collate([remapped])
        other.update(node_types=torch.tensor([types[i] for i in permutation]),
                     phase=b['phase'], uniform_phase=0)
        changed = dict(b, relational=other)
        with torch.no_grad():
            for expected, actual in zip(model.learning_forward(b), model.learning_forward(changed)):
                self.assertTrue(torch.allclose(expected, actual, atol=2e-6, rtol=1e-5))


if __name__ == '__main__':
    unittest.main(verbosity=2)
