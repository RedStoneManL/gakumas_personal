"""Execute the generated Notebook cache cell with bounded fake subprocesses."""
from copy import deepcopy
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


COLAB = Path(__file__).resolve().parents[1] / 'colab'
spec = importlib.util.spec_from_file_location('preflight_cache_notebook_builder', COLAB / 'build_notebook.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

RUNTIME = {'python': '3.12.0 (fixture)', 'node': 'v22.22.0', 'torch': '2.9.0+cu128',
           'cuda_runtime': '12.8', 'device': 'cuda', 'cuda_available': True,
           'gpu': 'A100 fixture', 'gpu_total_bytes': 80 * 2**30}


def task_row(task, profile=None, mode=None):
    return {'task': task, 'loadout_profile': profile, 'setup_mode': mode,
            'real_episode_raw_score': 10., 'termination': 'failed' if task == 'full_produce' else 'normal',
            'decisions': 2, 'decision_kinds': {'outer' if task == 'full_produce' else 'exam_action': 2},
            'gradient_abs_sum': 1., 'model_probes': [{'decision_kind': 'fixture', 'gradient_abs_sum': 1.}],
            'configured_batch_probe': {'forward_backward_finite': True, 'graphs': 2},
            'arena_version': {'fixture': 'same-bundle-arena'}}


class CacheCellTests(unittest.TestCase):
    def fixture(self, root, *, config=None):
        bundle = root / 'bundle'; (bundle / 'colab').mkdir(parents=True)
        (bundle / 'configs').mkdir()
        config = config or {'task': 'full_produce', 'task_config': {'setup_mode': 'given', 'loadout_pool': None}}
        config_path = root / 'effective.json'
        config_path.write_text(json.dumps(config, indent=2), encoding='utf8')
        (bundle / 'configs/full_produce.json').write_text(json.dumps(config), encoding='utf8')
        (bundle / 'configs/exam_score.json').write_text(json.dumps({'task': 'exam_score', 'task_config': {}}), encoding='utf8')
        return {'BUNDLE_ROOT': bundle, 'persistent': root / 'drive', 'RUN_NAME': 'same-v4-run',
            'CONFIG_PATH': config_path, 'MANIFEST_SHA256': 'frozen-v4-manifest',
            'RUN_PYTHON': Path('/fixture/python'), 'ENV': {}, 'Path': Path, 'sys': sys,
            'json': json, 'hashlib': hashlib, 'datetime': datetime, 'TASK': config['task'],
            'selected_config': config, 'PREFLIGHT': {'passed': True, 'stale': True}}

    def report(self, namespace, *, runtime=None):
        config = json.loads(namespace['CONFIG_PATH'].read_text())
        full = config if config['task'] == 'full_produce' else json.loads(
            (namespace['BUNDLE_ROOT']/'configs/full_produce.json').read_text())
        task_config = full.get('task_config', {})
        names = [r['name'] for r in task_config.get('loadout_pool') or []] or [None]
        mode = task_config.get('setup_mode', 'given')
        modes = ['given', 'select'] if mode == 'mixed' else [mode]
        return {'schema': 'hif-colab-preflight/1', 'passed': True,
                'scope': 'Original complete v4 report, without cache fields',
                'manifest_sha256': namespace['MANIFEST_SHA256'],
                'selected_config_sha256': hashlib.sha256(namespace['CONFIG_PATH'].read_bytes()).hexdigest(),
                'runtime': deepcopy(runtime or RUNTIME),
                'tasks': [task_row('exam_score'), *[task_row('full_produce', name, value)
                         for name in names for value in modes]]}

    def prior(self, namespace, payload, *, stamp='20260911-000000-UTC', raw=None):
        path = namespace['persistent']/'_session_diagnostics'/namespace['RUN_NAME']/stamp/'preflight.json'
        path.parent.mkdir(parents=True)
        path.write_bytes(raw if raw is not None else json.dumps(payload, ensure_ascii=False, indent=4).encode('utf8'))
        return path

    def execute(self, namespace, *, force=False, runtime=None, quick_error=None, quick_pass=True,
                full_transform=None):
        source = next(c['source'] for c in builder.notebook()['cells']
                      if c['cell_type'] == 'code' and '# 6.' in c['source'])
        if force:
            source = source.replace('FORCE_PREFLIGHT = False', 'FORCE_PREFLIGHT = True', 1)
        runtime = runtime or RUNTIME
        quick = Mock(side_effect=quick_error) if quick_error else Mock(return_value=json.dumps(
            {'runtime': runtime, 'cuda_smoke_passed': quick_pass}))
        def write_report(command, logfile, **kwargs):
            output = Path(command[command.index('--output')+1])
            report = self.report(namespace, runtime=runtime)
            if full_transform:
                full_transform(report)
            output.write_text(json.dumps(report), encoding='utf8')
        full = Mock(side_effect=write_report)
        helper = ModuleType('process_utils'); helper.run_logged = full
        namespace['subprocess'] = SimpleNamespace(check_output=quick)
        namespace['_quick_mock'], namespace['_full_mock'] = quick, full
        with patch.dict(sys.modules, {'process_utils': helper}), patch.object(sys, 'path', list(sys.path)), \
                contextlib.redirect_stdout(io.StringIO()):
            exec(compile(source, 'generated-step-6', 'exec'), namespace)
        return quick, full

    def test_existing_v4_full_report_reused_with_exact_original_byte_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            ns = self.fixture(Path(temporary))
            report = self.report(ns)
            original = ('\n  '+json.dumps(report, ensure_ascii=False, indent=3)+'\n').encode('utf8')
            source = self.prior(ns, report, raw=original)
            quick, full = self.execute(ns)
            quick.assert_called_once(); full.assert_not_called()
            self.assertTrue(ns['PREFLIGHT']['cache_reused'])
            self.assertEqual(ns['PREFLIGHT']['reused_from'], str(source))
            self.assertEqual(ns['PREFLIGHT']['reused_report_sha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(ns['PREFLIGHT']['tasks'], report['tasks'])
            self.assertEqual(json.loads(ns['PREFLIGHT_PATH'].read_text()), ns['PREFLIGHT'])
            self.assertIn('loss.backward()', quick.call_args.args[0][3])
            self.assertTrue((ns['DIAGNOSTICS']/'runtime-check.json').is_file())

    def test_hardware_config_manifest_and_runtime_mismatch_fall_back_to_full(self):
        changes = [lambda r: r['runtime'].update(gpu_total_bytes=40*2**30),
                   lambda r: r['runtime'].update(gpu='Different GPU'),
                   lambda r: r['runtime'].update(torch='2.8.0'),
                   lambda r: r.update(selected_config_sha256='different-config'),
                   lambda r: r.update(manifest_sha256='different-bundle')]
        for mutate in changes:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as temporary:
                ns = self.fixture(Path(temporary)); old = self.report(ns); mutate(old)
                self.prior(ns, old)
                _, full = self.execute(ns)
                full.assert_called_once()
                self.assertTrue(ns['PREFLIGHT']['passed'])
                self.assertFalse(ns['PREFLIGHT'].get('cache_reused', False))

    def test_force_full_and_reused_report_alone_do_not_bypass_full_probe(self):
        for force, reused in [(True, False), (False, True)]:
            with self.subTest(force=force, reused=reused), tempfile.TemporaryDirectory() as temporary:
                ns = self.fixture(Path(temporary)); report = self.report(ns)
                if reused:
                    report['cache_reused'] = True
                self.prior(ns, report)
                _, full = self.execute(ns, force=force)
                full.assert_called_once()

    def test_failed_corrupt_thin_and_wrong_schema_reports_fall_back(self):
        variants = [('failed', lambda r: r.update(passed=False)),
                    ('schema', lambda r: r.update(schema='old-schema')),
                    ('thin', lambda r: r.update(tasks=[])),
                    ('missing-task', lambda r: r.update(tasks=r['tasks'][:1])),
                    ('malformed-profile', lambda r: r['tasks'][1].update(loadout_profile=[])),
                    ('corrupt', None)]
        for label, mutate in variants:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                ns = self.fixture(Path(temporary)); report = self.report(ns)
                if mutate:
                    mutate(report)
                self.prior(ns, report, raw=b'{broken' if label == 'corrupt' else None)
                _, full = self.execute(ns)
                full.assert_called_once()

    def test_quick_failure_clears_stale_pass_and_never_runs_full_probe(self):
        for kwargs, expected in [({'quick_error': RuntimeError('CUDA unavailable')}, RuntimeError),
                                 ({'quick_pass': False}, RuntimeError)]:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as temporary:
                ns = self.fixture(Path(temporary)); self.prior(ns, self.report(ns))
                with self.assertRaises(expected):
                    self.execute(ns, **kwargs)
                self.assertIsNone(ns['PREFLIGHT'])
                ns['_full_mock'].assert_not_called()
                self.assertFalse(ns['PREFLIGHT_PATH'].exists())

    def test_failed_full_output_does_not_set_passed_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            ns = self.fixture(Path(temporary))
            with self.assertRaises(RuntimeError):
                self.execute(ns, full_transform=lambda r: r.update(passed=False))
            self.assertIsNone(ns['PREFLIGHT'])
            ns['_full_mock'].assert_called_once()

    def test_mixed_profile_coverage_must_include_every_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            ns = self.fixture(Path(temporary), config={'task': 'full_produce', 'task_config': {
                'setup_mode': 'mixed', 'loadout_pool': [
                    {'name': 'a', 'loadout': {}}, {'name': 'b', 'loadout': {}}]}})
            report = self.report(ns); report['tasks'].pop()
            self.prior(ns, report)
            _, full = self.execute(ns)
            full.assert_called_once()
            self.assertEqual(len(ns['PREFLIGHT']['tasks']), 5)

    def test_external_master_override_forces_full_and_active_training_blocks_all_probes(self):
        for name in ('GAKUMAS_RL_ROOT_DIR', 'GAKUMAS_RL_ASSETS_DIR', 'GAKUMAS_MASTERDATA_DIR'):
            with self.subTest(override=name), tempfile.TemporaryDirectory() as temporary:
                ns = self.fixture(Path(temporary)); self.prior(ns, self.report(ns))
                ns['ENV'][name] = '/fixture/external-master'
                _, full = self.execute(ns)
                full.assert_called_once()
        with tempfile.TemporaryDirectory() as temporary:
            ns = self.fixture(Path(temporary)); self.prior(ns, self.report(ns))
            ns['TRAINING_SESSION'] = SimpleNamespace(status=lambda: {'running': True})
            with self.assertRaisesRegex(RuntimeError, '训练仍在运行'):
                self.execute(ns)
            self.assertIsNone(ns['PREFLIGHT'])
            ns['_quick_mock'].assert_not_called()
            ns['_full_mock'].assert_not_called()

    def test_same_config_old_bundle_cannot_pass_step7_gate(self):
        source = next(c['source'] for c in builder.notebook()['cells']
                      if c['cell_type'] == 'code' and '# 7.' in c['source'])
        with tempfile.TemporaryDirectory() as temporary:
            ns = self.fixture(Path(temporary)); ns['PREFLIGHT'] = self.report(ns)
            ns['PREFLIGHT']['manifest_sha256'] = 'prior-bundle'
            # Claim the mount exists, isolating the manifest gate. A bypass
            # would reach command construction/imports which this test never supplies.
            with patch.object(Path, 'is_dir', return_value=True), self.assertRaises(RuntimeError):
                exec(compile(source, 'generated-step-7', 'exec'), ns)

    def test_failed_cache_audit_write_leaves_gate_closed_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            ns = self.fixture(Path(temporary)); prior = self.prior(ns, self.report(ns))
            original = prior.read_bytes()
            write_text = Path.write_text
            def failing_write(path, *args, **kwargs):
                if path.name == 'preflight.json' and path != prior:
                    raise OSError('Drive audit write failed')
                return write_text(path, *args, **kwargs)
            with patch.object(Path, 'write_text', failing_write), self.assertRaisesRegex(OSError, 'audit write failed'):
                self.execute(ns)
            self.assertIsNone(ns['PREFLIGHT'])
            ns['_full_mock'].assert_not_called()
            self.assertEqual(prior.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
