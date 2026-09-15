"""Bounded fake-process coverage; optional real psutil child lifecycle."""
from copy import deepcopy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / 'colab/resource_watch.py'
spec = importlib.util.spec_from_file_location('resource_watch_fixture', SOURCE)
watch = importlib.util.module_from_spec(spec); spec.loader.exec_module(watch)


class Missing(Exception):
    pass


class FakeProcess:
    def __init__(self, pid, ppid, *, name='python', command='', rss=100, pss=60, uss=40,
                 created=1000., status='running', children=(), details_error=False):
        self.pid, self.parent, self.label, self.command = pid, ppid, name, command
        self.rss, self.pss, self.uss, self.created = rss, pss, uss, created
        self.state, self.descendants, self.details_error = status, children, details_error
    def ppid(self): return self.parent
    def name(self): return self.label
    def cmdline(self): return self.command.split()
    def create_time(self): return self.created
    def status(self): return self.state
    def children(self, recursive=True): return self.descendants
    def memory_info(self):
        if self.rss is None: raise PermissionError('RSS unavailable')
        return SimpleNamespace(rss=self.rss)
    def memory_full_info(self):
        if self.details_error: raise PermissionError('PSS/USS unavailable')
        return SimpleNamespace(pss=self.pss, uss=self.uss)


def fake_psutil(process):
    return SimpleNamespace(Process=Mock(return_value=process), NoSuchProcess=Missing, ZombieProcess=Missing,
                           virtual_memory=lambda: SimpleNamespace(total=10000, available=3000))


