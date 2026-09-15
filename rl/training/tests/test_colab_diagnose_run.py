"""Offline Drive diagnostics use metadata only, never a live learner or weights."""
import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


COLAB = Path(__file__).resolve().parents[1] / 'colab'
sys.path.insert(0, str(COLAB))
from diagnose_run import diagnose_run, resource_summary


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf8')


def checksum(data):
    return {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


class DiagnoseRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'mounted-drive'
        self.name = 'hif-setup-mixed-v4-2'
        self.run = self.root / self.name
        self.identity = {'schema': 'gakumas-colab-run/1', 'run_name': self.name,
            'task': 'full_produce', 'config': {'task': 'full_produce', 'workers': 20,
                'episodes_per_update': 80, 'eval_every_updates': 5, 'eval_episodes': 10,
                'ppo': {'minibatch_size': 512, 'microbatch_size': 64}}}
        self.identity_hash = hashlib.sha256(canonical(self.identity)).hexdigest()
        write_json(self.run / 'run-identity.json', self.identity)

    def snapshot(self, generation=19, iteration=7, *, logs=None, state_overrides=None):
        path = self.run / 'snapshots' / f'snapshot-{generation:08d}'
        state = {'identity_sha256': self.identity_hash, 'iteration': iteration,
                 'policy_version': iteration, 'seed_cursor': 92000000 + iteration * 80,
                 'episodes_seen': iteration * 80, 'active_wall_seconds': 20000,
                 'status': 'ready', **(state_overrides or {})}
        state_bytes = canonical(state)
        weights = b'not-a-torch-checkpoint:diagnostics-must-not-open-this'
        (path / 'checkpoints').mkdir(parents=True)
        (path / 'checkpoints/latest.pt').write_bytes(weights)
        (path / 'colab-state.json').write_bytes(state_bytes)
        manifest = {'schema': 'gakumas-mounted-snapshot/1', 'generation': generation,
            'identity_sha256': self.identity_hash,
            'files': {'colab-state.json': checksum(state_bytes),
                      'checkpoints/latest.pt': checksum(weights)}, 'logs': logs or {}}
        manifest_bytes = canonical(manifest)
        (path / 'snapshot.json').write_bytes(manifest_bytes)
        write_json(path / 'COMMITTED.json', {'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest()})
        return path

    def chunk(self, name, data):
        relative = 'log-chunks/' + name
        path = self.run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {'path': relative, **checksum(data)}

    def test_committed_snapshot_reports_iteration_not_generation(self):
        self.snapshot(generation=19, iteration=7)
        report = diagnose_run(self.root, self.name)
        self.assertEqual(report['latest_saved_state']['iteration'], 7)
        self.assertEqual(report['saved_snapshots'][0]['generation'], 19)
        self.assertEqual(report['latest_saved_state']['identity_sha256'], self.identity_hash)
        self.assertEqual(report['initial_config']['episodes_per_update'], 80)
        self.assertIn('checkpoint size only', report['saved_snapshots'][0]['validation'])
        self.assertIn('Full weight integrity', report['saved_snapshots'][0]['validation'])

    def test_weights_are_stat_only_and_diagnostics_do_not_modify_run(self):
        self.snapshot()
        before = {str(p.relative_to(self.root)): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        original_open, original_read = Path.open, Path.read_bytes
        opened_weights = []
        def guarded_open(path, *args, **kwargs):
            if path.suffix == '.pt':
                opened_weights.append(str(path))
                raise AssertionError('Diagnostics opened model/optimizer weights')
            return original_open(path, *args, **kwargs)
        def guarded_read(path, *args, **kwargs):
            if path.suffix == '.pt':
                opened_weights.append(str(path))
                raise AssertionError('Diagnostics read model/optimizer weights')
            return original_read(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded_open), patch.object(Path, 'read_bytes', guarded_read):
            report = diagnose_run(self.root, self.name)
        self.assertEqual(report['latest_saved_state']['iteration'], 7)
        self.assertEqual(opened_weights, [])
        after = {str(p.relative_to(self.root)): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_corrupt_newer_metadata_warns_and_falls_back_to_older_snapshot(self):
        self.snapshot(generation=10, iteration=7)
        for generation, kind in ((11, 'state_hash'), (12, 'manifest_hash'), (13, 'state_identity')):
            with self.subTest(kind=kind):
                bad = self.snapshot(generation=generation, iteration=8,
                    state_overrides={'identity_sha256': 'different-run'} if kind == 'state_identity' else None)
                if kind == 'state_hash':
                    (bad / 'colab-state.json').write_bytes(b'{}')
                elif kind == 'manifest_hash':
                    (bad / 'snapshot.json').write_bytes(b'{}')
                report = diagnose_run(self.root, self.name)
                self.assertEqual(report['latest_saved_state']['iteration'], 7)
                self.assertEqual([row['generation'] for row in report['saved_snapshots']], [10])
                self.assertTrue(any(bad.name in warning for warning in report['warnings']))

    def test_metric_tail_recovers_last_three_records_across_split_log_chunks(self):
        records = [{'iteration': i, 'namespace': 'training', 'episodes': 80,
                    'raw_score_mean': 1000 + i, 'ppo': {'optimizer_steps': 20,
                        'kl_stop_reason': None, 'unneeded_details': ['large']} }
                   for i in range(1, 8)]
        lines = [canonical(row) + b'\n' for row in records]
        data = b''.join(lines)
        # Deliberately split inside rows; individual chunks need not be JSONL.
        cut_one = len(b''.join(lines[:2])) + 17
        cut_two = len(b''.join(lines[:5])) + 29
        chunks = [self.chunk(f'train-{i}', part) for i, part in enumerate(
            (data[:cut_one], data[cut_one:cut_two], data[cut_two:]))]
        evaluation = self.chunk('eval', canonical({'iteration': 5, 'namespace': 'evaluation',
                                                  'raw_score_mean': 1600}) + b'\n')
        self.snapshot(logs={'training/metrics.jsonl': {'chunks': chunks},
                            'evaluation/metrics.jsonl': {'chunks': [evaluation]}})
        report = diagnose_run(self.root, self.name)
        self.assertEqual([row['iteration'] for row in report['training_metrics']], [5, 6, 7])
        self.assertEqual(report['evaluation_metrics'][0]['iteration'], 5)
        self.assertNotIn('unneeded_details', report['training_metrics'][-1]['ppo'])

    def test_newer_preflight_only_directory_does_not_hide_older_training_console(self):
        self.snapshot()
        diagnostics = self.root / '_session_diagnostics' / self.name
        old = diagnostics / '20260911-080000'
        old.mkdir(parents=True)
        (old / 'training-console.log').write_text('old first\niteration 7 committed\n', encoding='utf8')
        recent = diagnostics / '20260912-090000'
        recent.mkdir()
        (recent / 'preflight.log').write_text('preflight only', encoding='utf8')
        (recent / 'resources.jsonl').write_text('{"host_ram": 123}\n', encoding='utf8')
        report = diagnose_run(self.root, self.name, tail_lines=1)
        self.assertEqual(len(report['console_logs']), 1)
        self.assertEqual(report['console_logs'][0]['tail'], 'iteration 7 committed')
        self.assertIn(old.name, report['console_logs'][0]['path'])
        self.assertIn(recent.name, report['resource_logs'][0]['path'])
        self.assertFalse(any('No training-console.log' in warning for warning in report['warnings']))

    def test_saved_pid_is_historical_and_control_error_is_not_training_failure(self):
        self.snapshot()
        write_json(self.root / '_notebook_sessions' / (self.name + '.json'),
                   {'pid': 45678, 'returncode': None, 'started_at': '2026-09-01T00:00:00Z'})
        write_json(self.root / '_runtime_controls' / (self.name + '.status.json'),
                   {'last_error': 'microbatch_size must not exceed minibatch_size', 'stage': 'update'})
        report = diagnose_run(self.root, self.name)
        self.assertEqual(report['historical_session_lease']['pid'], 45678)
        self.assertIsNone(report['historical_session_lease']['returncode'])
        self.assertNotIn('running', report)
        self.assertNotIn('live', report)
        self.assertIn('no live process check', report['scope'])
        self.assertIn('does not establish', report['historical_status_note'])
        self.assertIn('control requests', report['historical_status_note'])
        self.assertEqual(report['latest_saved_state']['status'], 'ready')
        self.assertNotIn('last_error', report['latest_saved_state'])

    def test_fresh_module_requires_no_torch_zip_or_previous_notebook_globals(self):
        self.snapshot()
        imported = []
        original_import = builtins.__import__
        def restricted_import(name, *args, **kwargs):
            imported.append(name)
            if name.split('.')[0] in {'torch', 'zipfile', 'psutil', 'notebook_session', 'gakumas_training'}:
                raise AssertionError('Offline diagnosis imported a training/live dependency: ' + name)
            return original_import(name, *args, **kwargs)
        spec = importlib.util.spec_from_file_location('fresh_offline_diagnostic', COLAB / 'diagnose_run.py')
        module = importlib.util.module_from_spec(spec)
        with patch('builtins.__import__', side_effect=restricted_import):
            spec.loader.exec_module(module)
            report = module.diagnose_run(self.root, self.name)
        self.assertEqual(report['latest_saved_state']['iteration'], 7)
        for name in ('TRAINING_SESSION', 'BUNDLE_ROOT', 'RUN_NAME', 'ZIP_PATH'):
            self.assertNotIn(name, vars(module))
        self.assertFalse(list(self.root.rglob('*.zip')))

    def test_bad_metric_chunk_does_not_fabricate_metrics_or_hide_valid_state(self):
        record = self.chunk('metrics-corrupt', canonical({'iteration': 7}) + b'\n')
        self.snapshot(logs={'training/metrics.jsonl': {'chunks': [record]}})
        (self.run / record['path']).write_bytes(b'{"iteration":999}\n')
        report = diagnose_run(self.root, self.name)
        self.assertEqual(report['latest_saved_state']['iteration'], 7)
        self.assertNotIn('training_metrics', report)
        self.assertTrue(any('training metrics' in warning and 'checksum mismatch' in warning
                            for warning in report['warnings']))

    def test_resource_summary_groups_comparable_stages_and_preserves_first_last_extrema(self):
        path = self.root / 'resource-history.jsonl'
        samples = []
        for index, (stage, root, workers, available, count) in enumerate((
                ('collection', 12, 20, 40, 20), ('collection', 22, 24, 18, 24),
                ('update', 19, 0, 42, 0), ('update', 16, 0, 47, 0))):
            samples.append({'event': 'resource_sample', 'observer_id': 'observer-one',
                'timestamp': f'2026-09-12T00:00:0{index}Z',
                'runtime_status': {'iteration': 7, 'stage': stage},
                'tree_enumeration_complete': True, 'tree_classification_complete': True,
                'groups': {'root': {'pss_bytes': {'total': root * 2**30}},
                           'workers': {'pss_bytes': {'total': workers * 2**30}},
                           'all': {'pss_bytes': {'total': (root + workers) * 2**30}}},
                'system_memory': {'available_bytes': available * 2**30},
                'processes': ([{'spawn_worker': True}] * count
                              + [{'spawn_worker': False}, {'kind': 'node'}, {'kind': 'resource_tracker'}])})
        path.write_bytes(b''.join(canonical(row) + b'\n' for row in samples))
        summary = resource_summary(path)
        self.assertEqual(summary['invalid_lines'], 0)
        self.assertFalse(summary['truncated'])
        groups = {row['stage']: row for row in summary['stages']}
        self.assertEqual(set(groups), {'collection', 'update'})
        for group in groups.values():
            self.assertEqual(group['iteration'], 7)
            self.assertEqual(group['samples'], 2)
        self.assertEqual(groups['collection']['metrics']['root_pss_gib'],
            {'first': 12., 'last': 22., 'min': 12., 'max': 22., 'valid_samples': 2})
        self.assertEqual(groups['update']['metrics']['root_pss_gib'],
            {'first': 19., 'last': 16., 'min': 16., 'max': 19., 'valid_samples': 2})
        self.assertEqual(groups['collection']['metrics']['system_available_gib']['min'], 18.)
        self.assertEqual(groups['collection']['metrics']['worker_count'],
            {'first': 20, 'last': 24, 'min': 20, 'max': 24, 'valid_samples': 2})
        self.assertEqual(groups['update']['metrics']['worker_count']['last'], 0)

    def test_incomplete_resource_tree_missing_pss_and_bad_tail_are_not_reported_as_zero(self):
        self.snapshot()
        path = self.root / '_session_diagnostics' / self.name / '20260912-120000' / 'resources-observer-a83f.jsonl'
        path.parent.mkdir(parents=True)
        base = {'event': 'resource_sample', 'observer_id': 'observer-a83f',
                'runtime_status': {'iteration': 7, 'stage': 'collection'},
                'groups': {'root': {'pss_bytes': {'total': None}},
                           'workers': {'pss_bytes': {'total': 99 * 2**30}},
                           'all': {'pss_bytes': {'total': 100 * 2**30}}},
                'processes': [{'spawn_worker': True}], 'system_memory': {'available_bytes': None}}
        rows = [{**base, 'tree_enumeration_complete': False, 'tree_classification_complete': True},
                {**base, 'tree_enumeration_complete': True, 'tree_classification_complete': False},
                {'event': 'observer_stopped', 'reason': 'root_exited', 'returncode': None}]
        path.write_bytes(b''.join(canonical(row) + b'\n' for row in rows) + b'{"event":')
        report = diagnose_run(self.root, self.name)
        self.assertEqual(len(report['resource_logs']), 1)
        entry = report['resource_logs'][0]
        self.assertEqual(Path(entry['path']).name, 'resources-observer-a83f.jsonl')
        self.assertIn('{"event":', entry['tail'])
        summary = entry['summary']
        self.assertEqual(summary['invalid_lines'], 1)
        self.assertEqual(summary['stages'][0]['samples'], 2)
        self.assertEqual(summary['stages'][0]['metrics'], {})
        self.assertEqual(summary['events'][-1]['event'], 'observer_stopped')
        self.assertIn('missing metrics remain absent', summary['note'])


if __name__ == '__main__':
    unittest.main()
