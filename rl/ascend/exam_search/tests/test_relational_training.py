"""Named Adam/LR/checkpoint integration checks, with synthetic CPU tensors only."""
import copy
import os
import random
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'runtime' / 'shared'), str(ROOT.parents[1] / 'training'),
               str(Path(__file__).resolve().parent)]

from test_relational_model import batch, examples
from draftrl import checkpoint, learning_rates
from draftrl.encoding import ENCODING
from draftrl.model import DraftPolicy, MODEL_SCHEMA
from draftrl.relational_training import (SCHEMA, PHASES, parameter_groups, named_groups,
                                         migrate_optimizer, validate_config)


def config(enabled=True):
    result = {key: .001 * (i + 1) for i, key in enumerate(learning_rates.PHASE_KEYS.values())}
    result['learning_rate_schedule'] = {
        'schema': 'arena-learning-rate-linear/1', 'basis': 'elapsed_minutes',
        'origin_elapsed_minutes': 0., 'hold_minutes': 120., 'decay_minutes': 240., 'min_ratio': .2,
    }
    if enabled:
        result['relational'] = {'enabled': True, 'schema': SCHEMA, 'legacy_lr_ratio': .25,
                                'adaptation_minutes': 120., 'new_lr_multiplier': 1.}
    return result


def rates():
    return {name: .001 * (i + 1) for i, name in enumerate(PHASES)}


def optimizer(model):
    return torch.optim.Adam(parameter_groups(model, rates()), eps=1e-5)


def source_checkpoint(*, names=True):
    torch.manual_seed(444)
    model = DraftPolicy(width=16, lexical=4, depth=2, quantiles=32)
    opt = optimizer(model)
    # Distinct moments expose incorrect migration by list position or shape.
    for i, parameter in enumerate(model.parameters()):
        parameter.grad = torch.full_like(parameter, .001 * (1 + i % 29))
    opt.step()
    opt.zero_grad(set_to_none=True)
    info = {'model_schema': MODEL_SCHEMA, 'encoding': ENCODING,
            'model_config': model.config, 'model_state': copy.deepcopy(model.state_dict()),
            'optimizer_state': copy.deepcopy(opt.state_dict()), 'arena_sha256': 'test-arena',
            'decisions': 123, 'batches': 7}
    if names:
        info['optimizer_parameter_names'] = named_groups(model, opt)
    return model, opt, info


def synthetic_step(model, opt, b):
    """Exercise every branch, including stochastic targets/order, without Arena."""
    opt.zero_grad(set_to_none=True)
    order = torch.randperm(b['batch_size'])
    target_actions = torch.randint(0, 2, (b['batch_size'],))
    returns = torch.rand(b['batch_size']) + random.random()
    logits, values, atoms = model.learning_forward(b)
    policy = -logits.log_softmax(-1)[order, target_actions].mean()
    loss = policy + (values[order] - returns).square().mean()
    loss = loss + (atoms[order] - returns[:, None]).square().mean()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), .5)
    opt.step()
    return loss.detach().clone()


class RelationalTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_old_five_positional_groups_keep_original_schedule(self):
        model, _, _ = source_checkpoint()
        raw_groups = parameter_groups(model, rates())
        raw_groups = [{'params': g['params'], 'lr': g['lr']} for g in raw_groups]
        opt = torch.optim.Adam(raw_groups)
        cfg = config(False)
        for minutes in (0, 60, 120, 180, 360, 1000):
            expected = learning_rates.scheduled(cfg, minutes)
            actual = learning_rates.apply(opt, cfg, minutes)
            self.assertEqual(expected, actual)
            self.assertEqual(learning_rates.current(opt), expected['rates'])

    def test_seven_named_groups_adapt_without_resetting_base_schedule(self):
        model = DraftPolicy(width=16, lexical=4, depth=2, quantiles=32, relational=True)
        opt = optimizer(model)
        cfg = config()
        for minutes, ratio in ((0, .25), (60, .625), (120, 1.), (240, 1.)):
            base = learning_rates.scheduled(cfg, minutes)
            result = learning_rates.apply(opt, cfg, minutes)
            self.assertAlmostEqual(result['relational_adaptation']['inherited_ratio'], ratio)
            for phase in PHASES:
                self.assertAlmostEqual(result['rates'][phase], base['rates'][phase] * ratio)
            for name in ('actor_relational', 'critic_relational'):
                self.assertAlmostEqual(result['rates'][name], base['rates']['exam'])
            self.assertEqual(result['stage'], base['stage'])
        cfg['learning_rate_schedule']['origin_elapsed_minutes'] = 240.
        restored = learning_rates.apply(opt, cfg, 240.)
        self.assertEqual(restored['stage'], 'hold')
        self.assertEqual(restored['relational_adaptation']['inherited_ratio'], 1.)
        # Named assignment also works when an optimizer serializes groups in another order.
        opt.param_groups.reverse()
        self.assertEqual(learning_rates.apply(opt, cfg, 240.)['rates'], restored['rates'])

    def test_adaptation_zero_duration_and_new_multiplier(self):
        model = DraftPolicy(width=16, lexical=4, depth=2, relational=True)
        opt = optimizer(model)
        cfg = config()
        cfg['relational'].update(adaptation_minutes=0., new_lr_multiplier=1.5)
        result = learning_rates.apply(opt, cfg, 0.)
        self.assertEqual(result['rates']['exam'], rates()['exam'])
        self.assertAlmostEqual(result['rates']['actor_relational'], rates()['exam'] * 1.5)
        self.assertEqual(result['relational_adaptation']['stage'], 'complete')

    def test_batch_adaptation_does_not_elapse_during_long_initial_validation(self):
        model = DraftPolicy(width=16, lexical=4, depth=2, relational=True)
        opt = optimizer(model)
        cfg = config()
        cfg['relational']['adaptation_batches'] = 8
        for minutes, completed, ratio in ((0, 0, .25), (600, 0, .25), (900, 4, .625), (1200, 8, 1.)):
            actual = learning_rates.apply(opt, cfg, minutes, completed_batches=completed)
            base = learning_rates.scheduled(cfg, minutes)
            self.assertEqual(actual['relational_adaptation']['basis'], 'completed_batches')
            self.assertAlmostEqual(actual['relational_adaptation']['inherited_ratio'], ratio)
            self.assertAlmostEqual(actual['rates']['exam'], base['rates']['exam'] * ratio)
        for completed in (None, -1, 1.5, True):
            with self.assertRaisesRegex(ValueError, 'completed_batches'):
                learning_rates.apply(opt, cfg, 10., completed_batches=completed)
        for duration in (0, -1, 1.5, True, float('nan'), float('inf')):
            malformed = copy.deepcopy(cfg)
            malformed['relational']['adaptation_batches'] = duration
            with self.assertRaisesRegex(ValueError, 'positive integer'):
                validate_config(malformed)

    def test_relational_enable_requires_an_explicit_boolean(self):
        for value in ('false', 1, None):
            cfg = config()
            cfg['relational']['enabled'] = value
            with self.assertRaisesRegex(ValueError, 'boolean'):
                validate_config(cfg)

    def test_group_identity_and_configuration_fail_closed(self):
        model = DraftPolicy(width=16, lexical=4, depth=2, relational=True)
        opt = optimizer(model)
        with self.assertRaisesRegex(ValueError, 'configuration'):
            learning_rates.apply(opt, config(False), 0.)
        opt.param_groups[-1]['name'] = 'actor_relational'
        with self.assertRaisesRegex(ValueError, 'names'):
            learning_rates.current(opt)
        opt = optimizer(model)
        opt.param_groups[-1]['inherited'] = True
        with self.assertRaisesRegex(ValueError, 'ownership'):
            learning_rates.current(opt)
        cfg = config()
        cfg['relational']['legacy_lr_ratio'] = 1.1
        with self.assertRaisesRegex(ValueError, 'exceed'):
            validate_config(cfg)

    def test_adam_by_name_copies_moments_and_leaves_new_groups_fresh(self):
        source, source_opt, info = source_checkpoint()
        model = DraftPolicy(**source.config, relational=True)
        target = optimizer(model)
        ids = [id(p) for g in target.param_groups for p in g['params']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {id(p) for p in model.parameters()})
        # Reorder both saved name lists and parameter lists; the state identity
        # remains valid, but positional-copy implementations would get this wrong.
        for names, group in zip(info['optimizer_parameter_names'], info['optimizer_state']['param_groups']):
            names.reverse()
            group['params'].reverse()
        info['optimizer_parameter_names'].reverse()
        info['optimizer_state']['param_groups'].reverse()
        before_rng = torch.get_rng_state().clone()
        report = migrate_optimizer(info, model, target, 'cpu')
        self.assertTrue(torch.equal(before_rng, torch.get_rng_state()))
        source_parameters = dict(source.named_parameters())
        for name, parameter in model.named_parameters():
            if name.startswith(('actor_relational.', 'critic_relational.')):
                self.assertNotIn(parameter, target.state)
                continue
            expected = source_opt.state[source_parameters[name]]
            actual = target.state[parameter]
            for key in ('exp_avg', 'exp_avg_sq', 'step'):
                self.assertTrue(torch.equal(expected[key], actual[key]), name + ':' + key)
                self.assertNotEqual(expected[key].data_ptr(), actual[key].data_ptr())
        self.assertEqual(report['copied_parameter_tensors'], len(source_parameters))
        self.assertFalse(report['old_rollout_data_reused'])

    def test_historical_unnamed_checkpoint_reconstructs_parameter_names(self):
        source, source_opt, info = source_checkpoint(names=False)
        model = DraftPolicy(**source.config, relational=True)
        target = optimizer(model)
        before_rng = torch.get_rng_state().clone()
        report = migrate_optimizer(info, model, target, 'cpu')
        self.assertTrue(torch.equal(before_rng, torch.get_rng_state()))
        self.assertEqual(report['copied_parameter_tensors'], len(list(source.parameters())))
        for name, parameter in source.named_parameters():
            actual = target.state[dict(model.named_parameters())[name]]
            self.assertTrue(torch.equal(actual['exp_avg'], source_opt.state[parameter]['exp_avg']))

    def test_checkpoint_warm_start_keeps_all_phase_outputs_and_inherited_tensors(self):
        source, _, info = source_checkpoint()
        with tempfile.TemporaryDirectory(prefix='arena-relational-checkpoint-') as directory:
            path = Path(directory) / 'old.pt'
            torch.save(info, path)
            model, report = checkpoint.transfer(path, 'test-arena', 'cpu', relational=True)
        self.assertTrue(report['all_old_weights_preserved'])
        self.assertFalse(report['restore_continuation'])
        for name, value in source.state_dict().items():
            self.assertTrue(torch.equal(model.state_dict()[name], value), name)
        b, _ = batch((0, 1, 2, 3, 4), [1, 2, 3, 2, 1])
        with torch.no_grad():
            for old, new in zip(source.learning_forward(b), model.learning_forward(b)):
                self.assertTrue(torch.equal(old, new))

    def test_checkpoint_schema_mismatch_is_rejected(self):
        _, _, info = source_checkpoint()
        malformed = [dict(info, model_schema=SCHEMA), dict(info, encoding='unknown-encoding')]
        with tempfile.TemporaryDirectory(prefix='arena-relational-schema-') as directory:
            path = Path(directory) / 'bad.pt'
            for payload in malformed:
                torch.save(payload, path)
                with self.assertRaises(ValueError):
                    checkpoint.load(path, 'cpu')

    def test_late_quantile_parameters_go_to_their_own_groups(self):
        model = DraftPolicy(width=16, lexical=4, depth=2, relational=True)
        opt = optimizer(model)
        model.enable_quantiles(32, opt)
        actual = {group['name']: {id(p) for p in group['params']} for group in opt.param_groups}
        self.assertTrue({id(p) for p in model.exam_quantile_head.parameters()} <= actual['exam'])
        self.assertTrue({id(p) for p in model.critic_relational.quantile_head.parameters()}
                        <= actual['critic_relational'])
        all_ids = [id(p) for g in opt.param_groups for p in g['params']]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(set(all_ids), {id(p) for p in model.parameters()})

    def test_warmed_v6_checkpoint_next_update_is_bit_identical_after_resume(self):
        from gakumas_training.device import load_optimizer_state
        torch.manual_seed(713)
        random.seed(917)
        model = DraftPolicy(width=16, lexical=4, depth=2, quantiles=32, relational=True)
        opt = optimizer(model)
        cfg = config()
        cfg['relational']['adaptation_batches'] = 8
        b, _ = batch()
        for completed in range(2):
            learning_rates.apply(opt, cfg, completed * 3., completed_batches=completed)
            synthetic_step(model, opt, b)
        # The resumed state is genuinely warmed: both output projections and
        # internal new encoders have participated in backpropagation.
        inner = model.actor_relational.encoder.stem.program_encoder[0].weight
        self.assertGreater(int(opt.state[inner]['step']), 0)
        self.assertGreater(float(opt.state[inner]['exp_avg'].abs().sum()), 0)
        with tempfile.TemporaryDirectory(prefix='arena-relational-resume-') as directory:
            path = Path(directory) / 'v6.pt'
            checkpoint.save(path, model, opt, training_config=cfg, batches=2,
                            decisions=10, arena_sha256='synthetic')
            restored, info = checkpoint.load(path, 'cpu')
            restored_opt = optimizer(restored)
            load_optimizer_state(restored_opt, info['optimizer_state'], 'cpu')
        self.assertEqual(info['model_schema'], SCHEMA)
        self.assertEqual(named_groups(model, opt), named_groups(restored, restored_opt))
        self.assertEqual(len(restored_opt.param_groups), 7)
        for name, value in model.state_dict().items():
            self.assertTrue(torch.equal(value, restored.state_dict()[name]), name)
        for current_model, current_opt in ((model, opt), (restored, restored_opt)):
            learning_rates.apply(current_opt, cfg, 6., completed_batches=info['batches'])
            torch.set_rng_state(info['torch_rng'])
            random.setstate(info['python_rng'])
            value = synthetic_step(current_model, current_opt, b)
            if current_model is model:
                expected_loss = value
                expected_rng = torch.get_rng_state().clone()
                expected_python_rng = random.getstate()
            else:
                self.assertTrue(torch.equal(expected_loss, value))
                self.assertTrue(torch.equal(expected_rng, torch.get_rng_state()))
                self.assertEqual(expected_python_rng, random.getstate())
        for name, value in model.state_dict().items():
            self.assertTrue(torch.equal(value, restored.state_dict()[name]), name)
        expected, actual = opt.state_dict(), restored_opt.state_dict()
        self.assertEqual(expected['param_groups'], actual['param_groups'])
        self.assertEqual(set(expected['state']), set(actual['state']))
        for key, state in expected['state'].items():
            for field, value in state.items():
                if isinstance(value, torch.Tensor):
                    self.assertTrue(torch.equal(value, actual['state'][key][field]), (key, field))
                else:
                    self.assertEqual(value, actual['state'][key][field])

    def test_critic_completion_freezes_old_and_new_actor_and_its_adam_state(self):
        from draftrl.critic_completion import complete_values, value_parameter
        from draftrl.kl_value_migration import SETTINGS
        from draftrl.encoding import collate
        from draftrl.relational_runtime import ENV
        model = DraftPolicy(width=16, lexical=4, depth=2, quantiles=32, relational=True)
        opt = optimizer(model)
        rows = []
        for phase in range(5):
            old, side, types = examples(phase)
            side.node_types = types
            old.relational_view = side
            rows.append({'encoded': old, 'profile': 'synthetic', 'loss_kind': 'ppo'})
        # The fixture supplies a complete side view. Do not load native rules or
        # inherit the opt-in semantics path of an unrelated test environment.
        with mock.patch.dict(os.environ, {ENV: ''}):
            b = collate([row['encoded'] for row in rows], 'cpu')
            synthetic_step(model, opt, b)
            synthetic_step(model, opt, b)
            before = {name: p.detach().clone() for name, p in model.named_parameters()}
            frozen_adam = {name: copy.deepcopy(opt.state[p]) for name, p in model.named_parameters()
                           if not value_parameter(name)}
            flags = {name: p.requires_grad for name, p in model.named_parameters()}
            cfg = {'critic_completion': SETTINGS, 'effective_minibatch': 5, 'minibatch': 2,
                   'max_grad': .5, 'value_coefficient': .5,
                   'value_calibration': {'distribution_coefficient': 1.}}
            result = complete_values(model, opt, rows, torch.arange(5, dtype=torch.float32) + .75,
                                     torch.ones(5), set(), set(), list(range(5)), cfg, 'cpu')
        self.assertTrue(result['actor_unchanged'])
        self.assertEqual(result['actor_sha256_before'], result['actor_sha256_after'])
        self.assertEqual(result['completed_records'], 5)
        self.assertEqual(result['optimizer_steps'], 1)
        changed_new_critic = False
        for name, parameter in model.named_parameters():
            self.assertEqual(parameter.requires_grad, flags[name], name)
            if value_parameter(name):
                if name.startswith('critic_relational.') and not torch.equal(before[name], parameter):
                    changed_new_critic = True
                continue
            self.assertTrue(torch.equal(before[name], parameter), name)
            for field, value in frozen_adam[name].items():
                if isinstance(value, torch.Tensor):
                    self.assertTrue(torch.equal(value, opt.state[parameter][field]), name + ':' + field)
                else:
                    self.assertEqual(value, opt.state[parameter][field])
            self.assertIsNone(parameter.grad, name)
        self.assertTrue(changed_new_critic)


if __name__ == '__main__':
    unittest.main(verbosity=2)