class ResourceWatchTests(unittest.TestCase):
    def test_worker_node_subtrees_root_and_other_children_deduplicate(self):
        worker = FakeProcess(2, 1, command='python -c from multiprocessing.spawn import spawn_main')
        node = FakeProcess(3, 2, name='node', rss=70, pss=30, uss=20)
        tracker = FakeProcess(4, 1, command='python multiprocessing.resource_tracker')
        root_node = FakeProcess(5, 1, name='node', rss=50, pss=20, uss=10)
        root = FakeProcess(1, 0, children=[worker, node, tracker, root_node, node])
        result = watch.process_tree(root)
        self.assertEqual(len(result['processes']), 5)
        self.assertEqual(result['groups']['workers']['process_count'], 2)
        self.assertEqual(result['groups']['workers']['rss_bytes']['total'], 170)
        self.assertEqual(result['groups']['other_children']['rss_bytes']['total'], 150)
        self.assertEqual(result['groups']['root']['rss_bytes']['total'], 100)
        self.assertEqual(result['groups']['all']['rss_bytes']['total'], 420)
        self.assertEqual(sum(r['native_node'] for r in result['processes']), 2)

    def test_partial_reads_remain_null_and_never_substitute_rss_for_pss(self):
        root = FakeProcess(1, 0, children=[FakeProcess(2, 1, details_error=True, rss=300)])
        result = watch.process_tree(root)
        pss = result['groups']['all']['pss_bytes']
        self.assertIsNone(pss['total']); self.assertEqual(pss['observed_sum'], 60)
        self.assertEqual(pss['missing_count'], 1)
        self.assertEqual(result['groups']['all']['rss_bytes']['total'], 400)
        absent = watch.memory_reading(FakeProcess(2, 1, rss=None, details_error=True))
        self.assertIsNone(absent['rss_bytes']); self.assertIsNone(absent['pss_bytes'])
        self.assertIsNone(absent['uss_bytes']); self.assertEqual(len(absent['errors']), 2)
        preferred = FakeProcess(3, 1)
        preferred.memory_footprint = lambda: SimpleNamespace(pss=20, uss=10)
        self.assertEqual(watch.memory_reading(preferred)['pss_bytes'], 20)

    def test_pid_reuse_missing_or_zombie_stops_with_unknown_exit_code(self):
        for status in ('reuse', 'zombie', 'missing'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                api = fake_psutil(FakeProcess(1, 0, created=2000. if status == 'reuse' else 1000.,
                                             status='zombie' if status == 'zombie' else 'running'))
                if status == 'missing': api.Process.side_effect = Missing('gone')
                output = Path(temporary)/'watch.jsonl'
                with patch.object(watch, 'gpu_sample', side_effect=AssertionError('no GPU query for gone target')):
                    watch.observe(1, 1000., output=output, psutil_module=api, sleep=Mock(), max_samples=3)
                records = [json.loads(line) for line in output.read_text().splitlines()]
                self.assertEqual([r['event'] for r in records], ['observer_started', 'process_disappeared'])
                self.assertIsNone(records[-1]['returncode'])
                self.assertEqual(api.Process.call_count, 1)

    def test_drive_failure_does_not_stop_local_logging_and_is_retried(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); drive, local = root/'drive/log.jsonl', root/'local/log.jsonl'
            original = watch.append_record; failures = []
            def append(path, record):
                if path == drive and len(failures) < 1:
                    failures.append(True); raise OSError('Drive temporarily unavailable')
                original(path, record)
            with patch.object(watch, 'append_record', side_effect=append), \
                 patch.object(watch, 'gpu_sample', return_value={'gpus': None, 'error': 'no GPU'}), \
                 patch.object(watch, 'cgroup_memory', return_value={'current_bytes': None}), \
                 contextlib.redirect_stderr(io.StringIO()) as errors:
                watch.observe(1, 1000., output=drive, local_output=local, psutil_module=fake_psutil(FakeProcess(1, 0)),
                              sleep=Mock(), max_samples=2)
            self.assertIn('Drive temporarily unavailable', errors.getvalue())
            self.assertEqual(len(local.read_text().splitlines()), 3)
            self.assertEqual(len(drive.read_text().splitlines()), 2)
            data = json.loads(local.read_text().splitlines()[-1])
            self.assertEqual(data['system_memory']['available_bytes'], 3000)
            self.assertEqual(data['gpu']['error'], 'no GPU')
            with self.assertRaises(FileExistsError):
                watch.observe(1, 1000., output=local, psutil_module=fake_psutil(FakeProcess(1, 0)), max_samples=0)

    def test_cgroup_records_real_source_paths_and_event_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); proc, mount = root/'proc', root/'cgroup'
            (proc/'123').mkdir(parents=True); (mount/'sample').mkdir(parents=True)
            (proc/'123/cgroup').write_text('0::/sample\n')
            (mount/'sample/memory.current').write_text('1234')
            (mount/'sample/memory.max').write_text('max')
            (mount/'sample/memory.events').write_text('oom 2\noom_kill 1\n')
            with patch.object(watch.platform, 'system', return_value='Linux'):
                result = watch.cgroup_memory(123, proc, mount)
            self.assertEqual(result['current_bytes'], 1234)
            self.assertEqual(result['max_bytes'], 'max')
            self.assertEqual(result['events'], {'oom': 2, 'oom_kill': 1})
            self.assertEqual(result['path'], str((mount/'sample').resolve()))

    def test_nvidia_timeout_is_bounded_nonfatal_and_unavailable_values_stay_null(self):
        with patch.object(watch.shutil, 'which', return_value='nvidia-smi'), \
             patch.object(watch.subprocess, 'run', side_effect=subprocess.TimeoutExpired('nvidia-smi', 3)) as run:
            result = watch.gpu_sample()
            self.assertIsNone(result['gpus']); self.assertIn('TimeoutExpired', result['error'])
            self.assertEqual(run.call_args.kwargs['timeout'], 3)
        with patch.object(watch.shutil, 'which', return_value='nvidia-smi'), \
             patch.object(watch.subprocess, 'run', return_value=SimpleNamespace(stdout='0, [N/A], 10, 80\n')):
            self.assertIsNone(watch.gpu_sample()['gpus'][0]['utilization_percent'])

    @unittest.skipUnless(importlib.util.find_spec('psutil'), 'Local test Python has no psutil installed')
    def test_owned_short_child_disappears_without_observer_killing_it(self):
        import psutil
        with tempfile.TemporaryDirectory() as temporary:
            process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(.2)'],
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                created = psutil.Process(process.pid).create_time()
                output = Path(temporary)/'resource.jsonl'
                with patch.object(watch, 'gpu_sample', return_value={'gpus': None}), \
                     patch.object(watch, 'cgroup_memory', return_value={'current_bytes': None}):
                    watch.observe(process.pid, created, output=output, psutil_module=psutil,
                                  sleep=lambda _: process.wait(timeout=5), max_samples=3)
                rows = [json.loads(line) for line in output.read_text().splitlines()]
                self.assertEqual(rows[-1]['event'], 'process_disappeared')
                self.assertEqual(process.wait(timeout=5), 0)
            finally:
                if process.poll() is None: process.kill(); process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
