"""Real spawn/IPC tests with tiny environments; no long Arena training."""
from dataclasses import dataclass, replace
import contextlib
import copy
import io
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np
import torch

from gakumas_training.algorithms import PPOConfig, PPOUpdater
from gakumas_training.contracts import DecisionContext, Episode, PolicySelection, Transition
from gakumas_training.runtime import RunConfig, Trainer
from gakumas_training.runtime.checkpoint import capture_rng
from gakumas_training.runtime.parallel import RemoteWorkerError, SynchronousCollector, _kill_tree
from test_runtime import TinyEncoder
from test_ppo import TinyPolicy


@dataclass
class ToyConfig:
    fail_seed: int | None = None
    close_dir: str | None = None
    spawn_helper: bool = False
    discard_first: bool = False


class ParallelToyTask:
    name = 'full_produce'

    def __init__(self, config=None):
        self.config = config or ToyConfig()
        self.helper = None

    def run_episode(self, policy, *, seed, policy_version):
        if self.config.spawn_helper and self.helper is None:
            self.helper = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        transitions = []
        for step in range(2 + seed % 3):
            time.sleep(.003 * (3 - seed % 3))  # Deliberately vary OS arrival order.
            context = DecisionContext(self.name, 'setup_support' if step == 0 else 'exam_action',
                {'public': seed % 3, 'step': step}, ({'a': 0}, {'a': 1}))
            selection = policy(context)
            if selection.encoded is not None:
                raise AssertionError('Environment received parent encoding')
            transitions.append(Transition(context, selection))
            if seed == self.config.fail_seed:
                raise RuntimeError('deliberate environment failure')
        if self.config.discard_first:
            transitions = transitions[1:]  # Emulate a discarded callback transaction.
        score = 10. + seed % 7 + sum(t.selection.action_index for t in transitions) * 3.
        return Episode(self.name, seed, transitions, score, 'failed' if seed % 2 else 'passed',
            {'loadout_profile': str(seed % 5), 'setup_mode': 'select' if (seed // 5) % 2 else 'given',
             'worker_pid': os.getpid()})

    def close(self):
        if self.helper is not None:
            self.helper.kill()
            self.helper.wait(timeout=5)
        if self.config.close_dir:
            Path(self.config.close_dir, f'{os.getpid()}.json').write_text(json.dumps({
                'pid': os.getpid(), 'helper_reaped': self.helper is None or self.helper.poll() is not None}))


class BatchedTinyRunner:
    def __init__(self, encoder, model):
        self.encoder, self.model = encoder, model
        self.batches = []

    def act_batch(self, contexts, policy_version=0, deterministic=False):
        self.batches.append([(c.observation['public'], c.observation['step']) for c in contexts])
        encoded = []
        for context in contexts:
            self.encoder.seen.append(context.observation['public'])
            encoded.append([1., float(context.observation['public']) + .1 * context.observation['step']])
        with torch.no_grad():
            evaluated = self.model.evaluate(encoded)
            distribution = torch.distributions.Categorical(logits=evaluated.logits)
            actions = evaluated.logits.argmax(-1) if deterministic else distribution.sample()
            log_probs = distribution.log_prob(actions)
        return [PolicySelection(int(action), float(log_prob), float(value), policy_version, data)
                for action, log_prob, value, data in zip(actions, log_probs, evaluated.values, encoded)]


def make_parallel_trainer(output, *, config=None):
    config = config or RunConfig(task='full_produce', seed=100, eval_seed=10000, workers=2,
        episodes_per_update=4, eval_episodes=2, eval_every_updates=0, score_scale=10,
        ppo=PPOConfig(epochs=1, minibatch_size=16, microbatch_size=4))
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    encoder, model = TinyEncoder(), TinyPolicy()
    return Trainer(task=ParallelToyTask(), encoder=encoder, model=model,
        policy_runner=BatchedTinyRunner(encoder, model), config=config,
        output=output, arena_version='parallel-toy-v1')


class ParallelRuntimeTests(unittest.TestCase):
    def assert_reaped(self, collector):
        live = {child.pid for child in mp.active_children()}
        self.assertTrue(set(collector.last_worker_pids).isdisjoint(live))
        self.assertEqual(collector.processes, [])

    def test_spawned_waves_order_mixed_coverage_behavior_parity_and_parent_encoding(self):
        torch.manual_seed(41)
        model = TinyPolicy()
        runner = BatchedTinyRunner(TinyEncoder(), model)
        collector = SynchronousCollector(ParallelToyTask(), runner, workers=2)
        episodes = collector.collect(range(100, 110), policy_version=0)
        self.assertEqual([e.seed for e in episodes], list(range(100, 110)))
        self.assertEqual(len({e.metadata['worker_pid'] for e in episodes}), 2)
        self.assertEqual(len({(e.metadata['loadout_profile'], e.metadata['setup_mode']) for e in episodes}), 10)
        self.assertTrue(all(t.selection.encoded is not None for e in episodes for t in e.transitions))
        self.assertTrue(any(len(batch) == 2 for batch in runner.batches))
        metrics = PPOUpdater(model, PPOConfig(epochs=1)).update(episodes,
            task='full_produce', policy_version=0, score_scale=10)
        self.assertLess(metrics['behavior_parity_max_error'], 2e-5)
        self.assert_reaped(collector)

    def test_worker_transaction_discard_does_not_train_on_aborted_callbacks(self):
        runner = BatchedTinyRunner(TinyEncoder(), TinyPolicy())
        collector = SynchronousCollector(ParallelToyTask(ToyConfig(discard_first=True)), runner, workers=2)
        episodes = collector.collect([1, 2], policy_version=0)
        self.assertTrue(all(e.transitions[0].decision.observation['step'] == 1 for e in episodes))
        self.assert_reaped(collector)

    def test_environment_failure_and_parent_interrupt_reap_workers_and_owned_helpers(self):
        for interrupt in (False, True):
            with self.subTest(interrupt=interrupt), tempfile.TemporaryDirectory() as directory:
                config = ToyConfig(fail_seed=None if interrupt else 1, close_dir=directory, spawn_helper=True)
                runner = BatchedTinyRunner(TinyEncoder(), TinyPolicy())
                collector = SynchronousCollector(ParallelToyTask(config), runner, workers=2)
                if interrupt:
                    with patch.object(runner, 'act_batch', side_effect=KeyboardInterrupt('parent cancelled')):
                        with self.assertRaises(KeyboardInterrupt):
                            collector.collect([1, 2], policy_version=0)
                else:
                    with self.assertRaisesRegex(RemoteWorkerError, 'deliberate environment failure'):
                        collector.collect([1, 2], policy_version=0)
                self.assert_reaped(collector)
                records = [json.loads(path.read_text()) for path in Path(directory).glob('*.json')]
                self.assertEqual({r['pid'] for r in records}, set(collector.last_worker_pids))
                self.assertTrue(all(r['helper_reaped'] for r in records))

    def test_same_configuration_resume_repeats_next_update_and_evaluation_preserves_rng(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            original = make_parallel_trainer(root / 'original')
            original.train(1)
            saved = root / 'saved.pt'
            saved.write_bytes(original.checkpoint_path.read_bytes())
            original.train(1)
            resumed = make_parallel_trainer(root / 'resumed')
            resumed.resume(saved)
            before, vocabulary, cursor = capture_rng(), copy.deepcopy(resumed.encoder.state_dict()), resumed.seed_cursor
            evaluated = resumed.evaluate()
            after = capture_rng()
            self.assertEqual(before['python'], after['python'])
            self.assertEqual(before['numpy'], after['numpy'])
            self.assertTrue(torch.equal(before['torch'], after['torch']))
            self.assertEqual(resumed.encoder.state_dict(), vocabulary)
            self.assertEqual(resumed.seed_cursor, cursor)
            self.assertEqual(evaluated['episodes'], 2)
            resumed.train(1)
            for key, value in original.model.state_dict().items():
                torch.testing.assert_close(value, resumed.model.state_dict()[key], rtol=0, atol=0)
            self.assertEqual(original.encoder.state_dict(), resumed.encoder.state_dict())
            changed = make_parallel_trainer(root / 'wrong', config=replace(original.config, workers=4))
            with self.assertRaisesRegex(ValueError, 'config'):
                changed.resume(saved)

    def test_worker_count_validation_and_owned_posix_group_target(self):
        for workers in (1, 2, 4, 8, 10, 12, 16, 128, 129, 1024, 1000000):
            self.assertEqual(RunConfig(task='full_produce', workers=workers).workers, workers)
            collector = SynchronousCollector(ParallelToyTask(), BatchedTinyRunner(None, None), workers=workers)
            self.assertEqual(collector.workers, workers)
        for workers in (0, -1, True, 2.5):
            with self.assertRaises(ValueError):
                RunConfig(task='full_produce', workers=workers)
            with self.assertRaises(ValueError):
                SynchronousCollector(ParallelToyTask(), BatchedTinyRunner(None, None), workers=workers)
        process = Mock(pid=43210)
        with patch('gakumas_training.runtime.parallel.os.name', 'posix'), \
             patch('gakumas_training.runtime.parallel.os.killpg', create=True) as kill:
            _kill_tree(process, True, {54321})
            kill.assert_called_once()
            self.assertEqual(kill.call_args.args[0], 43210)
        process.terminate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
