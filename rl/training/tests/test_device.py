import unittest
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import torch

from gakumas_training import device as backend
from gakumas_training.runtime.checkpoint import capture_rng, restore_rng


class DeviceTests(unittest.TestCase):
    def test_restored_optimizer_cannot_reenable_cuda_execution_options_on_npu(self):
        state = {'state': {0: {'step': torch.tensor(3.), 'exp_avg': torch.tensor([.2])}},
                 'param_groups': [{'params': [0], 'lr': .003, 'foreach': True,
                                   'fused': True, 'capturable': True}]}
        optimizer = Mock()
        backend.load_optimizer_state(optimizer, state, 'npu:0')
        restored = optimizer.load_state_dict.call_args.args[0]
        self.assertIs(restored['state'], state['state'])
        self.assertEqual(restored['param_groups'][0],
                         {'params': [0], 'lr': .003, 'foreach': False, 'fused': False, 'capturable': False})
        self.assertTrue(state['param_groups'][0]['foreach'])
        backend.load_optimizer_state(optimizer, state, 'cpu')
        self.assertIs(optimizer.load_state_dict.call_args.args[0], state)

    def test_single_learner_preserves_explicit_device_index(self):
        from gakumas_training.collectives import CollectiveGroup
        env = dict(RANK='0', WORLD_SIZE='1', LOCAL_RANK='0', LOCAL_WORLD_SIZE='1')
        with patch.dict(os.environ, env), patch.object(backend, 'resolve_device', return_value='npu:5') as resolve:
            self.assertEqual(CollectiveGroup('npu:5').device, 'npu:5')
            resolve.assert_called_once_with('npu:5')

    def test_torchrun_assigns_owned_card_and_rejects_multiple_hosts(self):
        from gakumas_training.collectives import CollectiveGroup
        env = dict(RANK='19', WORLD_SIZE='32', LOCAL_RANK='19', LOCAL_WORLD_SIZE='32')
        with patch.dict(os.environ, env), patch.object(backend, 'resolve_device', return_value='npu:19') as resolve:
            with patch.object(torch.distributed, 'init_process_group') as init, patch.object(torch.distributed, 'new_group') as group:
                self.assertEqual(CollectiveGroup('npu:0').device, 'npu:19')
                resolve.assert_called_once_with('npu:19')
                self.assertEqual(init.call_args.args[0], 'gloo')
                self.assertEqual(group.call_args.kwargs['backend'], 'hccl')
            os.environ['LOCAL_WORLD_SIZE'] = '4'
            with self.assertRaisesRegex(ValueError, 'one host'):
                CollectiveGroup('npu')

    def test_threads_have_no_application_cap_and_invalid_topology_fails_early(self):
        from gakumas_training.collectives import CollectiveGroup
        env = dict(RANK='0', WORLD_SIZE='1', LOCAL_RANK='0', LOCAL_WORLD_SIZE='1')
        with patch.dict(os.environ, env), patch.object(torch, 'set_num_threads') as threads:
            CollectiveGroup('cpu', torch_threads=256)
            threads.assert_called_once_with(256)
            for count in (0, -1, True, 2.5):
                with self.assertRaisesRegex(ValueError, 'positive integer'):
                    CollectiveGroup('cpu', torch_threads=count)
            for changes in ({'WORLD_SIZE': '0', 'LOCAL_WORLD_SIZE': '0'},
                            {'RANK': '1'}, {'LOCAL_RANK': '1'}):
                with patch.dict(os.environ, changes), self.assertRaises(ValueError):
                    CollectiveGroup('cpu')

    def test_cpu_does_not_import_optional_npu(self):
        with patch.object(backend.importlib, 'import_module') as imported:
            self.assertEqual(backend.resolve_device('cpu'), torch.device('cpu'))
            imported.assert_not_called()

    def test_missing_npu_fails_before_device_parsing(self):
        with patch.object(backend.importlib, 'import_module', side_effect=ImportError('missing')):
            with self.assertRaisesRegex(RuntimeError, 'matching PyTorch/torch_npu/CANN'):
                backend.resolve_device('npu:0')

    def test_registration_before_parsing_and_index_validation(self):
        npu = SimpleNamespace(is_available=lambda: True, device_count=lambda: 8, set_device=Mock())
        def register(name):
            self.assertEqual(name, 'torch_npu')
            torch.npu = npu
        with patch.object(torch, 'npu', None, create=True), patch.object(backend.importlib, 'import_module', side_effect=register):
            with patch.object(torch, 'device', side_effect=lambda v: (v, torch.npu is npu)):
                self.assertEqual(backend.resolve_device('npu:7'), ('npu:7', True))
            npu.set_device.assert_called_once_with(7)
            with self.assertRaisesRegex(ValueError, 'outside'):
                backend.resolve_device('npu:8')

    def test_npu_rng_tracks_only_owned_device_and_rejects_topology_change(self):
        generator = torch.Generator().manual_seed(678)
        npu = SimpleNamespace(is_initialized=lambda: True, is_available=lambda: True,
            current_device=lambda: 3, device_count=lambda: 8,
            get_rng_state=lambda index: generator.get_state(),
            set_rng_state=lambda state, index: generator.set_state(state))
        with patch.object(torch, 'npu', npu, create=True):
            state = capture_rng()
            self.assertEqual(state['npu']['device_index'], 3)
            expected = torch.rand(4, generator=generator)
            restore_rng(state)
            torch.testing.assert_close(torch.rand(4, generator=generator), expected, rtol=0, atol=0)
            npu.device_count = lambda: 4
            with self.assertRaisesRegex(ValueError, 'NPU topology'):
                restore_rng(state)

    def test_retry_only_allocator_oom(self):
        self.assertTrue(backend.is_accelerator_oom(RuntimeError('NPU out of memory. Tried to allocate'), 'npu:0'))
        for message in ('ACL internal error', 'CPU out of memory', 'unsupported operator'):
            self.assertFalse(backend.is_accelerator_oom(RuntimeError(message), 'npu:0'))
        self.assertFalse(backend.is_accelerator_oom(RuntimeError('NPU out of memory'), 'cpu'))

    def test_legacy_cpu_checkpoint_rng(self):
        state = capture_rng()
        state.pop('npu')
        expected = torch.rand(3)
        restore_rng(state)
        torch.testing.assert_close(torch.rand(3), expected, atol=0, rtol=0)
