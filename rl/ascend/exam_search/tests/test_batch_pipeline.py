"""Input overlap keeps record order, structural metadata, RNG and Adam exact."""
import copy
import os
import random
import threading
import unittest
from unittest.mock import patch
import torch
from draftrl.batch_pipeline import BatchStream, prepare_cpu, transfer
from draftrl.encoding import collate
from draftrl.model import DraftPolicy
from draftrl.ppo import update
from test_joint_search import example, records, config


class BatchPipelineTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(61)

    def equal(self, left, right):
        if isinstance(left, torch.Tensor):
            torch.testing.assert_close(left, right, atol=0, rtol=0)
        elif isinstance(left, dict):
            self.assertEqual(left.keys(), right.keys())
            for k in left:
                self.equal(left[k], right[k])
        elif isinstance(left, (list, tuple)):
            self.assertEqual(len(left), len(right))
            for a, b in zip(left, right):
                self.equal(a, b)
        else:
            self.assertEqual(left, right)

    def test_cpu_structure_and_npu_plans_survive_transfer(self):
        examples = [example(p) for p in range(5)]
        base = collate(examples, 'cpu')
        staged = prepare_cpu(examples, npu=True)
        self.equal(base, {k: staged[k] for k in base})
        moved = transfer(staged, 'cpu')
        self.assertIs(moved['lengths'], staged['lengths'])
        for k in ('entities', 'batches'):
            self.equal(staged[k]._arena_segment_plan, moved[k]._arena_segment_plan)
        for part in moved['tower_inputs'].values():
            self.assertTrue(hasattr(part['batches'], '_arena_segment_plan'))
        self.equal(staged, moved)

    def test_bounded_ordered_overlap_empty_blocks_and_rng(self):
        rows = [{'encoded': example(p % 5)} for p in range(12)]
        owner = threading.get_ident()
        second = threading.Event()
        calls = []

        def prepare(examples, **kwargs):
            self.assertNotEqual(threading.get_ident(), owner)
            calls.append(examples)
            if len(calls) == 2:
                second.set()
            return prepare_cpu(examples, **kwargs)

        python_rng, torch_rng = random.getstate(), torch.get_rng_state().clone()
        with patch('draftrl.batch_pipeline.prepare_cpu', prepare):
            with BatchStream(rows, [[5, 3, 1], [], [8, 2, 4, 7]], 2, 'cpu', enabled=True) as stream:
                first = list(stream.block(0))
                self.assertTrue(second.wait(2))
                self.assertEqual([i for ids, _ in first for i in ids], [5, 3, 1])
                self.assertEqual(list(stream.block(1)), [])
                final = list(stream.block(2))
                self.assertEqual([i for ids, _ in final for i in ids], [8, 2, 4, 7])
                self.assertLessEqual(len(stream.pending), 2)
        self.assertEqual(python_rng, random.getstate())
        self.equal(torch_rng, torch.get_rng_state())
        self.assertFalse(any(t.name.startswith('ppo-input') for t in threading.enumerate()))

    def test_early_exit_does_not_prepare_whole_epoch(self):
        rows = [{'encoded': example(0)} for _ in range(30)]
        calls = []

        def prepare(examples, **kwargs):
            calls.append(1)
            return prepare_cpu(examples, **kwargs)

        with patch('draftrl.batch_pipeline.prepare_cpu', prepare):
            with BatchStream(rows, [list(range(30))], 1, 'cpu', enabled=True) as stream:
                next(stream.block(0))
        self.assertLessEqual(len(calls), 3)
        self.assertFalse(any(t.name.startswith('ppo-input') for t in threading.enumerate()))

    def test_worker_failure_surfaces_and_joins(self):
        with patch('draftrl.batch_pipeline.prepare_cpu', side_effect=ValueError('bad input')):
            with self.assertRaisesRegex(ValueError, 'bad input'):
                with BatchStream([{'encoded': example(0)}], [[0]], 1, 'cpu', enabled=True) as stream:
                    list(stream.block(0))
        self.assertFalse(any(t.name.startswith('ppo-input') for t in threading.enumerate()))

    def test_mixed_ppo_search_gradients_adam_and_rng_identical(self):
        prototype = DraftPolicy(width=16, lexical=8)
        rows = records(prototype) * 3
        cfg = config()
        cfg['sample_efficiency']['ppo_epochs_max'] = 2
        cfg['target_kl'] = 10.
        results = []
        for flag in ('0', '1'):
            model = copy.deepcopy(prototype)
            optimizer = torch.optim.Adam(model.parameters(), lr=.0001, foreach=False)
            random.seed(417)
            torch.manual_seed(417)
            with patch.dict(os.environ, {'GAKUMAS_PPO_PREFETCH': flag}):
                metrics = update(model, optimizer, copy.deepcopy(rows), cfg, 'cpu')
            self.assertEqual(metrics['input_pipeline']['enabled'], flag == '1')
            metrics.pop('input_pipeline')
            results.append((copy.deepcopy(model.state_dict()), copy.deepcopy(optimizer.state_dict()),
                            {n: p.grad.clone() for n, p in model.named_parameters() if p.grad is not None},
                            random.getstate(), torch.get_rng_state().clone(), metrics))
        self.equal(*results)


if __name__ == '__main__':
    unittest.main()
