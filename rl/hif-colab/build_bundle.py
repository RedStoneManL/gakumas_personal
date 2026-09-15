#!/usr/bin/env python3
"""Build or verify the explicitly allowlisted, offline HIF Colab readiness bundle.

This script uses the Python standard library only. It never starts training, loads
checkpoint tensors, changes source files, or recursively scans the workspace.
The archive is a source snapshot, not a claim that a full-produce trainer exists.
Identical inputs and Python/zlib versions produce identical archive bytes.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import unicodedata
import zipfile

SCHEMA = "hif-colab-bundle/1"
MAX_UNCOMPRESSED_BYTES = 4 * 1024**3
MAX_FILE_COUNT = 40000
MAX_MANIFEST_BYTES = 16 * 1024**2
MAX_DESIGN_JSON_BYTES = 2 * 1024**2
CHUNK_BYTES = 1024**2
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
FIXED_TIMESTAMP = "1980-01-01T00:00:00Z"
EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".venv", "venv", "__pycache__", "node_modules", "build", "runs",
    "logs", "log", ".cache", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "maa", "maagakumas", "image_cache", "live",
})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo", ".log", ".bak", ".tmp"})
TEXT_SOURCE_SUFFIXES = (".py", ".json", ".yaml", ".yml", ".mjs", ".js", ".csv", ".jsonl", ".md", ".txt", ".html")
CAPABILITIES = {
    "schema": "hif-colab-capabilities/1",
    "training_enabled": False,
    "full_produce_trainer_implemented": False,
    "purpose": "offline source snapshot, installation and native simulator readiness checks",
    "checkpoint_policy": "optional explicit local checkpoint; never loaded by this packager",
}


class BundleError(ValueError):
    """The selected source snapshot or archive violates the bundle contract."""


@dataclass(frozen=True)
class IncludeRule:
    source: str
    destination: str
    suffixes: tuple[str, ...] | None = None
    required: bool = True
    recursive: bool = True


# Reviewed directory boundaries, not an unrestricted workspace scan. Runtime
# mappings intentionally preserve Arena's relative master-data/vendor paths.
DEFAULT_RULES = (
    IncludeRule("third_party/gakumas_arena/pyproject.toml", "arena/pyproject.toml"),
    IncludeRule("third_party/gakumas_arena/README.md", "arena/README.md"),
    IncludeRule("third_party/gakumas_arena/AGENT_ENTRY.md", "arena/AGENT_ENTRY.md"),
    IncludeRule("third_party/gakumas_arena/gakumas_arena", "arena/gakumas_arena", TEXT_SOURCE_SUFFIXES),
    IncludeRule("third_party/gakumas_arena/gakumas_rl", "arena/gakumas_rl", TEXT_SOURCE_SUFFIXES),
    IncludeRule("third_party/gakumas_arena/data/raw/gakumasu-diff", "arena/data/raw/gakumasu-diff", (".yaml",), recursive=False),
    IncludeRule("third_party/gakumas_arena/docs", "arena/docs", (".md", ".json")),
    IncludeRule("third_party/gakumas_arena/third_party/gakumas_rl_upstream/LICENSE", "arena/third_party/gakumas_rl_upstream/LICENSE"),
    IncludeRule("third_party/gakumas_arena/third_party/gakumas_rl_upstream/README.upstream.md", "arena/third_party/gakumas_rl_upstream/README.upstream.md"),
    IncludeRule("third_party/gakumas_arena/third_party/gakumas_rl_upstream/PROVENANCE.txt", "arena/third_party/gakumas_rl_upstream/PROVENANCE.txt"),
    IncludeRule("design/rl-full-produce-20260910", "design", (".md", ".json", ".py", ".xml")),
    IncludeRule("rl/drink-supply/runtime/shared/round2rl", "runtime/shared/round2rl", (".py", ".json")),
    IncludeRule("rl/drink-supply/runtime/shared/r1rl", "runtime/shared/r1rl", (".py", ".json")),
    IncludeRule("rl/drink-supply/draftrl", "runtime/draftrl", (".py",)),
    IncludeRule("rl/hif-colab/scripts", "scripts", (".py", ".sh", ".txt", ".json")),
    IncludeRule("rl/hif-colab/config", "config", (".json", ".yaml", ".yml", ".txt")),
    IncludeRule("rl/hif-colab/colab", "colab", (".ipynb", ".md", ".py", ".txt")),
    IncludeRule("rl/hif-colab/build_bundle.py", "scripts/build_bundle.py"),
    IncludeRule("rl/hif-colab/README.md", "README.md"),
)


@dataclass(frozen=True)
class SourceFile:
    path: Path
    source: str
    size: int
    signature: tuple[int, ...]


class SourceInventory(dict):
    def __init__(self, files=(), omitted=()):
        super().__init__(files)
        self.omitted = tuple(omitted)


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def safe_archive_path(name: str) -> str:
    """Require one canonical path that is safe on both Linux and Windows."""
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise BundleError(f"invalid archive path: {name!r}")
    if name.startswith("/") or any(ord(ch) < 32 for ch in name):
        raise BundleError(f"invalid archive path: {name!r}")
    parts = name.split("/")
    if any(part in {"", ".", ".."} or part[-1:] in {" ", "."} for part in parts):
        raise BundleError(f"noncanonical archive path: {name!r}")
    reserved = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)
    if any(reserved.match(part) for part in parts):
        raise BundleError(f"reserved archive path: {name!r}")
    if PurePosixPath(name).is_absolute():
        raise BundleError(f"absolute archive path: {name!r}")
    return name


def _collision_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _validate_name_set(names: list[str]) -> None:
    seen: set[str] = set()
    for name in names:
        key = _collision_key(safe_archive_path(name))
        if key in seen:
            raise BundleError(f"duplicate or case-colliding archive path: {name}")
        seen.add(key)
    for key in seen:
        parts = key.split("/")
        if any("/".join(parts[:n]) in seen for n in range(1, len(parts))):
            raise BundleError(f"file/directory collision: {key}")


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _signature(info: os.stat_result) -> tuple[int, ...]:
    # On Windows, lstat's cached creation time and handle fstat's creation time
    # can briefly disagree for newly written files. mtime, size and file identity
    # are consistent; POSIX ctime additionally detects metadata changes.
    change_time = info.st_ctime_ns if os.name != "nt" else 0
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, change_time)


def _checked_source(workspace: Path, relative: str) -> Path:
    safe_archive_path(relative)
    current = workspace
    for component in relative.split("/"):
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            return workspace / relative
        if _is_reparse(info):
            raise BundleError(f"source symlink/junction is forbidden: {relative}")
    if not current.resolve().is_relative_to(workspace):
        raise BundleError(f"source escapes workspace: {relative}")
    return current


def _selected_files(path: Path, suffixes: tuple[str, ...] | None, recursive: bool = True):
    info = path.lstat()
    if _is_reparse(info):
        raise BundleError(f"source symlink/junction is forbidden: {path.name}")
    if stat.S_ISREG(info.st_mode):
        if path.suffix.lower() not in EXCLUDED_SUFFIXES and (
            suffixes is None or path.suffix.lower() in suffixes or path.name.upper().startswith("LICENSE")
        ):
            yield path
        return
    if not stat.S_ISDIR(info.st_mode):
        raise BundleError(f"special source file is forbidden: {path.name}")
    with os.scandir(path) as entries:
        children = sorted(entries, key=lambda entry: entry.name)
    for entry in children:
        if entry.name.lower() in EXCLUDED_DIRECTORIES or entry.name.endswith(".egg-info"):
            continue
        if entry.name.startswith(".env"):
            continue
        if not recursive and entry.is_dir(follow_symlinks=False):
            continue
        yield from _selected_files(Path(entry.path), suffixes, recursive)


def collect_sources(workspace: Path, rules=DEFAULT_RULES, checkpoint: Path | None = None) -> dict[str, SourceFile]:
    workspace = workspace.resolve(strict=True)
    if not workspace.is_dir():
        raise BundleError("workspace must be a directory")
    result: dict[str, SourceFile] = {}
    omitted = []
    for rule in rules:
        base = _checked_source(workspace, rule.source)
        if not base.exists():
            if rule.required:
                raise BundleError(f"required allowlisted source is missing: {rule.source}")
            continue
        is_directory = base.is_dir()
        for path in _selected_files(base, rule.suffixes, rule.recursive):
            destination = rule.destination
            if is_directory:
                destination += "/" + path.relative_to(base).as_posix()
            safe_archive_path(destination)
            if destination in result:
                raise BundleError(f"duplicate source mapping: {destination}")
            info = path.lstat()
            source = SourceFile(path, path.relative_to(workspace).as_posix(), info.st_size, _signature(info))
            if rule.destination == "design" and path.suffix.lower() == ".json" and info.st_size > MAX_DESIGN_JSON_BYTES:
                omitted.append((destination, source))
            else:
                result[destination] = source
    if checkpoint is not None:
        selected = checkpoint if checkpoint.is_absolute() else workspace / checkpoint
        selected = selected.absolute()
        if not selected.is_relative_to(workspace):
            raise BundleError("checkpoint must be explicitly selected inside this workspace")
        relative = selected.relative_to(workspace).as_posix()
        selected = _checked_source(workspace, relative)
        if selected.suffix.lower() != ".pt" or not selected.is_file():
            raise BundleError("checkpoint must be one existing .pt file")
        info = selected.lstat()
        result["pretrained/exam_actor_warmstart.pt"] = SourceFile(selected, relative, info.st_size, _signature(info))
    _validate_name_set(list(result))
    return SourceInventory(sorted(result.items()), sorted(omitted))


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def _read_stable(source: SourceFile, writer=None) -> str:
    before = source.path.lstat()
    if _is_reparse(before) or _signature(before) != source.signature:
        raise BundleError(f"source changed after inventory: {source.source}")
    digest = hashlib.sha256()
    copied = 0
    with source.path.open("rb") as reader:
        if _signature(os.fstat(reader.fileno())) != source.signature:
            raise BundleError(f"source replaced before read: {source.source}")
        while chunk := reader.read(CHUNK_BYTES):
            copied += len(chunk)
            if copied > source.size:
                raise BundleError(f"source grew during read: {source.source}")
            digest.update(chunk)
            if writer is not None:
                writer.write(chunk)
        after_open = os.fstat(reader.fileno())
    after_path = source.path.lstat()
    if copied != source.size or _is_reparse(after_path) or _signature(after_open) != source.signature or _signature(after_path) != source.signature:
        raise BundleError(f"source changed during read: {source.source}")
    return digest.hexdigest()


def _copy_source(archive: zipfile.ZipFile, name: str, source: SourceFile) -> dict:
    with archive.open(_zip_info(name), "w", force_zip64=True) as writer:
        digest = _read_stable(source, writer)
    return {"path": name, "source": source.source, "size": source.size, "sha256": digest, "compressed_size": archive.getinfo(name).compress_size}


def omission_records(sources: dict[str, SourceFile]) -> list[dict]:
    return [{"path": name, "source": source.source, "size": source.size, "sha256": _read_stable(source), "reason": "design JSON exceeds 2 MiB; raw replay/snapshot excluded, reproduction scripts retained"} for name, source in getattr(sources, "omitted", ())]


def _snapshot_hash(files: list[dict], omitted=()) -> str:
    records = [{key: row[key] for key in ("path", "source", "size", "sha256")} for row in files]
    return hashlib.sha256(canonical_json({"files": records, "omitted_large_design_files": list(omitted)})).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def build_bundle(sources: dict[str, SourceFile], output: Path, max_bytes: int = MAX_UNCOMPRESSED_BYTES) -> dict:
    generated_path = "config/bundle-capabilities.json"
    _validate_name_set(list(sources) + [generated_path, "manifest.json"])
    if len(sources) + 2 > MAX_FILE_COUNT:
        raise BundleError("file-count limit exceeded")
    if sum(source.size for source in sources.values()) > max_bytes:
        raise BundleError("uncompressed size limit exceeded")
    output = output.absolute()
    if any(output == source.path.absolute() for source in sources.values()):
        raise BundleError("output cannot overwrite a source file")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".hif-bundle-", suffix=".zip", dir=output.parent)
    os.close(descriptor)
    staged = Path(temporary)
    try:
        files = []
        omitted = omission_records(sources)
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for name, source in sorted(sources.items()):
                files.append(_copy_source(archive, name, source))
            generated_bytes = canonical_json(CAPABILITIES)
            archive.writestr(_zip_info(generated_path), generated_bytes)
            files.append({"path": generated_path, "source": "generated/bundle-capabilities", "size": len(generated_bytes), "sha256": hashlib.sha256(generated_bytes).hexdigest(), "compressed_size": archive.getinfo(generated_path).compress_size})
            files.sort(key=lambda item: item["path"])
            manifest = {
                "schema": SCHEMA,
                "timestamp": FIXED_TIMESTAMP,
                "timestamp_policy": "fixed archive timestamp; source identity is content-addressed",
                "training_enabled": False,
                "full_produce_trainer_implemented": False,
                "checkpoint_usage": "warm_start_only; no full-produce optimizer/collector resume state is provided",
                "payload_file_count": len(files),
                "payload_uncompressed_bytes": sum(item["size"] for item in files),
                "payload_compressed_bytes": sum(item["compressed_size"] for item in files),
                "source_snapshot_sha256": _snapshot_hash(files, omitted),
                "omitted_large_design_files": omitted,
                "files": files,
                "manifest_scope": "files and size totals exclude manifest.json; whole-archive SHA-256 is returned externally",
            }
            archive.writestr(_zip_info("manifest.json"), canonical_json(manifest))
        # A concurrent engine edit must not silently yield a mixed source snapshot.
        for source in list(sources.values()) + [source for _, source in getattr(sources, "omitted", ())]:
            now = source.path.lstat()
            if _is_reparse(now) or _signature(now) != source.signature:
                raise BundleError(f"source changed before build completed: {source.source}")
        result = verify_bundle(staged, max_bytes=max_bytes)
        os.replace(staged, output)
        return {**result, "output": str(output), "archive_sha256": _sha256_file(output), "archive_bytes": output.stat().st_size}
    finally:
        if staged.exists():
            staged.unlink()


def verify_bundle(path: Path, max_bytes: int = MAX_UNCOMPRESSED_BYTES) -> dict:
    """Validate metadata, safe names, exact inventory and streamed payload hashes.

    This checks integrity, not publisher authenticity. Compare the returned archive
    digest with a trusted digest before installing or executing bundled source.
    Nothing is extracted or executed by this function.
    """
    if max_bytes <= 0:
        raise BundleError("size limit must be positive")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILE_COUNT:
                raise BundleError("file-count limit exceeded")
            _validate_name_set([info.filename for info in infos])
            if any(info.is_dir() for info in infos):
                raise BundleError("explicit directory entries are not allowed")
            total_bytes = sum(info.file_size for info in infos)
            if total_bytes > max_bytes:
                raise BundleError("uncompressed size limit exceeded")
            for info in infos:
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not stat.S_ISREG(mode)):
                    raise BundleError(f"symlink or special ZIP entry: {info.filename}")
                if info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise BundleError(f"encrypted/unsupported ZIP entry: {info.filename}")
            by_name = {info.filename: info for info in infos}
            if "manifest.json" not in by_name or by_name["manifest.json"].file_size > MAX_MANIFEST_BYTES:
                raise BundleError("missing or oversized manifest.json")
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
                raise BundleError("unsupported manifest schema")
            if manifest.get("training_enabled") is not False or manifest.get("full_produce_trainer_implemented") is not False:
                raise BundleError("bundle must declare training disabled and no full-produce trainer")
            files = manifest.get("files")
            if not isinstance(files, list) or not all(isinstance(item, dict) for item in files):
                raise BundleError("invalid manifest files")
            names = [item.get("path") for item in files]
            _validate_name_set(names)
            if "manifest.json" in names or set(names) != set(by_name) - {"manifest.json"}:
                raise BundleError("missing or extra payload file compared with manifest")
            if files != sorted(files, key=lambda item: item["path"]):
                raise BundleError("manifest file inventory must be sorted")
            omitted = manifest.get("omitted_large_design_files", [])
            if not isinstance(omitted, list) or not all(isinstance(item, dict) for item in omitted):
                raise BundleError("invalid omitted-file inventory")
            _validate_name_set(names + [item.get("path") for item in omitted])
            for item in omitted:
                name = safe_archive_path(item.get("path"))
                safe_archive_path(item.get("source"))
                if not name.startswith("design/") or not name.endswith(".json") or type(item.get("size")) is not int or item["size"] <= MAX_DESIGN_JSON_BYTES or not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]) or not isinstance(item.get("reason"), str):
                    raise BundleError("invalid omitted large design file")
            for item in files:
                name = item["path"]
                safe_archive_path(item.get("source"))
                info = by_name[name]
                if type(item.get("size")) is not int or item["size"] < 0 or item["size"] != info.file_size:
                    raise BundleError(f"size mismatch: {name}")
                if type(item.get("compressed_size")) is not int or item["compressed_size"] != info.compress_size:
                    raise BundleError(f"compressed size mismatch: {name}")
                if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
                    raise BundleError(f"invalid SHA-256: {name}")
                digest = hashlib.sha256()
                read_bytes = 0
                with archive.open(name) as stream:
                    while chunk := stream.read(CHUNK_BYTES):
                        read_bytes += len(chunk)
                        if read_bytes > item["size"]:
                            raise BundleError(f"expanded size mismatch: {name}")
                        digest.update(chunk)
                if read_bytes != item["size"] or digest.hexdigest() != item["sha256"]:
                    raise BundleError(f"SHA-256 mismatch: {name}")
            expected = {
                "payload_file_count": len(files),
                "payload_uncompressed_bytes": sum(item["size"] for item in files),
                "payload_compressed_bytes": sum(item["compressed_size"] for item in files),
                "source_snapshot_sha256": _snapshot_hash(files, omitted),
            }
            if any(manifest.get(key) != value for key, value in expected.items()):
                raise BundleError("manifest aggregate mismatch")
            capability_name = "config/bundle-capabilities.json"
            if capability_name not in by_name or json.loads(archive.read(capability_name)) != CAPABILITIES:
                raise BundleError("missing or invalid readiness-only capabilities")
        return {"verified": True, "schema": SCHEMA, **expected, "archive_file_count": len(infos), "archive_uncompressed_bytes": total_bytes, "archive_bytes": path.stat().st_size, "archive_sha256": _sha256_file(path)}
    except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError, RuntimeError, EOFError, NotImplementedError) as exc:
        raise BundleError(f"invalid ZIP bundle: {exc}") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, help="default: <workspace>/rl/hif-colab/artifacts/hif-colab-readiness.zip")
    parser.add_argument("--checkpoint", type=Path, help="one explicit existing .pt inside the workspace; omitted by default")
    parser.add_argument("--inventory-only", action="store_true", help="read-only allowlist inventory; do not build a ZIP")
    parser.add_argument("--verify-only", type=Path, metavar="ZIP", help="verify an existing ZIP without extraction or execution")
    parser.add_argument("--max-uncompressed-bytes", type=int, default=MAX_UNCOMPRESSED_BYTES)
    args = parser.parse_args(argv)
    try:
        if args.verify_only:
            if args.output or args.checkpoint or args.inventory_only:
                parser.error("--verify-only cannot be combined with build options")
            result = verify_bundle(args.verify_only, max_bytes=args.max_uncompressed_bytes)
        else:
            workspace = args.workspace.resolve(strict=True)
            sources = collect_sources(workspace, checkpoint=args.checkpoint)
            if args.inventory_only:
                result = {"mode": "inventory-only", "schema": SCHEMA, "training_enabled": False, "selected_file_count": len(sources), "selected_uncompressed_bytes": sum(item.size for item in sources.values()), "omitted_large_design_files": omission_records(sources), "files": [{"path": name, "source": source.source, "size": source.size} for name, source in sources.items()]}
            else:
                output = args.output or workspace / "rl/hif-colab/artifacts/hif-colab-readiness.zip"
                result = build_bundle(sources, output, max_bytes=args.max_uncompressed_bytes)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (BundleError, OSError) as exc:
        print(f"Bundle error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
