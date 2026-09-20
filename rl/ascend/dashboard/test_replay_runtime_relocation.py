"""Relocated recording paths never authorize executing an external runtime."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generalist_data import replay_runtime


class ReplayRelocationTests(unittest.TestCase):
    def test_relocated_deploy_uses_only_bundled_copy_with_recorded_hash(self):
        for name in ('exam-search', 'exam_search'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()/'dashboard-deploy'
                bundled = root/name/'runtime/arena'
                bundled.mkdir(parents=True)
                recorded = root.parent/'deploy-v6-credit-opt/exam-search/runtime/arena'
                recorded.mkdir(parents=True)
                self.assertEqual(replay_runtime(root, recorded, arena_sha256='a'*64), bundled)
                for missing in (None, '', 'wrong', 'g'*64):
                    with self.assertRaises(ValueError):
                        replay_runtime(root, recorded, arena_sha256=missing)

    def test_external_runtime_is_never_used_when_bundle_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()/'dashboard-deploy'
            recorded = root.parent/'unrelated/runtime/arena'
            recorded.mkdir(parents=True)
            with self.assertRaises(ValueError):
                replay_runtime(root, recorded, arena_sha256='a'*64)

    def test_existing_named_revision_remains_preferred(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            named = root/'rl/generalist-search-signed-credit/runtime/arena'
            (root/'exam-search/runtime/arena').mkdir(parents=True)
            self.assertEqual(replay_runtime(root, named, arena_sha256='a'*64), named)

    def test_bundle_symlink_cannot_escape_allowed_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()/'dashboard-deploy'
            outside = root.parent/'external'
            outside.mkdir()
            parent = root/'exam-search/runtime'
            parent.mkdir(parents=True)
            try:
                (parent/'arena').symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(str(error))
            with self.assertRaises(ValueError):
                replay_runtime(root, outside, arena_sha256='a'*64)


if __name__ == '__main__':
    unittest.main()
