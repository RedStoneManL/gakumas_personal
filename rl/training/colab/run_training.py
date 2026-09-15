"""Resume one long-lived task on Colab using verified mounted-Drive snapshots.

No cloud APIs, environment installation, or background training is performed by
this module. The notebook prepares dependencies and mounts Drive explicitly.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import random
import signal
import sys
import time

from persistence import SnapshotStore, RUN_SCHEMA, atomic_json, bind_identity, file_hash, object_hash, safe_child


def verify_bundle(bundle_root):
    root = Path(bundle_root).resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "hif-colab-training/1" or not isinstance(manifest.get("files"), list):
        raise ValueError("Unsupported bundle manifest schema")
    listed = {}
    for record in manifest["files"]:
        relative = record["path"]
        if relative in listed:
            raise ValueError(f"Duplicate bundle manifest path: {relative}")
        path = safe_child(root, relative)
        if path.is_symlink() or not path.is_file() or path.stat().st_size != record["size"]:
            raise ValueError(f"Bundle file is missing or has changed size: {relative}")
        if file_hash(path) != record["sha256"]:
            raise ValueError(f"Bundle checksum mismatch: {relative}")
        listed[relative] = record["sha256"]
    for folder in (root / "training" / "gakumas_training", root / "arena" / "gakumas_arena"):
        if not folder.is_dir():
            raise ValueError(f"Missing bundled package: {folder}")
        for path in folder.rglob("*.py"):
            if path.relative_to(root).as_posix() not in listed:
                raise ValueError(f"Unversioned Python source in bundle: {path}")
    sources = {path: digest for path, digest in listed.items()
               if path.startswith(("training/", "arena/", "colab/"))}
    return {"manifest_sha256": file_hash(manifest_path), "source_sha256": object_hash(sources),
            "schema": manifest["schema"], "files_verified": len(listed)}


class WallClockBudget:
    """Accumulate active session wall time, including collection/update/eval/I/O.

    Offline time between sessions is not training time. A VM killed without a
    final write can lose time since its last durable boundary, like its batch.
    """
    def __init__(self, previous_seconds=0., *, total_hours=24., session_hours=8., clock=time.monotonic):
        if any(not math.isfinite(v) or v <= 0 for v in (total_hours, session_hours)):
            raise ValueError("Time budgets must be finite and positive")
        if not math.isfinite(previous_seconds) or previous_seconds < 0:
            raise ValueError("Invalid saved active wall-clock time")
        self.previous_seconds, self.total_seconds = previous_seconds, total_hours * 3600
        self.session_limit_seconds, self.clock = session_hours * 3600, clock
        self.started = clock()

    @property
    def session_seconds(self):
        return max(0., self.clock() - self.started)

    @property
    def active_seconds(self):
        return self.previous_seconds + self.session_seconds

    def stop_reason(self):
        if self.active_seconds >= self.total_seconds:
            return "total_budget_reached"
        if self.session_seconds >= self.session_limit_seconds:
            return "session_budget_reached"
        return None


def safe_checkpoint_summary(path):
    import torch
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint.get("boundary") != "after_complete_update":
        raise ValueError("Persistence requires a complete-update checkpoint")
    if checkpoint["iteration"] != checkpoint["policy_version"]:
        raise ValueError("Saved policy version/iteration disagree")
    result = {key: checkpoint[key] for key in ("iteration", "policy_version", "seed_cursor", "episodes_seen", "decisions")}
    result.update({key: checkpoint[key] for key in ("execution_settings", "pending_execution_settings",
                   "execution_control_state") if key in checkpoint})
    return result


def initialize_safe_checkpoint(trainer):
    """Persist random initial weights without tripping core's overwrite guard."""
    latest = trainer.checkpoint_path
    initial = latest.with_name("initial.pt")
    if trainer.iteration == 0:
        if latest.exists():
            # A restored initial snapshot is canonicalized as latest.pt by the
            # store. Keep it as initial.pt until the first complete PPO update.
            summary = safe_checkpoint_summary(latest)
            if summary["iteration"] != 0:
                raise ValueError("Initial learner has a non-initial checkpoint")
            os.replace(latest, initial)
        elif not initial.exists():
            trainer.checkpoint_path = initial
            try:
                trainer.checkpoint()
            finally:
                trainer.checkpoint_path = latest
        return initial
    if not latest.exists():
        raise ValueError("Resumed learner has no local safe checkpoint")
    return latest


