"""Standard-library-only ZIP validation, embedded verbatim in the notebook.

Nothing from the ZIP is imported or executed before every declared byte is
verified. A self-contained manifest detects corruption, not a forged publisher.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile

MAX_UNPACKED_BYTES = 4 * 1024**3
MAX_MEMBERS = 40_000
MAX_MANIFEST_BYTES = 16 * 1024**2
BUNDLE_SCHEMA = "hif-colab-training/1"


def safe_relative_path(raw):
    if not isinstance(raw, str) or not raw or "\\" in raw or ":" in raw:
        raise ValueError(f"非法 ZIP 路径：{raw!r}")
    if raw.startswith("/") or any(ord(ch) < 32 for ch in raw):
        raise ValueError(f"非法 ZIP 路径：{raw!r}")
    parts = raw.rstrip("/").split("/")
    if any(p in {"", ".", ".."} or p[-1:] in {" ", "."} for p in parts):
        raise ValueError(f"非规范 ZIP 路径：{raw!r}")
    reserved = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)
    if any(reserved.match(part) for part in parts):
        raise ValueError(f"保留路径：{raw!r}")
    return PurePosixPath(*parts).as_posix()


def _collision_key(name):
    return unicodedata.normalize("NFC", name).casefold()


def reject_path_collisions(names):
    keys = [_collision_key(name) for name in names]
    if len(set(keys)) != len(keys):
        raise ValueError("文件路径重复，或大小写 / Unicode 形式冲突")
    seen = set(keys)
    for key in keys:
        parts = key.split("/")
        if any("/".join(parts[:count]) in seen for count in range(1, len(parts))):
            raise ValueError(f"文件和目录路径冲突：{key}")


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"manifest JSON 键重复：{key}")
        result[key] = value
    return result


def validate_zip_archive(archive, expected_manifest_sha256=""):
    infos = archive.infolist()
    if not infos or len(infos) > MAX_MEMBERS:
        raise ValueError("ZIP 文件数量超出限制")
    if sum(info.file_size for info in infos) > MAX_UNPACKED_BYTES:
        raise ValueError("ZIP 解压大小超出限制")
    members, all_names = {}, set()
    directories = set()
    for info in infos:
        name = safe_relative_path(info.filename)
        collision = _collision_key(name)
        if collision in all_names:
            raise ValueError(f"ZIP 路径重复：{name}")
        all_names.add(collision)
        mode = (info.external_attr >> 16) & 0xFFFF
        kind = stat.S_IFMT(mode)
        if stat.S_ISLNK(mode) or kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise ValueError(f"ZIP 链接或特殊文件被拒绝：{name}")
        if info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise ValueError("ZIP 加密或压缩方式不受支持")
        if kind == stat.S_IFDIR and not info.is_dir():
            raise ValueError(f"ZIP 目录类型不一致：{name}")
        if info.is_dir():
            directories.add(name)
        else:
            members[name] = info
    if "manifest.json" not in members:
        raise ValueError("ZIP 根目录缺少 manifest.json，请上传新的训练包")
    reject_path_collisions(members)
    if any(_collision_key(directory) in {_collision_key(x) for x in members} for directory in directories):
        raise ValueError("ZIP 文件和目录冲突")
    manifest_info = members["manifest.json"]
    if manifest_info.file_size > MAX_MANIFEST_BYTES:
        raise ValueError("manifest 超出大小限制")
    raw_manifest = archive.read(manifest_info)
    manifest_sha256 = hashlib.sha256(raw_manifest).hexdigest()
    expected = expected_manifest_sha256.strip().lower()
    if expected and (not re.fullmatch(r"[0-9a-f]{64}", expected) or expected != manifest_sha256):
        raise ValueError("manifest SHA256 与指定值不符")
    manifest = json.loads(raw_manifest, object_pairs_hook=_unique_json_object)
    if manifest.get("schema") != BUNDLE_SCHEMA or not isinstance(manifest.get("files"), list):
        raise ValueError("不支持的 manifest schema；旧 readiness 包不能用于训练")
    entries = {}
    for row in manifest["files"]:
        if not isinstance(row, dict):
            raise ValueError("manifest 文件条目不是对象")
        name = safe_relative_path(row.get("path"))
        if name == "manifest.json" or name in entries or row["path"].endswith("/"):
            raise ValueError(f"manifest 自引用或重复路径：{name}")
        digest, size = row.get("sha256"), row.get("size")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"非法 SHA256：{name}")
        if type(size) is not int or size < 0:
            raise ValueError(f"非法文件大小：{name}")
        entries[name] = row
    reject_path_collisions(entries)
    if set(members) != set(entries) | {"manifest.json"}:
        missing = sorted(set(entries)-set(members))[:5]
        extra = sorted(set(members)-set(entries)-{"manifest.json"})[:5]
        raise ValueError(f"ZIP 与 manifest 文件集合不同；缺失={missing}，额外={extra}")
    # Explicit directory entries are allowed only when they contain declared files.
    for directory in directories:
        if not any(name.startswith(directory + "/") for name in members):
            raise ValueError(f"ZIP 存在未声明的空目录：{directory}")
    for name, row in entries.items():
        info = members[name]
        if info.file_size != row["size"]:
            raise ValueError(f"文件大小不符：{name}")
        digest = hashlib.sha256()
        with archive.open(info) as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != row["sha256"]:
            raise ValueError(f"文件 SHA256 不符：{name}")
    return members, manifest, manifest_sha256


def extract_verified_bundle(zip_path, parent, expected_manifest_sha256=""):
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        members, manifest, digest = validate_zip_archive(archive, expected_manifest_sha256)
        destination = Path(tempfile.mkdtemp(prefix="hif-training-", dir=parent)).resolve()
        try:
            for name, info in members.items():
                target = destination / name
                if not target.resolve().is_relative_to(destination):
                    raise ValueError(f"解压路径越界：{name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        except BaseException:
            # Only our freshly-created, resolved temporary directory is removed.
            if destination.parent == parent and destination.name.startswith("hif-training-"):
                shutil.rmtree(destination)
            raise
    return destination, manifest, digest
