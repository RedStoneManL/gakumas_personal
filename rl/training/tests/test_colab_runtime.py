"""Mounted-Drive persistence tests use temporary local directories only."""
import contextlib
import copy
from dataclasses import replace
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "colab"))
from persistence import SnapshotStore, RUN_SCHEMA, atomic_json, bind_identity, file_hash
from run_training import WallClockBudget, run_loop, verify_bundle
from test_runtime import make_trainer
from gakumas_training.runtime.checkpoint import capture_rng


IDENTITY = {"schema": RUN_SCHEMA, "task": "exam_score", "run_name": "trial", "source": "test-source-v1"}


def local_payload(local, store, iteration):
    bind_identity(local, IDENTITY)
    (local / "checkpoints").mkdir(exist_ok=True)
    (local / "checkpoints" / "latest.pt").write_bytes(f"checkpoint-{iteration}".encode())
    atomic_json(local / "manifest.json", {"task": "exam_score"})
    return {"identity_sha256": store.identity_sha256, "iteration": iteration,
            "active_wall_seconds": 100. * iteration}


def add_episode(local, seed):
    path = local / "training" / "episodes.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"task": "exam_score", "seed": seed, "raw_score": seed * 10,
            "termination": "failed", "iteration": seed, "policy_version": seed - 1,
            "metadata": {"objective": "raw_score", "terminal_observation": {"huge": "x" * 10000},
                         "setup_mode": "select", "selected_support_ids": ["support-a", "support-b"],
                         "selected_memory_ids": ["memory-a"],
                         "selected_memory_specs": [{"memory_id": "memory-a", "ability_ids": ["factor-a"],
                             "ability_levels": [1], "produce_card": {"card_id": "card-a", "upgrade_count": 1,
                                 "customize_ids": ["customize-a"], "phase_type": "ProduceMemoryProduceCardPhaseType_ProduceStart"}}],
                         "rating_provenance": {"early_terminal_mapping": True}}}) + "\n")


class PersistenceTests(unittest.TestCase):
    def test_all_committed_snapshots_corrupt_without_pointer_cannot_reset_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            local = root / "local"
            committed = store.publish(local, local_payload(local, store, 1))
            (store.run_dir / "latest.json").unlink()
            (committed["path"] / "checkpoints" / "latest.pt").write_bytes(b"corrupt")
            recovering = SnapshotStore(root / "drive", "trial", IDENTITY)
            with self.assertRaisesRegex(ValueError, "refusing to reset"):
                recovering.latest()
            with self.assertRaisesRegex(ValueError, "refusing to reset"):
                recovering.restore(root / "recovered")
            self.assertFalse((root / "recovered").exists())

    def test_only_uncommitted_upload_may_start_from_initial_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SnapshotStore(Path(tmp) / "drive", "trial", IDENTITY)
            (store.snapshots_dir / ".upload-never-committed").mkdir()
            self.assertIsNone(store.latest())

    def test_newest_corrupt_snapshot_falls_back_and_partial_upload_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            local = root / "local"
            first = store.publish(local, local_payload(local, store, 1))
            newest = store.publish(local, local_payload(local, store, 2))
            (newest["path"] / "checkpoints" / "latest.pt").write_bytes(b"corrupt")
            (store.snapshots_dir / ".upload-interrupted").mkdir()
            restored = store.restore(root / "recovered")
            self.assertEqual(restored["iteration"], 1)
            self.assertEqual((root / "recovered" / "checkpoints" / "latest.pt").read_bytes(), b"checkpoint-1")
            self.assertTrue(store.recovery_warnings)
            # Recovery from an older verified generation may make progress even
            # though the corrupt old latest pointer is still on disk.
            resumed = store.publish(root / "recovered", restored)
            self.assertEqual(resumed["manifest"]["generation"], first["manifest"]["generation"] + 1)

    def test_upload_failure_leaves_previous_commit_recoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            local = root / "local"
            store.publish(local, local_payload(local, store, 1))
            with patch("persistence.copy_verified", side_effect=OSError("simulated upload disconnect")):
                with self.assertRaises(OSError):
                    store.publish(local, local_payload(local, store, 2))
            recovered = SnapshotStore(root / "drive", "trial", IDENTITY).restore(root / "recovered")
            self.assertEqual(recovered["iteration"], 1)

    def test_corrupt_new_log_chunk_falls_back_without_reusing_bad_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            local = root / "local"
            state = local_payload(local, store, 1)
            add_episode(local, 1)
            store.publish(local, state)
            add_episode(local, 2)
            latest = store.publish(local, local_payload(local, store, 2))
            chunk = latest["manifest"]["logs"]["training/episodes.jsonl"]["chunks"][-1]
            (store.run_dir / chunk["path"]).write_bytes(b"bad chunk")
            recovered = root / "recovered"
            state = store.restore(recovered)
            self.assertEqual(state["iteration"], 1)
            store.publish(recovered, state)
            self.assertEqual(store.latest()["state"]["iteration"], 1)

    def test_incremental_compact_logs_survive_restore_and_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            local = root / "local"
            state = local_payload(local, store, 1)
            add_episode(local, 1)
            one = store.publish(local, state)
            log = one["manifest"]["logs"]["training/episodes.jsonl"]
            blob = store.run_dir / log["chunks"][0]["path"]
            before = blob.stat().st_mtime_ns
            add_episode(local, 2)
            two = store.publish(local, local_payload(local, store, 2))
            self.assertEqual(blob.stat().st_mtime_ns, before)
            self.assertEqual(len(two["manifest"]["logs"]["training/episodes.jsonl"]["chunks"]), 2)
            self.assertNotIn("training/episodes.jsonl", two["manifest"]["files"])
            store2 = SnapshotStore(root / "drive", "trial", IDENTITY)
            recovered = root / "recovered"
            state = store2.restore(recovered)
            rows = [json.loads(line) for line in (recovered / "training" / "episodes.jsonl").read_text().splitlines()]
            self.assertEqual([r["seed"] for r in rows], [1, 2])
            self.assertNotIn("terminal_observation", rows[0]["metadata"])
            self.assertTrue(rows[0]["metadata"]["rating_provenance"]["early_terminal_mapping"])
            self.assertEqual(rows[0]["metadata"]["setup_mode"], "select")
            self.assertEqual(rows[0]["metadata"]["selected_support_ids"], ["support-a", "support-b"])
            self.assertEqual(rows[0]["metadata"]["selected_memory_ids"], ["memory-a"])
            self.assertEqual(rows[0]["metadata"]["selected_memory_specs"][0]['produce_card']['customize_ids'], ['customize-a'])
            self.assertEqual(rows[0]["metadata"]["selected_memory_specs"][0]['ability_ids'], ['factor-a'])
            add_episode(recovered, 3)
            store2.publish(recovered, state)
            store3 = SnapshotStore(root / "drive", "trial", IDENTITY)
            store3.restore(root / "again")
            rows = [json.loads(line) for line in (root / "again" / "training" / "episodes.jsonl").read_text().splitlines()]
            self.assertEqual([r["seed"] for r in rows], [1, 2, 3])

    def test_retains_three_complete_snapshots_and_rejects_changed_run_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            for iteration in range(5):
                store.publish(root / "local", local_payload(root / "local", store, iteration))
            self.assertEqual(len(store.complete_snapshots()), 3)
            self.assertEqual([r["state"]["iteration"] for r in store.complete_snapshots()], [2, 3, 4])
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                SnapshotStore(root / "drive", "trial", {**IDENTITY, "task": "full_produce"})


