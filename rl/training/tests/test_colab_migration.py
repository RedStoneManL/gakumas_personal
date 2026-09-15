"""Safe-boundary migration uses real tiny model/Adam/checkpoint/log fixtures."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import torch

COLAB = Path(__file__).resolve().parents[1] / 'colab'
if not COLAB.is_dir():
    COLAB = Path(__file__).resolve().parents[2] / 'colab'
sys.path.insert(0, str(COLAB))
from migrate_run import migrate_run
from persistence import SnapshotStore, RUN_SCHEMA, atomic_json, bind_identity, file_hash, object_hash
from run_training import run_loop
from test_runtime import make_trainer
from gakumas_training.runtime import RunConfig


def tree_hashes(path):
    return {p.relative_to(path).as_posix(): file_hash(p) for p in path.rglob('*') if p.is_file()}


class MigrationTests(unittest.TestCase):
    def source(self, root, *, iteration=1):
        local = root / 'source-local'
        trainer = make_trainer(local, fail=iteration == 0)
        identity = {'schema': RUN_SCHEMA, 'task': trainer.config.task, 'run_name': 'old',
            'bundle': {'manifest_sha256': 'old-manifest', 'source_sha256': 'old-source'},
            'config': trainer.config.to_dict(), 'config_sha256': object_hash(trainer.config.to_dict()),
            'arena_version': trainer.arena_version, 'model_schema': trainer.model_schema,
            'encoding_schema': trainer.encoding_schema}
        bind_identity(local, identity)
        store = SnapshotStore(root / 'drive', 'old', identity)
        with contextlib.redirect_stdout(io.StringIO()):
            if iteration == 0:
                with self.assertRaisesRegex(RuntimeError, 'engine failure'):
                    run_loop(trainer, store, max_updates=1)
            else:
                run_loop(trainer, store, max_updates=1)
        state = deepcopy(store.latest()['state'])
        state['active_wall_seconds'] = 24 * 3600 - 321.5
        state['total_target_seconds'] = 24 * 3600
        checkpoint = local / 'checkpoints' / ('initial.pt' if iteration == 0 else 'latest.pt')
        store.publish(local, state, checkpoint=checkpoint)
        new = deepcopy(identity)
        new.update(run_name='new', bundle={'manifest_sha256': 'new-manifest', 'source_sha256': 'new-source'})
        new['config']['workers'] = 1024
        new['config']['ppo']['microbatch_size'] = 4
        new['config_sha256'] = object_hash(new['config'])
        return store, identity, new, state

    def equal_payload(self, actual, expected):
        if isinstance(expected, torch.Tensor):
            torch.testing.assert_close(actual, expected, atol=0, rtol=0)
        elif isinstance(expected, dict):
            self.assertEqual(actual.keys(), expected.keys())
            for key in expected:
                self.equal_payload(actual[key], expected[key])
        elif isinstance(expected, (list, tuple)):
            self.assertEqual(type(actual), type(expected))
            self.assertEqual(len(actual), len(expected))
            for a, b in zip(actual, expected):
                self.equal_payload(a, b)
        else:
            self.assertEqual(actual, expected)

    def test_preserves_complete_state_logs_elapsed_and_source_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store, old, new, before_state = self.source(root)
            # The tiny unit-test task has no Arena child-process constructor;
            # use one worker for an actual next update. The iteration-zero test
            # below independently covers a workers=1024 migrated checkpoint.
            new['config']['workers'] = 1
            new['config_sha256'] = object_hash(new['config'])
            source_hashes = tree_hashes(store.run_dir)
            source_local = root / 'source-recovered'
            store.restore(source_local)
            before = torch.load(source_local / 'checkpoints/latest.pt', weights_only=True)
            state = migrate_run(root / 'drive', 'old', 'new', root / 'new-local', new)
            after = torch.load(root / 'new-local/checkpoints/latest.pt', weights_only=True)
            expected = deepcopy(before); expected['config'] = new['config']
            expected['execution_settings']['microbatch_size'] = new['config']['ppo']['microbatch_size']
            self.equal_payload(after, expected)
            self.assertEqual(state['active_wall_seconds'], before_state['active_wall_seconds'])
            self.assertEqual(state['total_target_seconds'], 24 * 3600)
            self.assertEqual(tree_hashes(store.run_dir), source_hashes)
            for namespace in ('training', 'evaluation'):
                for path in (source_local / namespace).rglob('*.jsonl'):
                    self.assertEqual(path.read_bytes(), (root / 'new-local' / path.relative_to(source_local)).read_bytes())
            resumed = make_trainer(root / 'new-local', config=RunConfig.from_dict(new['config']))
            resumed.resume()
            self.assertEqual(resumed.iteration, before['iteration'])
            self.assertEqual(resumed.seed_cursor, before['seed_cursor'])
            target_store = SnapshotStore(root / 'drive', 'new', new)
            with contextlib.redirect_stdout(io.StringIO()):
                continued = run_loop(resumed, target_store, restored_state=state, max_updates=1)
            self.assertEqual(continued['iteration'], before['iteration'] + 1)
            self.assertEqual(continued['migration'], state['migration'])
            self.assertEqual(json.loads((root / 'new-local/manifest.json').read_text())['migration'], state['migration'])
            again = migrate_run(root / 'drive', 'old', 'new', root / 'again', new)
            self.assertEqual(again['seed_cursor'], continued['seed_cursor'])
            self.assertGreaterEqual(again['active_wall_seconds'], state['active_wall_seconds'])
            self.assertEqual(tree_hashes(store.run_dir), source_hashes)

    def test_initial_checkpoint_is_migratable_and_resumable_without_resetting_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, new, original = self.source(root, iteration=0)
            state = migrate_run(root / 'drive', 'old', 'new', root / 'new-local', new)
            self.assertEqual(state['iteration'], 0)
            self.assertEqual(state['active_wall_seconds'], original['active_wall_seconds'])
            trainer = make_trainer(root / 'new-local', config=RunConfig.from_dict(new['config']))
            trainer.resume()
            self.assertEqual(trainer.iteration, 0)

    def test_semantic_or_schema_changes_and_existing_unmarked_targets_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store, _, new, _ = self.source(root)
            source_hashes = tree_hashes(store.run_dir)
            for field in ('score_scale', 'seed', 'model', 'task_config'):
                modified = deepcopy(new)
                modified['config'][field] = 99 if field in ('score_scale', 'seed') else {'changed': True}
                modified['config_sha256'] = object_hash(modified['config'])
                with self.subTest(field=field), self.assertRaises(ValueError):
                    migrate_run(root / 'drive', 'old', 'new', root / 'reject', modified)
            for field in ('arena_version', 'model_schema', 'encoding_schema'):
                modified = deepcopy(new); modified[field] = 'changed'
                with self.subTest(field=field), self.assertRaises(ValueError):
                    migrate_run(root / 'drive', 'old', 'new', root / 'reject', modified)
            bind_identity(root / 'drive/new', new)
            with self.assertRaises(ValueError):
                migrate_run(root / 'drive', 'old', 'new', root / 'reject', new)
            self.assertEqual(tree_hashes(store.run_dir), source_hashes)

    def test_partial_publication_is_never_treated_as_a_fresh_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, new, _ = self.source(root)
            with patch.object(SnapshotStore, 'publish', side_effect=IOError('Drive interrupted')):
                with self.assertRaisesRegex(IOError, 'Drive interrupted'):
                    migrate_run(root / 'drive', 'old', 'new', root / 'new-local', new)
            with self.assertRaises(ValueError):
                migrate_run(root / 'drive', 'old', 'new', root / 'new-local', new)
            self.assertFalse((root / 'drive/new/migration.json').exists())

    def test_corrupt_source_cannot_initialize_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store, _, new, _ = self.source(root)
            for snapshot in store.complete_snapshots():
                (snapshot['path'] / 'checkpoints/latest.pt').write_bytes(b'corrupt')
            hashes = tree_hashes(store.run_dir)
            with self.assertRaisesRegex(ValueError, 'no valid recoverable snapshot'):
                migrate_run(root / 'drive', 'old', 'new', root / 'new-local', new)
            self.assertFalse((root / 'drive/new').exists())
            self.assertEqual(tree_hashes(store.run_dir), hashes)


if __name__ == '__main__':
    unittest.main()
