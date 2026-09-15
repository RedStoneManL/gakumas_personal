"""Exercise the actual HTTP app, portable run binding, icons and scale requests."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from server import make_server, icon, CARDS
import resource_control
from generalist_data import GeneralistData, replay_runtime


class PortableDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)/'run'
        self.run.mkdir()
        self.config = {'training_stage': 'joint_build_and_public_history_mcts_exam',
                       'resource_mode': 'cluster', 'effective_minibatch': 32768,
                       'parallelism': dict(workers=96, parallel_roots=24, inference_batch=32, microbatch=2, torch_threads=2)}
        (self.run/'manifest.json').write_text(json.dumps({'config': self.config, 'profiles': []}), encoding='utf-8')
        (self.run/'progress.json').write_text(json.dumps({'status':'running','trainer_pid':os.getpid()}), encoding='utf-8')
        self.server = make_server(self.run, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(5); self.temp.cleanup()

    def get(self, path):
        with urlopen(self.url+path, timeout=10) as response:
            return response.read()

    def test_page_state_latest_features_and_packaged_icon(self):
        self.assertIn('resource-form', self.get('/').decode())
        self.assertIn('signed_credit', self.get('/generalist.js').decode())
        value = json.loads(self.get('/api/generalist'))
        self.assertEqual(value['run']['id'], 'run')
        self.assertEqual(value['status'], 'running')
        path = next(icon('skillCards', key) for key in CARDS if icon('skillCards', key))
        self.assertTrue(self.get(path).startswith(b'\x89PNG'))
        self.assertEqual(json.loads(self.get('/api/generalist/episodes')), [])

    def test_post_supports_large_scale_and_waits_for_batch_boundary(self):
        settings = dict(workers=1024, parallel_roots=512, inference_batch=1024, microbatch=2048, torch_threads=128)
        body = json.dumps({'run_id': 'run', 'parallelism': settings}).encode()
        with urlopen(Request(self.url+'/api/generalist/resources', body, headers={'Content-Type':'application/json'}), timeout=10) as response:
            value = json.load(response)
        self.assertEqual(value['requested']['parallelism'], settings)
        self.assertEqual(value['actual'], {})
        self.assertEqual(json.loads((self.run/'manifest.json').read_text())['config'], self.config)

    def test_bad_request_does_not_touch_trainer(self):
        for change in ({'workers':0}, {'workers':True}, {'unexpected':3}, {'microbatch':32769}):
            settings = {**self.config['parallelism'], **change}
            with self.assertRaises(ValueError): resource_control.request(self.run, {'run_id':'run','parallelism':settings})
        self.assertFalse((self.run/'resource-mode.json').exists())
        with self.assertRaises(HTTPError) as failure:
            urlopen(Request(self.url+'/api/generalist/resources', b'{}', headers={'Content-Type':'application/json','Origin':'https://elsewhere.test'}))
        self.assertEqual(failure.exception.code, 403)

    def test_replay_path_is_frozen_and_arbitrary_logs_rejected(self):
        root = Path(__file__).resolve().parent.parent
        self.assertEqual(replay_runtime(root, root/'exam-search/runtime/arena'), root/'exam-search/runtime/arena')
        with self.assertRaises(ValueError): replay_runtime(root, self.run/'arena')
        data = GeneralistData(root, run_dir=self.run)
        with self.assertRaises(ValueError): data.logs('../../unrelated')


if __name__ == '__main__':
    import test_generalist_data
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(PortableDashboardTests),
                               unittest.defaultTestLoader.loadTestsFromModule(test_generalist_data)])
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
