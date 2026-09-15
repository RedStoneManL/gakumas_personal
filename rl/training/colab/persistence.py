"""Hash-verified snapshots on a mounted persistent filesystem, without APIs.

Checkpoint bytes are copied into a fresh staging directory, verified there,
then committed as an immutable snapshot. The small latest pointer is replaced
last. Recovery also scans complete snapshots, so an interrupted pointer write
does not hide a fully uploaded checkpoint. Incomplete uploads are never loaded.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid


SNAPSHOT_SCHEMA = "gakumas-mounted-snapshot/1"
RUN_SCHEMA = "gakumas-colab-run/1"


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def object_hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("wb") as stream:
            stream.write(canonical_bytes(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def safe_child(root, relative):
    root = Path(root).resolve()
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in ("..", "") for part in path.parts):
        raise ValueError(f"Unsafe snapshot path: {relative}")
    destination = root.joinpath(path).resolve()
    if destination == root or not destination.is_relative_to(root):
        raise ValueError(f"Snapshot path escaped its root: {relative}")
    return destination


def copy_verified(source, destination):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"Snapshot source must be a regular file: {source}")
    expected = file_hash(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    if file_hash(destination) != expected or file_hash(source) != expected:
        raise IOError(f"Snapshot copy checksum failed or source changed: {source}")
    return {"sha256": expected, "size": destination.stat().st_size}


def bind_identity(run_dir, identity):
    """Never reuse a run name for a different task/config/bundle/source identity."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run-identity.json"
    if path.exists():
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual != identity:
            raise ValueError(f"Run identity mismatch at {run_dir}; choose a new run name")
    else:
        unexpected = [p.name for p in run_dir.iterdir() if p.name not in ("STOP",)]
        if unexpected:
            raise ValueError(f"Unidentified existing run directory: {run_dir}")
        # Exclusive creation rejects a competing initializer instead of replacing
        # its identity. A partial identity file fails closed on recovery.
        with path.open("xb") as stream:
            stream.write(canonical_bytes(identity) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())


