"""Hot execution controls change safe batches without restarting learning."""
import contextlib
import copy
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from gakumas_training.runtime.checkpoint import capture_rng
from gakumas_training.runtime.config import EXECUTION_LIMITS, validate_execution_settings
from test_runtime import make_trainer


class ExecutionControlTests(unittest.TestCase):
    def test_successful_initial_evaluation_persists_controls_and_resume_can_train(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            trainer = make_trainer(root / 'original')
            latest = trainer.checkpoint_path
            initial = latest.with_name('initial.pt')
            trainer.checkpoint_path = initial
            trainer.checkpoint()
            trainer.checkpoint_path = latest
            rng, vocab = capture_rng(), trainer.encoder.state_dict()
            def control(stage, learner):
                learner.apply_execution_settings({'episodes_per_update': 6}, stage=stage)
                learner.execution_control_state = {'desired_sha256': 'evaluated-control'}
            trainer.execution_control = control
            trainer.evaluate()
            self.assertFalse(latest.exists())
            saved = torch.load(initial, weights_only=True)
            self.assertEqual(saved['execution_settings']['episodes_per_update'], 6)
            self.assertEqual(saved['execution_control_state']['desired_sha256'], 'evaluated-control')
            self.assertEqual(saved['encoder_state'], vocab)
            self.assertTrue(torch.equal(saved['rng']['torch'], rng['torch']))
            self.assertEqual(saved['rng']['python'], rng['python'])
            self.assertEqual(saved['rng']['numpy'], rng['numpy'])
            restored = make_trainer(root / 'restored').resume(initial)
            self.assertEqual(restored.execution_settings['episodes_per_update'], 6)
            self.assertEqual(restored.execution_control_state, trainer.execution_control_state)
            result = restored.train(1)[0]
            self.assertEqual(result['episodes'], 6)
            self.assertEqual(restored.seed_cursor, restored.config.seed + 6)

    def test_failed_or_unchanged_evaluation_never_replaces_safe_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            trainer = make_trainer(directory)
            trainer.train(1)
            saved = trainer.checkpoint_path.read_bytes()
            with patch.object(trainer, 'checkpoint', wraps=trainer.checkpoint) as checkpoint:
                trainer.evaluate()
                checkpoint.assert_not_called()
            self.assertEqual(trainer.checkpoint_path.read_bytes(), saved)
            def control(stage, learner):
                learner.apply_execution_settings({'episodes_per_update': 6}, stage=stage)
                learner.execution_control_state = {'desired_sha256': 'not-committed'}
            trainer.execution_control = control
            trainer.task.fail = True
            with patch.object(trainer, 'checkpoint', wraps=trainer.checkpoint) as checkpoint:
                with self.assertRaisesRegex(RuntimeError, 'authoritative engine failure'):
                    trainer.evaluate()
                checkpoint.assert_not_called()
            self.assertEqual(trainer.checkpoint_path.read_bytes(), saved)
            restored = make_trainer(Path(directory) / 'restored').resume(trainer.checkpoint_path)
            self.assertEqual(restored.execution_settings['episodes_per_update'], 4)
            self.assertEqual(restored.execution_control_state, {})

    def test_bounds_atomic_validation_pending_and_optimizer_identity(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            trainer = make_trainer(directory)
            trainer.train(1)
            optimizer = trainer.updater.optimizer
            state = copy.deepcopy(optimizer.state_dict())
            parameters = list(trainer.model.parameters())
            weights = copy.deepcopy(trainer.model.state_dict())
            original_config = trainer.config.to_dict()
            trainer.apply_execution_settings({'workers': 1024, 'episodes_per_update': 100000,
                'minibatch_size': 32768, 'microbatch_size': 2048}, stage='update')
            self.assertEqual(trainer.execution_settings['workers'], 1)
            self.assertEqual(trainer.execution_settings['episodes_per_update'], 4)
            self.assertEqual(trainer.pending_execution_settings, {'workers': 1024, 'episodes_per_update': 100000})
            self.assertEqual(trainer.updater.config.microbatch_size, 2048)
            actual, pending = trainer.execution_settings, trainer.pending_execution_settings
            bad = [{'clip': .3}, {'score_scale': 1}, {'microbatch_size': 32769}]
            bad += [{key: value} for key in EXECUTION_LIMITS for value in (0, -1, True, 2.5)]
            for settings in bad:
                with self.assertRaises(ValueError):
                    trainer.apply_execution_settings(settings)
                self.assertEqual(trainer.execution_settings, actual)
                self.assertEqual(trainer.pending_execution_settings, pending)
            trainer.apply_execution_settings({}, stage='collection')
            self.assertFalse(trainer.pending_execution_settings)
            self.assertEqual(trainer.execution_settings['workers'], 1024)
            self.assertIs(trainer.updater.optimizer, optimizer)
            self.assertEqual(trainer.config.to_dict(), original_config)
            self.assertTrue(all(a is b for a, b in zip(parameters, trainer.model.parameters())))
            for name, value in weights.items():
                torch.testing.assert_close(value, trainer.model.state_dict()[name], rtol=0, atol=0)
            for index, values in state['state'].items():
                for key, value in values.items():
                    torch.testing.assert_close(value, optimizer.state_dict()['state'][index][key], rtol=0, atol=0)

    def test_hot_episode_counts_resume_exact_seed_stream_and_pending(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            initial = make_trainer(root / 'unused').config
            config = replace(initial, eval_every_updates=0)
            original = make_trainer(root / 'original', config=config)
            calls = []
            def control(stage, trainer):
                calls.append((stage, trainer.iteration))
                if trainer.iteration == 0:
                    trainer.apply_execution_settings({'episodes_per_update': 3 if stage == 'collection' else 5,
                        'minibatch_size': 4, 'microbatch_size': 1}, stage=stage)
            original.execution_control = control
            original.execution_control_state = {'desired_sha256': 'saved-control-hash'}
            first = original.train(1)[0]
            self.assertEqual(calls, [('collection', 0), ('update', 0)])
            self.assertEqual(first['episodes'], 3)
            self.assertEqual(first['execution_settings']['episodes_per_update'], 3)
            self.assertEqual(original.seed_cursor, 104)
            self.assertEqual(original.pending_execution_settings, {'episodes_per_update': 5})
            saved = root / 'resume.pt'
            saved.write_bytes(original.checkpoint_path.read_bytes())
            original.train(1)
            expected = copy.deepcopy(original.model.state_dict())
            resumed = make_trainer(root / 'resumed', config=config).resume(saved)
            self.assertEqual(resumed.execution_settings['episodes_per_update'], 3)
            self.assertEqual(resumed.pending_execution_settings, {'episodes_per_update': 5})
            self.assertEqual(resumed.execution_control_state, {'desired_sha256': 'saved-control-hash'})
            resumed.execution_control = control
            second = resumed.train(1)[0]
            self.assertEqual(second['episodes'], 5)
            self.assertEqual(resumed.seed_cursor, config.seed + 8)
            self.assertEqual(resumed.episodes_seen, 8)
            rows = [json.loads(s) for s in (original.output / 'training/episodes.jsonl').read_text().splitlines()]
            self.assertEqual([r['seed'] for r in rows], list(range(config.seed, config.seed + 8)))
            for name, value in expected.items():
                torch.testing.assert_close(value, resumed.model.state_dict()[name], rtol=0, atol=0)
            self.assertEqual(resumed.encoder.state_dict(), original.encoder.state_dict())

    def test_evaluation_hook_keeps_fixed_seeds_rng_and_vocabulary(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            trainer = make_trainer(directory)
            before, vocab, cursor = capture_rng(), trainer.encoder.state_dict(), trainer.seed_cursor
            calls = []
            def control(stage, learner):
                calls.append(stage)
                learner.apply_execution_settings({'episodes_per_update': 9}, stage=stage)
            trainer.execution_control = control
            result = trainer.evaluate()
            self.assertEqual(calls, ['collection'])
            self.assertEqual(result['episodes'], trainer.config.eval_episodes)
            self.assertEqual(trainer.seed_cursor, cursor)
            self.assertEqual(trainer.encoder.state_dict(), vocab)
            after = capture_rng()
            self.assertEqual(after['python'], before['python'])
            self.assertEqual(after['numpy'], before['numpy'])
            self.assertTrue(torch.equal(after['torch'], before['torch']))
            rows = [json.loads(s) for s in (trainer.output / 'evaluation/episodes.jsonl').read_text().splitlines()]
            self.assertEqual([r['seed'] for r in rows], list(range(trainer.config.eval_seed,
                trainer.config.eval_seed + trainer.config.eval_episodes)))

    def test_legacy_checkpoint_defaults_and_cursor_validation(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            trainer = make_trainer(root / 'original')
            trainer.train(1)
            value = torch.load(trainer.checkpoint_path, weights_only=True)
            for key in ('execution_settings', 'pending_execution_settings', 'last_batch_execution_settings',
                        'execution_control_state'):
                value.pop(key)
            legacy = root / 'legacy.pt'
            torch.save(value, legacy)
            restored = make_trainer(root / 'legacy').resume(legacy)
            self.assertEqual(restored.execution_settings, trainer.execution_settings)
            self.assertEqual(restored.execution_control_state, {})
            value['episodes_seen'] += 1
            torch.save(value, legacy)
            with self.assertRaisesRegex(ValueError, 'seed cursor'):
                make_trainer(root / 'bad').resume(legacy)

    def test_microbatch_change_preserves_accumulated_gradient_and_oom_setting(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            config = replace(make_trainer(root / 'unused').config, eval_every_updates=0)
            trainer = make_trainer(root / 'original', config=config)
            trainer.train(1)
            saved = root / 'saved.pt'
            saved.write_bytes(trainer.checkpoint_path.read_bytes())
            optimizer = trainer.updater.optimizer
            trainer.apply_execution_settings({'microbatch_size': 1})
            trainer.train(1)
            self.assertIs(optimizer, trainer.updater.optimizer)
            expected = copy.deepcopy(trainer.model.state_dict())
            other = make_trainer(root / 'other', config=config).resume(saved)
            other.apply_execution_settings({'microbatch_size': 4})
            other.train(1)
            for name, value in expected.items():
                torch.testing.assert_close(value, other.model.state_dict()[name], rtol=1e-6, atol=1e-7)
            update = other.updater.update
            def reported_fallback(*args, **kwargs):
                result = update(*args, **kwargs)
                result['effective_microbatch_size'] = 2
                return result
            other.updater.update = reported_fallback
            metrics = other.train(1)[0]
            self.assertEqual(other.execution_settings['microbatch_size'], 2)
            self.assertEqual(other.updater.config.microbatch_size, 2)
            self.assertEqual(metrics['execution_settings']['microbatch_size'], 2)
            state = torch.load(other.checkpoint_path, weights_only=True)
            self.assertEqual(state['execution_settings']['microbatch_size'], 2)


if __name__ == '__main__':
    unittest.main()
