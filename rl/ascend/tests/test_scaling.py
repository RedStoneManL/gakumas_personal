"""Scale configuration reaches runtime consumers without allocating large jobs."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from draftrl.async_service import SearchService
from draftrl.process_service import ProcessSearchService
from draftrl.resource_modes import RuntimeResources


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'configure.py' if (ROOT / 'configure.py').is_file() else ROOT / 'scripts/configure.py'
spec = importlib.util.spec_from_file_location('ascend_configure', SCRIPT)
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


class ScalingTests(unittest.TestCase):
    def test_dashboard_scale_request_rebuilds_same_mode_pool_at_batch_boundary(self):
        from datetime import datetime, timezone
        config, _ = self.bases()
        config['device'] = 'cpu'
        first_pool, next_pool = Mock(), Mock()
        factory = Mock(side_effect=[first_pool, next_pool])
        with tempfile.TemporaryDirectory() as directory:
            resource = RuntimeResources(directory, 'cluster')
            with patch('draftrl.resource_modes.apply_settings'):
                pool, _ = resource.apply(resource.requested(), config, 0, None, factory)
                value = {'schema': 'arena-resource-mode/1', 'mode': 'cluster', 'request_id': 'resize',
                         'requested_at': datetime.now(timezone.utc).isoformat(),
                         'parallelism': dict(workers=1024, parallel_roots=512, inference_batch=1024, microbatch=8, torch_threads=32)}
                pool, changed = resource.apply(value, config, 4, pool, factory)
                self.assertTrue(changed)
                self.assertIs(pool, next_pool)
                first_pool.close.assert_called_once()
                factory.assert_called_with(1024)
                self.assertEqual(resource.current['parallel_roots'], 512)
                self.assertEqual(resource.current['applied_after_batch'], 4)
                self.assertEqual(config['minibatch'], 8)

    def bases(self):
        return [json.loads((ROOT / 'configs' / name).read_text(encoding='utf-8'))
                for name in ('search_8npu.json', 'full_produce_npu.json')]

    def test_cli_generates_both_configs_above_previous_limits_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            configure.main(['--output-dir', directory, '--learners', '32', '--workers', '1024',
                            '--search-workers', '512', '--inference-batch', '1024',
                            '--batch-decisions', '1000000', '--episodes-per-update', '100000',
                            '--minibatch-size', '32768', '--microbatch-size', '2048',
                            '--torch-threads', '128', '--device', 'cpu'])
            search = json.loads((Path(directory) / 'search.json').read_text(encoding='utf-8'))
            full = json.loads((Path(directory) / 'full_produce.json').read_text(encoding='utf-8'))
            self.assertEqual(search['learner_world_size'], 32)
            self.assertEqual(search['batch_decisions'], 1000000)
            self.assertEqual(search['effective_minibatch'], 32768)
            self.assertEqual(search['parallelism'], dict(workers=1024, parallel_roots=512,
                inference_batch=1024, microbatch=2048, torch_threads=128))
            self.assertEqual((full['workers'], full['episodes_per_update'], full['torch_threads']),
                             (1024, 100000, 128))
            self.assertEqual(full['ppo']['microbatch_size'], 2048)
            self.assertEqual(full['ppo']['minibatch_size'], 32768)
            self.assertEqual(search['device'], full['device'])
            self.assertEqual(search['device'], 'cpu')
            before = {path.name: path.read_bytes() for path in Path(directory).iterdir()}
            with self.assertRaises(FileExistsError):
                configure.main(['--output-dir', directory, '--workers', '1'])
            self.assertEqual({path.name: path.read_bytes() for path in Path(directory).iterdir()}, before)

    def test_generator_preserves_algorithm_and_rejects_invalid_scale_before_writing(self):
        search, full = self.bases()
        before = deepcopy((search, full))
        result = configure.configurations(search, full, workers=256)
        self.assertEqual((search, full), before)
        for name in ('search', 'practice', 'value_calibration', 'learning_rate_schedule'):
            self.assertEqual(result['search.json'][name], search[name])
        for field in configure.FIELDS:
            for value in (0, -1, True, 1.5):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    configure.configurations(search, full, **{field: value})
        with self.assertRaisesRegex(ValueError, 'must not exceed'):
            configure.configurations(search, full, microbatch_size=513, minibatch_size=512)
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            configure.configurations(search, full, workres=256)

    def test_cluster_overrides_reach_pool_and_training_config(self):
        search, _ = self.bases()
        search = configure.configurations(search, self.bases()[1], workers=1024, search_workers=512,
            inference_batch=1024, microbatch_size=2048, minibatch_size=32768, torch_threads=128)['search.json']
        search['device'] = 'cpu'
        factory = Mock(return_value=Mock())
        with tempfile.TemporaryDirectory() as directory:
            resources = RuntimeResources(directory, 'cluster')
            with patch('draftrl.resource_modes.apply_settings') as apply:
                pool, changed = resources.apply(resources.requested(), search, 0, None, factory)
            factory.assert_called_once_with(1024)
            self.assertIs(pool, factory.return_value)
            self.assertTrue(changed)
            self.assertEqual(apply.call_args.args[0]['torch_threads'], 128)
            self.assertEqual(resources.current['parallel_roots'], 512)
            self.assertEqual(resources.current['inference_batch'], 1024)
            self.assertEqual((search['workers'], search['minibatch'], search['torch_threads']), (1024, 2048, 128))

    def test_search_service_no_longer_rejects_cluster_defaults_or_large_overrides(self):
        for roots, batch in ((24, 32), (512, 1024)):
            with self.subTest(roots=roots), SearchService(None, 'cpu', parallel_roots=roots,
                                                        inference_batch=batch) as service:
                self.assertEqual(service.inference_batch, batch)
                self.assertEqual(service.executor._max_workers, roots)
            # Run the production process-service constructor but mock OS pools
            # and queues: this verifies propagation, not 512-process capacity.
            with patch('draftrl.process_service.mp.get_context'), \
                 patch('draftrl.process_service.ProcessPoolExecutor') as executor:
                with ProcessSearchService(None, 'cpu', parallel_roots=roots, inference_batch=batch) as service:
                    self.assertEqual(service.inference_batch, batch)
                    self.assertEqual(len(service.response_queues), roots)
                    self.assertEqual(executor.call_args.kwargs['max_workers'], roots)

    def test_invalid_search_service_values_fail_before_allocating_executors(self):
        for field in ('parallel_roots', 'inference_batch'):
            for value in (0, -1, True, 1.5):
                with patch('draftrl.async_service.ThreadPoolExecutor') as executor:
                    with self.assertRaises(ValueError):
                        ProcessSearchService(None, 'cpu', **{field: value})
                    executor.assert_not_called()


if __name__ == '__main__':
    unittest.main()