def hardware_info(device="cuda"):
    import torch
    from gakumas_training.device import device_report
    return {"python": platform.python_version(), "machine": platform.machine(), **device_report(device),
            "cuda_runtime": torch.version.cuda, "cuda_device_count": torch.cuda.device_count(),
            "gpus": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
            "bitwise_replay_claimed": False,
            "resume_note": "Optimizer/RNG/seed continuation; changing GPU model or runtime may change floating-point results."}


def completed_evaluation(local_run, task):
    """Return the first complete held-out metric; never infer scores from episodes.

    A VM may stop between the individual episode logs and the final metric.
    Only the latter proves that the whole configured evaluation finished.
    """
    path = Path(local_run) / "evaluation" / "metrics.jsonl"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.endswith("\n"):
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (value.get("namespace") == "evaluation" and value.get("task") == task
                    and value.get("episodes", 0) > 0
                    and isinstance(value.get("raw_score_mean"), (int, float))
                    and math.isfinite(value["raw_score_mean"])):
                return value
    return None


def run_loop(trainer, store, *, restored_state=None, total_hours=24., session_hours=8.,
             max_updates=None, session_metadata=None, clock=time.monotonic):
    """Run ``train(1)`` repeatedly in one process; synchronize every safe batch.

    Public API used by small local tests. ``trainer`` follows the existing core
    Trainer API, and ``store`` is a SnapshotStore on an already mounted path.
    """
    if max_updates is not None and max_updates < 1:
        raise ValueError("max-updates must be positive")
    local_run = Path(trainer.output).resolve()
    restored_state = restored_state or {}
    budget = WallClockBudget(restored_state.get("active_wall_seconds", 0.),
                             total_hours=total_hours, session_hours=session_hours, clock=clock)
    start_iteration = trainer.iteration
    session = {"started_at": datetime.now(timezone.utc).isoformat(),
               "start_iteration": start_iteration, "hardware": session_metadata or {},
               "total_hours": total_hours, "session_hours": session_hours,
               "recovery_warnings": list(store.recovery_warnings)}
    atomic_json(local_run / "session.json", session)
    if not (local_run / "manifest.json").exists():
        atomic_json(local_run / "manifest.json", {"config": trainer.config.to_dict(),
            "arena_version": trainer.arena_version, "model_schema": trainer.model_schema,
            "encoding_schema": trainer.encoding_schema,
            "reward": "zero intermediate; terminal raw score / fixed C", "initial_state": True})
    checkpoint = initialize_safe_checkpoint(trainer)

    def sync(status, error=None):
        checkpoint = (trainer.checkpoint_path if trainer.checkpoint_path.exists()
                      else trainer.checkpoint_path.with_name("initial.pt"))
        summary = safe_checkpoint_summary(checkpoint)
        state = {"schema": "gakumas-colab-session-state/1", "identity_sha256": store.identity_sha256,
            **summary, "active_wall_seconds": budget.active_seconds,
            "session_wall_seconds": budget.session_seconds,
            "total_target_seconds": total_hours * 3600, "session_limit_seconds": session_hours * 3600,
            "status": status, "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_error": error, "hardware": session_metadata or {},
            "lost_work_boundary": "an interrupted in-progress batch is repeated from the last complete checkpoint"}
        if "migration" in restored_state:
            state["migration"] = restored_state["migration"]
        committed = store.publish(local_run, state, checkpoint=checkpoint, refresh_state=lambda: {
            "active_wall_seconds": budget.active_seconds, "session_wall_seconds": budget.session_seconds,
            "updated_at": datetime.now(timezone.utc).isoformat()})
        print(json.dumps({"event": "persistent_checkpoint", "generation": committed["manifest"]["generation"],
                          "iteration": summary["iteration"], "status": status,
                          "active_hours": state["active_wall_seconds"] / 3600,
                          "persistent_run": str(store.run_dir)}, ensure_ascii=False), flush=True)
        control = getattr(trainer, "execution_control", None)
        if hasattr(control, "publish_status"):
            control.publish_status(trainer, stage=status)
        return state

    # Initial and restored state is durable before beginning any new expensive
    # rollout. Failure to synchronize stops the run instead of accumulating risk.
    state = sync("ready")
    try:
        baseline_checked = False
        while True:
            reason = budget.stop_reason()
            if (local_run / "STOP").exists() or (store.run_dir / "STOP").exists():
                reason = "stop_file"
            if max_updates is not None and trainer.iteration - start_iteration >= max_updates:
                reason = "max_updates_reached"
            if reason:
                return sync(reason)
            if not baseline_checked:
                metric = completed_evaluation(local_run, trainer.config.task)
                if metric is None:
                    if trainer.iteration != 0:
                        raise ValueError("Resumed trained policy has no completed held-out baseline; cannot fabricate iteration-zero scores")
                    print(json.dumps({"event": "initial_baseline_started", "iteration": 0,
                        "episodes": trainer.config.eval_episodes, "seed_start": trainer.config.eval_seed,
                        "deterministic": True}), flush=True)
                    metric = trainer.evaluate()
                    completed = completed_evaluation(local_run, trainer.config.task)
                    if completed is None or completed != metric:
                        raise ValueError("Initial evaluation did not write a complete matching metric")
                    print(json.dumps({"event": "initial_baseline_completed", **metric},
                                     ensure_ascii=False, allow_nan=False), flush=True)
                if metric.get("iteration") == 0 and metric.get("policy_version") == 0:
                    atomic_json(local_run / "initial-baseline.json", {
                        "kind": "initial_baseline", "deterministic": True,
                        "seed_start": trainer.config.eval_seed, "metrics": metric})
                baseline_checked = True
                state = sync("baseline_ready")
                # A full held-out evaluation can itself consume the remaining
                # budget or receive a STOP request. Recheck before collecting.
                continue
            trainer.train(1)
            state = sync("ready")
    except BaseException as error:
        # Do not serialize the in-memory model here: an interrupted optimizer
        # update may have partially changed it. Only upload the last safe file.
        try:
            sync("interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                 {"type": type(error).__name__, "message": str(error)})
        except BaseException as persistence_error:
            print(f"Persistent sync also failed; local safe checkpoint retained: {persistence_error}",
                  file=sys.stderr, flush=True)
        raise


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle-root", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--task", choices=("full_produce", "exam_score"), required=True)
    p.add_argument("--run-name", required=True)
    p.add_argument("--migrate-from-run", help="Copy a verified complete checkpoint from an older run into this new run")
    p.add_argument("--local-root", type=Path, default=Path("/content/gakumas-runs"))
    p.add_argument("--persistent-root", "--drive-root", dest="persistent_root", type=Path, required=True)
    p.add_argument("--total-hours", type=float, default=24.)
    p.add_argument("--session-hours", type=float, default=8.)
    p.add_argument("--max-updates", type=int, help="Bounded smoke/diagnostic runs only")
    p.add_argument("--device", help="Explicit cuda[:N] or npu[:N] override for a new run")
    p.add_argument("--allow-cpu-smoke", action="store_true", help="Explicit CPU test; requires max-updates <= 2")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    bundle_root = args.bundle_root.resolve()
    bundle_version = verify_bundle(bundle_root)
    config_path = args.config if args.config.is_absolute() else bundle_root / args.config
    data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if data.get("task") != args.task:
        raise ValueError("Config task differs from --task")
    training_path = bundle_root / "training"
    sys.path.insert(0, str(training_path))
    import numpy as np
    import torch
    import gakumas_training
    if not Path(gakumas_training.__file__).resolve().is_relative_to(training_path):
        raise RuntimeError("A different gakumas_training package was already imported")
    from gakumas_training.encoding import DecisionEncoder, Vocabulary
    from gakumas_training.encoding.graph import ENCODING_VERSION
    from gakumas_training.models import ModelConfig, PolicyRunner, PolicyValueNet
    from gakumas_training.runtime import RunConfig, Trainer
    from gakumas_training.runtime.config import EXECUTION_LIMITS
    from gakumas_training.device import resolve_device, seed_device, device_kind
    from gakumas_training.tasks import ExamScoreConfig, ExamScoreTask, FullProduceConfig, FullProduceTask
    if args.allow_cpu_smoke:
        if args.device not in (None, "cpu"):
            raise ValueError("--allow-cpu-smoke cannot be combined with an accelerator --device")
        if args.max_updates is None or not 1 <= args.max_updates <= 2:
            raise ValueError("CPU smoke requires --max-updates 1 or 2")
        data["device"] = "cpu"
    else:
        if args.device is not None:
            data["device"] = args.device
        if device_kind(data.get("device")) not in ("cuda", "npu"):
            raise RuntimeError("Long training requires CUDA or NPU; CPU tests require --allow-cpu-smoke")
    resolve_device(data["device"])
    config = RunConfig.from_dict(data)
    model_config = ModelConfig(**config.model)
    task_cls, task_config_cls = ((FullProduceTask, FullProduceConfig) if args.task == "full_produce"
                                else (ExamScoreTask, ExamScoreConfig))
    task_config = task_config_cls(**config.task_config)
    config = replace(config, model=asdict(model_config), task_config=asdict(task_config))
    local_run = args.local_root.resolve() / args.run_name
    persistent_run = args.persistent_root.resolve() / args.run_name
    if local_run.is_relative_to(persistent_run) or persistent_run.is_relative_to(local_run):
        raise ValueError("Local scratch and persistent run directories must be separate")
    if not args.persistent_root.exists():
        raise FileNotFoundError("Persistent root does not exist; mount Drive and create the intended root first")
    torch.set_num_threads(config.torch_threads)
    random.seed(config.seed)
    np.random.seed(config.seed % 2**32)
    seed_device(config.seed, config.device)
    task = task_cls(task_config, arena_root=bundle_root / "arena")
    try:
        identity = {"schema": RUN_SCHEMA, "task": args.task, "run_name": args.run_name,
                    "bundle": bundle_version, "config": config.to_dict(),
                    "config_sha256": object_hash(config.to_dict()), "arena_version": task.arena_version,
                    "model_schema": "gakumas-candidate-graph-policy/1", "encoding_schema": ENCODING_VERSION}
        if args.migrate_from_run:
            from migrate_run import migrate_run
            migrated = migrate_run(args.persistent_root, args.migrate_from_run, args.run_name, local_run, identity)
            print(json.dumps({"event": "migration_restored", "source_run": args.migrate_from_run,
                "target_run": args.run_name, "iteration": migrated["iteration"],
                "active_hours": migrated["active_wall_seconds"] / 3600}, ensure_ascii=False), flush=True)
        store = SnapshotStore(args.persistent_root, args.run_name, identity)
        bind_identity(local_run, identity)
        restored_state = store.restore(local_run)
        encoder = DecisionEncoder(Vocabulary(capacity=model_config.vocab_capacity), max_nodes=model_config.max_nodes)
        model = PolicyValueNet(model_config).to(config.device)
        trainer = Trainer(task=task, encoder=encoder, model=model, policy_runner=PolicyRunner(encoder, model),
            config=config, output=local_run, arena_version=task.arena_version,
            model_schema=identity["model_schema"], encoding_schema=ENCODING_VERSION)
        local_checkpoint = (trainer.checkpoint_path if trainer.checkpoint_path.exists()
                            else trainer.checkpoint_path.with_name("initial.pt"))
        if local_checkpoint.exists():
            trainer.resume(local_checkpoint)
            if restored_state is None and (local_run / "colab-state.json").exists():
                restored_state = json.loads((local_run / "colab-state.json").read_text())
        from runtime_control import RuntimeControl
        trainer.execution_control = RuntimeControl(persistent_run)
        trainer.execution_control.publish_status(trainer, stage="ready")
        print(json.dumps({"event": "runtime_control_ready", "path": str(trainer.execution_control.path),
            "effective": trainer.execution_settings,
            "limits": EXECUTION_LIMITS}, ensure_ascii=False), flush=True)
        hardware = hardware_info(config.device)
        old_hardware = (restored_state or {}).get("hardware")
        if old_hardware and old_hardware != hardware:
            print(json.dumps({"event": "runtime_changed", "previous": old_hardware, "current": hardware,
                "note": "Continuation is supported when checkpoint validation passes; bitwise identity is not promised."}), flush=True)
        previous_sigterm = signal.getsignal(signal.SIGTERM)

        def handle_termination(signum, frame):
            raise KeyboardInterrupt("SIGTERM")

        signal.signal(signal.SIGTERM, handle_termination)
        try:
            run_loop(trainer, store, restored_state=restored_state, total_hours=args.total_hours,
                     session_hours=args.session_hours, max_updates=args.max_updates, session_metadata=hardware)
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
        return 0
    except KeyboardInterrupt:
        print("Interrupted; resume the same run name to continue from its last verified safe snapshot.", flush=True)
        return 130
    finally:
        task.close()


if __name__ == "__main__":
    raise SystemExit(main())