class SnapshotStore:
    def __init__(self, persistent_root, run_name, identity, *, keep=3):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_name):
            raise ValueError("run-name must be 1-80 safe letters, digits, dots, dashes or underscores")
        if keep < 1:
            raise ValueError("At least one complete snapshot must be retained")
        self.run_dir = Path(persistent_root).resolve() / run_name
        self.identity = identity
        self.identity_sha256 = object_hash(identity)
        self.keep = keep
        bind_identity(self.run_dir, identity)
        self.snapshots_dir = self.run_dir / "snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)
        self.last_generation = None
        self.recovery_warnings = []
        self._source_offsets = {}
        self._invalid_snapshots = set()
        self._validated_cache = {}

    def _validate(self, snapshot, *, validate_logs=True):
        snapshot = Path(snapshot)
        if snapshot.is_symlink() or snapshot.resolve().parent != self.snapshots_dir.resolve():
            raise ValueError("Snapshot is outside the run's snapshot directory")
        if not validate_logs and snapshot.name in self._validated_cache:
            # Snapshots are immutable. Restore and newly uploaded snapshots are
            # fully checked; repeated batch commits need not re-read old weights
            # and historical log chunks from mounted Drive.
            return self._validated_cache[snapshot.name]
        commit = json.loads((snapshot / "COMMITTED.json").read_text(encoding="utf-8"))
        if file_hash(snapshot / "snapshot.json") != commit["manifest_sha256"]:
            raise ValueError("Snapshot manifest checksum mismatch")
        manifest = json.loads((snapshot / "snapshot.json").read_text(encoding="utf-8"))
        if manifest.get("schema") != SNAPSHOT_SCHEMA or manifest.get("identity_sha256") != self.identity_sha256:
            raise ValueError("Snapshot schema/identity mismatch")
        if not isinstance(manifest.get("generation"), int) or manifest["generation"] < 0:
            raise ValueError("Invalid snapshot generation")
        files = manifest["files"]
        for required in ("checkpoints/latest.pt", "run-identity.json", "manifest.json", "colab-state.json"):
            if required not in files:
                raise ValueError(f"Snapshot is missing {required}")
        for relative, expected in files.items():
            path = safe_child(snapshot, relative)
            if path.is_symlink() or not path.is_file() or path.stat().st_size != expected["size"]:
                raise ValueError(f"Snapshot file missing or wrong size: {relative}")
            if file_hash(path) != expected["sha256"]:
                raise ValueError(f"Snapshot checksum mismatch: {relative}")
        for relative, log in manifest.get("logs", {}).items():
            safe_child(snapshot, relative)
            if sum(c["size"] for c in log["chunks"]) != log["size"]:
                raise ValueError("Log chunk lengths do not match the manifest")
            if validate_logs:
                for chunk in log["chunks"]:
                    path = safe_child(self.run_dir, chunk["path"])
                    if (not path.is_file() or path.stat().st_size != chunk["size"] or
                            file_hash(path) != chunk["sha256"]):
                        raise ValueError(f"Log chunk checksum mismatch: {chunk['path']}")
        state = json.loads((snapshot / "colab-state.json").read_text(encoding="utf-8"))
        if state["identity_sha256"] != self.identity_sha256:
            raise ValueError("Snapshot state belongs to another run")
        result = {"path": snapshot, "manifest": manifest, "state": state}
        self._validated_cache[snapshot.name] = result
        return result

    def complete_snapshots(self, *, validate_logs=True):
        complete, warnings = [], []
        for path in self.snapshots_dir.iterdir():
            if not path.is_dir() or not path.name.startswith("snapshot-"):
                continue
            if not validate_logs and path.name in self._invalid_snapshots:
                continue
            try:
                complete.append(self._validate(path, validate_logs=validate_logs))
                self._invalid_snapshots.discard(path.name)
            except (OSError, ValueError, KeyError, TypeError) as error:
                warnings.append({"snapshot": path.name, "error": str(error)})
                self._invalid_snapshots.add(path.name)
                self._validated_cache.pop(path.name, None)
        if validate_logs:
            self.recovery_warnings = warnings
        return sorted(complete, key=lambda row: (row["manifest"]["generation"], row["path"].name))

    def latest(self, *, validate_logs=True):
        snapshots = self.complete_snapshots(validate_logs=validate_logs)
        latest = snapshots[-1] if snapshots else None
        self.last_generation = latest["manifest"]["generation"] if latest else -1
        committed_artifacts = any(path.name.startswith("snapshot-") for path in self.snapshots_dir.iterdir())
        if latest is None and ((self.run_dir / "latest.json").exists() or committed_artifacts):
            raise ValueError("Persistent run has committed snapshot data but no valid recoverable snapshot; refusing to reset")
        return latest

    def restore(self, local_run):
        latest = self.latest()
        if latest is None:
            return None
        local_run = Path(local_run)
        bind_identity(local_run, self.identity)
        # Restore each immutable file through a verified temporary file. The
        # local tree is disposable; the persistent snapshot remains untouched.
        for relative in latest["manifest"]["files"]:
            source = safe_child(latest["path"], relative)
            destination = safe_child(local_run, relative)
            temporary = destination.with_name(destination.name + ".restore-" + uuid.uuid4().hex)
            try:
                copy_verified(source, temporary)
                os.replace(temporary, destination)
            finally:
                if temporary.exists():
                    temporary.unlink()
        for namespace in ("training", "evaluation"):
            base = local_run / namespace
            if base.exists():
                for path in base.rglob("*.jsonl"):
                    if path.relative_to(local_run).as_posix() not in latest["manifest"].get("logs", {}):
                        if path.is_symlink() or not path.resolve().is_relative_to(local_run.resolve()):
                            raise ValueError("Stale local log escaped its run directory")
                        path.unlink()
        for relative, log in latest["manifest"].get("logs", {}).items():
            destination = safe_child(local_run, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".restore-" + uuid.uuid4().hex)
            try:
                with temporary.open("xb") as stream:
                    for chunk in log["chunks"]:
                        with safe_child(self.run_dir, chunk["path"]).open("rb") as source:
                            shutil.copyfileobj(source, stream, length=1024 * 1024)
                    stream.flush()
                    os.fsync(stream.fileno())
                if temporary.stat().st_size != log["size"]:
                    raise IOError("Restored log length mismatch")
                os.replace(temporary, destination)
                self._source_offsets[relative] = destination.stat().st_size
            finally:
                if temporary.exists():
                    temporary.unlink()
        return latest["state"]

    def _log_updates(self, local_run, previous):
        """Upload append-only chunks; avoid re-copying an ever-growing log.

        Episode metadata is compacted for Drive. The terminal score, failure
        outcome, seed, identity and rating provenance are retained, while large
        repeated engine artifacts remain in the disposable local logs.
        """
        logs = json.loads(json.dumps(previous or {}))
        offsets = {}
        for namespace in ("training", "evaluation"):
            base = local_run / namespace
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.jsonl")):
                relative = path.relative_to(local_run).as_posix()
                old = logs.get(relative, {"size": 0, "source_bytes": 0, "chunks": []})
                offset = self._source_offsets.get(relative, old["source_bytes"])
                if path.stat().st_size < offset:
                    raise ValueError(f"Append-only log was truncated: {relative}")
                chunks, buffer = list(old["chunks"]), bytearray()

                def flush():
                    if not buffer:
                        return
                    data = bytes(buffer)
                    checksum = hashlib.sha256(data).hexdigest()
                    blob = self.run_dir / "log-chunks" / (checksum + ".jsonl")
                    blob.parent.mkdir(exist_ok=True)
                    if not blob.exists():
                        temporary = blob.with_name(blob.name + ".tmp-" + uuid.uuid4().hex)
                        with temporary.open("xb") as dst:
                            dst.write(data)
                            dst.flush()
                            os.fsync(dst.fileno())
                        if file_hash(temporary) != checksum:
                            raise IOError("Uploaded log chunk checksum mismatch")
                        os.replace(temporary, blob)
                    if blob.stat().st_size != len(data) or file_hash(blob) != checksum:
                        raise IOError("Existing log chunk is corrupt")
                    chunks.append({"path": blob.relative_to(self.run_dir).as_posix(),
                                   "sha256": checksum, "size": len(data)})
                    buffer.clear()

                with path.open("rb") as source:
                    source.seek(offset)
                    while True:
                        row_start = source.tell()
                        line = source.readline()
                        if not line:
                            break
                        if not line.endswith(b"\n"):
                            source.seek(row_start)
                            break
                        if path.name == "episodes.jsonl":
                            row = json.loads(line)
                            metadata = row.get("metadata", {})
                            row["metadata"] = {k: v for k, v in metadata.items() if
                                k in ("rating_provenance", "completed_scenarios", "accepted_exam_count",
                                      "selected_support_ids", "selected_memory_ids", "selected_memory_specs", "setup_mode")
                                or isinstance(v, (str, int, float, bool, type(None)))}
                            line = canonical_bytes(row) + b"\n"
                        buffer.extend(line)
                        if len(buffer) >= 4 * 1024 * 1024:
                            flush()
                    offsets[relative] = source.tell()
                flush()
                logs[relative] = {"size": sum(c["size"] for c in chunks),
                                  "source_bytes": offsets[relative], "chunks": chunks,
                                  "format": "compact_episode_v1" if path.name == "episodes.jsonl" else "original_jsonl"}
        return logs, offsets

    def publish(self, local_run, state, *, checkpoint=None, refresh_state=None):
        local_run = Path(local_run).resolve()
        bind_identity(local_run, self.identity)
        if state.get("identity_sha256") != self.identity_sha256:
            raise ValueError("Refusing to publish a different run's state")
        previous = self.last_generation
        current = self.latest(validate_logs=False)
        if previous is not None and previous != self.last_generation:
            raise RuntimeError("Another writer advanced this persistent run; use one active session per run")
        generation = self.last_generation + 1
        atomic_json(local_run / "colab-state.json", state)
        checkpoint = Path(checkpoint or local_run / "checkpoints" / "latest.pt").resolve()
        if not checkpoint.is_relative_to(local_run):
            raise ValueError("Checkpoint must be inside this local run")
        files = {"checkpoints/latest.pt": checkpoint}
        for relative in ("run-identity.json", "manifest.json", "colab-state.json", "progress.json", "session.json", "initial-baseline.json"):
            candidate = local_run / relative
            if candidate.exists():
                files[relative] = candidate
        logs, offsets = self._log_updates(local_run, current["manifest"].get("logs") if current else None)
        upload = self.snapshots_dir / (".upload-" + uuid.uuid4().hex)
        upload.mkdir()
        records = {}
        # An interrupted upload is intentionally left as .upload-* and ignored.
        # This avoids treating partial mounted-Drive writes as checkpoints.
        for relative, source in files.items():
            records[relative] = copy_verified(source, safe_child(upload, relative))
        if refresh_state is not None:
            # Record wall time after the potentially lengthy mounted-Drive
            # upload, rather than omitting all upload time at session end.
            state.update(refresh_state())
            atomic_json(local_run / "colab-state.json", state)
            atomic_json(upload / "colab-state.json", state)
            records["colab-state.json"] = {"sha256": file_hash(upload / "colab-state.json"),
                                          "size": (upload / "colab-state.json").stat().st_size}
        manifest = {"schema": SNAPSHOT_SCHEMA, "identity_sha256": self.identity_sha256,
                    "generation": generation, "iteration": state["iteration"],
                    "created_at_ns": time.time_ns(), "files": records, "logs": logs}
        atomic_json(upload / "snapshot.json", manifest)
        atomic_json(upload / "COMMITTED.json", {"manifest_sha256": file_hash(upload / "snapshot.json")})
        # Detect another completed upload before committing our own pointer.
        before_commit = self.complete_snapshots(validate_logs=False)
        latest_generation = before_commit[-1]["manifest"]["generation"] if before_commit else -1
        if latest_generation != generation - 1:
            raise RuntimeError("Concurrent persistent writer detected before commit")
        committed = self.snapshots_dir / f"snapshot-{generation:08d}-{uuid.uuid4().hex[:12]}"
        os.replace(upload, committed)
        checked = self._validate(committed, validate_logs=False)
        atomic_json(self.run_dir / "latest.json", {"schema": SNAPSHOT_SCHEMA,
            "snapshot": committed.name, "generation": generation,
            "identity_sha256": self.identity_sha256,
            "manifest_sha256": file_hash(committed / "snapshot.json")})
        self.last_generation = generation
        self._source_offsets.update(offsets)
        # Delete only verified complete snapshots beyond the retention window,
        # and only after a new verified pointer was committed.
        complete = self.complete_snapshots(validate_logs=False)
        for obsolete in complete[:-self.keep]:
            path = obsolete["path"]
            if path.is_symlink() or path.resolve().parent != self.snapshots_dir.resolve():
                raise ValueError("Retention path escaped its snapshot directory")
            shutil.rmtree(path)
            self._validated_cache.pop(path.name, None)
        return checked