class ColabLoopTests(unittest.TestCase):
    def test_initial_baseline_is_durable_rng_neutral_and_not_repeated_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            local = root / "local"
            bind_identity(local, IDENTITY)
            trainer = make_trainer(local)
            trainer.config = replace(trainer.config, eval_every_updates=0)
            rng = capture_rng()
            vocab = copy.deepcopy(trainer.encoder.state_dict())
            seed_cursor = trainer.seed_cursor
            train = trainer.train

            def train_after_baseline(updates):
                after = capture_rng()
                self.assertEqual(after["python"], rng["python"])
                self.assertEqual(after["numpy"], rng["numpy"])
                self.assertTrue(torch.equal(after["torch"], rng["torch"]))
                self.assertEqual(trainer.seed_cursor, seed_cursor)
                self.assertEqual(trainer.encoder.state_dict(), vocab)
                safe = store.latest()
                self.assertEqual(safe["state"]["iteration"], 0)
                self.assertIn("initial-baseline.json", safe["manifest"]["files"])
                self.assertIn("evaluation/metrics.jsonl", safe["manifest"]["logs"])
                return train(updates)

            with patch.object(trainer, "evaluate", wraps=trainer.evaluate) as evaluate:
                with patch.object(trainer, "train", side_effect=train_after_baseline):
                    run_loop(trainer, store, max_updates=1)
                self.assertEqual(evaluate.call_count, 1)
            marker = json.loads((local / "initial-baseline.json").read_text())
            self.assertEqual(marker["kind"], "initial_baseline")
            self.assertEqual(marker["metrics"]["iteration"], 0)
            self.assertEqual(marker["metrics"]["episodes"], trainer.config.eval_episodes)
            self.assertEqual(marker["seed_start"], trainer.config.eval_seed)
            recovered = root / "recovered"
            store2 = SnapshotStore(root / "drive", "trial", IDENTITY)
            state = store2.restore(recovered)
            resumed = make_trainer(recovered, config=trainer.config)
            resumed.resume()
            with patch.object(resumed, "evaluate", side_effect=AssertionError("baseline repeated")):
                run_loop(resumed, store2, restored_state=state, max_updates=1)
            rows = [json.loads(line) for line in (recovered / "evaluation" / "metrics.jsonl").read_text().splitlines()]
            self.assertEqual([row["iteration"] for row in rows], [0])

    def test_interrupted_initial_baseline_has_no_fake_metric_and_is_retried(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            local = root / "local"
            bind_identity(local, IDENTITY)
            trainer = make_trainer(local)
            trainer.config = replace(trainer.config, eval_every_updates=0)
            with patch.object(trainer, "evaluate", side_effect=KeyboardInterrupt("initial evaluation interrupted")):
                with self.assertRaises(KeyboardInterrupt):
                    run_loop(trainer, store, max_updates=1)
            self.assertNotIn("initial-baseline.json", store.latest()["manifest"]["files"])
            self.assertNotIn("evaluation/metrics.jsonl", store.latest()["manifest"]["logs"])
            recovered = root / "recovered"
            store2 = SnapshotStore(root / "drive", "trial", IDENTITY)
            state = store2.restore(recovered)
            resumed = make_trainer(recovered, config=trainer.config)
            resumed.resume()
            with patch.object(resumed, "evaluate", wraps=resumed.evaluate) as evaluate:
                run_loop(resumed, store2, restored_state=state, max_updates=1)
                self.assertEqual(evaluate.call_count, 1)

    def test_keyboard_interrupt_does_not_save_partially_modified_model(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            local = root / "local"
            bind_identity(local, IDENTITY)
            trainer = make_trainer(local)
            before = copy.deepcopy(trainer.model.state_dict())

            def interrupted_update(_):
                with torch.no_grad():
                    next(trainer.model.parameters()).add_(100.)
                raise KeyboardInterrupt("simulated SIGINT during update")

            with patch.object(trainer, "train", side_effect=interrupted_update):
                with self.assertRaises(KeyboardInterrupt):
                    run_loop(trainer, store, max_updates=1)
            latest = store.latest()
            self.assertEqual(latest["state"]["status"], "interrupted")
            saved = torch.load(latest["path"] / "checkpoints" / "latest.pt", weights_only=True)
            for key, tensor in before.items():
                torch.testing.assert_close(tensor, saved["model_state"][key], atol=0, rtol=0)

    def test_initial_checkpoint_interrupt_and_resumption_then_cpu_next_update_match(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            local = root / "local"
            bind_identity(local, IDENTITY)
            interrupted = make_trainer(local, fail=True)
            with self.assertRaisesRegex(RuntimeError, "engine failure"):
                run_loop(interrupted, store, max_updates=1)
            self.assertEqual(store.latest()["state"]["iteration"], 0)
            resumed_local = root / "resumed"
            store2 = SnapshotStore(root / "drive", "trial", IDENTITY)
            state = store2.restore(resumed_local)
            trainer = make_trainer(resumed_local)
            trainer.resume()
            first = run_loop(trainer, store2, restored_state=state, max_updates=1)
            self.assertEqual(first["iteration"], 1)
            store3 = SnapshotStore(root / "drive", "trial", IDENTITY)
            next_local = root / "next"
            state = store3.restore(next_local)
            continued = make_trainer(next_local)
            continued.resume()
            run_loop(continued, store3, restored_state=state, max_updates=1)
            reference = make_trainer(root / "reference")
            reference.train(2)
            for name, value in reference.model.state_dict().items():
                torch.testing.assert_close(value, continued.model.state_dict()[name], atol=0, rtol=0)

    def test_stop_file_persists_initial_state_without_running_episode(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            store = SnapshotStore(root / "drive", "trial", IDENTITY)
            (store.run_dir / "STOP").write_text("stop after safe boundary")
            local = root / "local"
            bind_identity(local, IDENTITY)
            trainer = make_trainer(local, fail=True)
            state = run_loop(trainer, store, max_updates=1)
            self.assertEqual(state["status"], "stop_file")
            self.assertEqual(state["iteration"], 0)
            self.assertTrue(store.latest()["path"].is_dir())

    def test_wall_clock_accumulates_active_sessions_and_excludes_offline_gap(self):
        now = [10.]
        clock = lambda: now[0]
        first = WallClockBudget(100., total_hours=1, session_hours=.1, clock=clock)
        now[0] += 125.
        self.assertEqual(first.active_seconds, 225.)
        saved = first.active_seconds
        now[0] += 100000.  # VM offline; not consumed active training budget.
        second = WallClockBudget(saved, total_hours=1, session_hours=.1, clock=clock)
        now[0] += 50.
        self.assertEqual(second.active_seconds, 275.)
        now[0] += 311.
        self.assertEqual(second.stop_reason(), "session_budget_reached")

    def test_bundle_manifest_rejects_changed_or_unlisted_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = []
            for relative in ("training/gakumas_training/__init__.py", "arena/gakumas_arena/__init__.py"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# source\n")
                records.append({"path": relative, "size": path.stat().st_size, "sha256": file_hash(path)})
            atomic_json(root / "manifest.json", {"schema": "hif-colab-training/1", "files": records})
            self.assertEqual(verify_bundle(root)["files_verified"], 2)
            extra = root / "training/gakumas_training/extra.py"
            extra.write_text("# not in manifest\n")
            with self.assertRaisesRegex(ValueError, "Unversioned"):
                verify_bundle(root)
            extra.unlink()
            (root / records[0]["path"]).write_text("# tampered\n")
            with self.assertRaises(ValueError):
                verify_bundle(root)


if __name__ == "__main__":
    unittest.main()
