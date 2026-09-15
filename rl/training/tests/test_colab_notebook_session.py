"""Short owned Popen helpers only: no Arena, model, GPU or training."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest
import tempfile


def module():
    path = Path(__file__).resolve().parents[1] / 'colab/notebook_session.py'
    if not path.is_file():
        path = Path(__file__).resolve().parents[2] / 'colab/notebook_session.py'
    spec = importlib.util.spec_from_file_location('session_fixture_' + str(time.time_ns()), path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class NotebookSessionTests(unittest.TestCase):
    def test_nonblocking_live_tail_full_log_duplicate_start_and_safe_stop(self):
        helper = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / 'drive/trial'; run.mkdir(parents=True)
            (run / 'run-identity.json').write_text('{}')
            script = root / 'helper.py'
            script.write_text('import sys,time\nfrom pathlib import Path\n'
                'for i in range(250): print(f"line-{i}",flush=True)\n'
                'print("x"*5000,flush=True)\nprint("stderr-tail",file=sys.stderr,flush=True)\n'
                'deadline=time.monotonic()+10\n'
                'while not Path(sys.argv[1]).exists() and time.monotonic()<deadline: time.sleep(.01)\n'
                'print("safe-boundary-stopped",flush=True)\n')
            args = dict(cwd=root, env=dict(os.environ), persistent_run=run, display=False)
            started = time.monotonic()
            session = helper.start_session([sys.executable, '-u', str(script), str(run/'STOP')], root/'console.log', **args)
            try:
                self.assertLess(time.monotonic()-started, 2.)
                self.assertTrue(session.status()['running'])
                with self.assertRaisesRegex(RuntimeError, '已有训练进程'):
                    helper.start_session([sys.executable, '-c', 'pass'], root/'second.log', **args)
                deadline = time.monotonic()+5
                while 'stderr-tail' not in session.tail() and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertIn('stderr-tail', session.tail())
                self.assertLessEqual(len(session.tail().splitlines()), 200)
                self.assertNotIn('line-0\n', session.tail())
                self.assertIn('display truncated', session.tail())
                self.assertEqual(session.request_stop(), run/'STOP')
                self.assertEqual(session.wait(10)['returncode'], 0)
                self.assertIn('safe-boundary-stopped', session.tail())
                text = (root/'console.log').read_text()
                self.assertIn('line-0\n', text)
                self.assertIn('x'*5000, text)
                self.assertIn('stderr-tail', text)
                again = helper.start_session([sys.executable, '-c', 'print("resumed")'], root/'console.log', **args)
                self.assertEqual(again.wait(10)['returncode'], 0)
                self.assertIn('resumed', (root/'console.log').read_text())
            finally:
                session.terminate_owned(); session.wait(10)

    def test_controls_are_atomic_and_do_not_create_target_before_initialization(self):
        helper = module()
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / 'drive/trial'
            path = helper.write_runtime_control(run, workers=12, episodes_per_update=40,
                                                minibatch_size=128, microbatch_size=32)
            self.assertEqual(path, run.parent/'_runtime_controls/trial.json')
            self.assertFalse(run.exists())
            expected = {'workers': 12, 'episodes_per_update': 40, 'minibatch_size': 128, 'microbatch_size': 32}
            first = json.loads(path.read_text())
            self.assertEqual({k: first[k] for k in expected}, expected)
            self.assertEqual(len(first['_request_id']), 32)
            helper.write_runtime_control(run, **expected)
            second = json.loads(path.read_text())
            self.assertNotEqual(first['_request_id'], second['_request_id'])
            self.assertEqual({k: second[k] for k in expected}, expected)
            expected = {'workers': 1024, 'episodes_per_update': 100000,
                        'minibatch_size': 32768, 'microbatch_size': 2048}
            helper.write_runtime_control(run, **expected)
            second = json.loads(path.read_text())
            self.assertEqual({k: second[k] for k in expected}, expected)
            for changes in ({'workers': -1}, {'microbatch_size': 32769}, {'episodes_per_update': 0},
                            {'minibatch_size': 2.5}, {'workers': True}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    helper.write_runtime_control(run, **(expected | changes))
            self.assertEqual(json.loads(path.read_text()), second)

    def test_unowned_live_lease_is_rejected_and_emergency_stops_only_owned_handle(self):
        helper = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); run = root/'drive/trial'
            lease = run.parent/'_notebook_sessions/trial.json'; lease.parent.mkdir(parents=True)
            lease.write_text(json.dumps({'host_id': helper._host_id(), 'pid': os.getpid(), 'returncode': None}))
            args = dict(cwd=root, env=dict(os.environ), persistent_run=run, display=False)
            with self.assertRaisesRegex(RuntimeError, '不拥有'):
                helper.start_session([sys.executable, '-c', 'pass'], root/'log', **args)
            lease.unlink()
            session = helper.start_session([sys.executable, '-u', '-c', 'import time;print("alive");time.sleep(30)'], root/'log', **args)
            try:
                with self.assertRaisesRegex(RuntimeError, '初始化'):
                    session.request_stop()
                self.assertFalse(run.exists())
                session.terminate_owned(grace_seconds=.1)
                self.assertFalse(session.wait(10)['running'])
                self.assertIsNotNone(session.status()['returncode'])
            finally:
                session.terminate_owned(); session.wait(10)

    def test_status_exposes_desired_effective_pending_and_invalid_control_error(self):
        helper = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); run = root/'drive/trial'
            helper.write_runtime_control(run, workers=12, episodes_per_update=40,
                                         minibatch_size=128, microbatch_size=32)
            status_path = run.parent/'_runtime_controls/trial.status.json'
            payload = {'effective': {'workers': 8}, 'pending': True, 'error': 'fixture error'}
            status_path.write_text(json.dumps(payload))
            session = helper.start_session([sys.executable, '-c', 'print("done")'], root/'log',
                cwd=root, env=dict(os.environ), persistent_run=run, display=False)
            session.wait(10)
            self.assertEqual(session.status()['control']['runtime'], payload)
            self.assertEqual(session.status()['control']['desired']['workers'], 12)
            self.assertIn('fixture error', session._html())
            status_path.write_text('{not json')
            self.assertIn('runtime_read_error', session.status()['control'])


if __name__ == '__main__':
    unittest.main()
