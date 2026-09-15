"""Download pinned original artwork into a reusable, versioned local cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import tempfile
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

REVISION = "6c3d00648c32ea72a05086a18c63ab62e0d0c7e5"
GITHUB_IMAGES = (
    f"https://raw.githubusercontent.com/surisuririsu/gakumas-tools/{REVISION}"
    "/packages/gakumas-images/images"
)
ASSETS = Path(__file__).resolve().parent / "preview_assets"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[1] / "data/image_cache"
INDEXES = {
    "skillCards": "skill_card_icon_keys.json",
    "pItems": "p_item_icon_keys.json",
    "pDrinks": "p_drink_icon_keys.json",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def cache_path(cache_dir: str | Path | None = None) -> Path:
    """The supplied directory is a cache root; each upstream revision is isolated."""
    base = cache_dir or os.environ.get("GAKUMAS_ARENA_IMAGE_CACHE") or DEFAULT_CACHE_DIR
    return Path(base).expanduser().resolve() / REVISION


def indexed_images() -> list[str]:
    return [
        f"{kind}/icons/{key}.png"
        for kind, index in INDEXES.items()
        for key in json.loads((ASSETS / index).read_bytes())
    ]


def _validate_png(data: bytes) -> None:
    """Reject HTML errors, truncated files and damaged PNG chunks before caching."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("not a supported PNG image")
    offset = 8
    first = True
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        end = offset + 12 + size
        if end > len(data):
            break
        chunk = data[offset + 4 : offset + 8]
        if first and (chunk != b"IHDR" or size != 13):
            raise ValueError("PNG header is missing")
        first = False
        expected = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(data[offset + 4 : end - 4]) != expected:
            raise ValueError("PNG checksum failed")
        if chunk == b"IEND" and size == 0 and end == len(data):
            return
        offset = end
    raise ValueError("PNG is incomplete")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _fetch(relative: str, root: Path, allow_download: bool) -> dict:
    path = root / relative
    data = None
    try:
        candidate = path.read_bytes()
        _validate_png(candidate)
        data = candidate
    except (OSError, ValueError):
        pass
    hit = data is not None
    if data is None:
        if not allow_download:
            raise FileNotFoundError("valid image is not in the local cache")
        for attempt in range(3):
            try:
                with urlopen(f"{GITHUB_IMAGES}/{relative}", timeout=25) as response:
                    data = response.read(MAX_IMAGE_BYTES + 1)
                break
            except (URLError, TimeoutError) as error:
                if isinstance(error, HTTPError) and error.code not in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
        _validate_png(data)
        _atomic_write(path, data)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "cache_hit": hit,
    }


def cache_images(
    relatives,
    *,
    cache_dir: str | Path | None = None,
    allow_download: bool = True,
    workers: int = 8,
    progress=None,
) -> dict:
    """Cache only pinned, indexed artwork; errors remain explicit and retryable.

    ``allow_download=False`` guarantees no network calls. Existing valid files are
    reused. All requested paths are checked before any fetch is attempted.
    """
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("workers: expected 1 through 16")
    names = sorted(set(relatives))
    allowed = set(indexed_images())
    for name in names:
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"(skillCards|pItems|pDrinks)/icons/\d+(?:_\d+)?\.png", name)
            or name not in allowed
        ):
            raise ValueError(f"not a pinned icon path: {name!r}")
    root = cache_path(cache_dir)
    images, errors = {}, {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        jobs = {executor.submit(_fetch, name, root, allow_download): name for name in names}
        for done, job in enumerate(as_completed(jobs), 1):
            name = jobs[job]
            try:
                images[name] = job.result()
            except (OSError, ValueError) as error:
                errors[name] = str(error)
            if progress:
                progress(done, len(names))
    return {
        "revision": REVISION,
        "cache_dir": str(root),
        "images": dict(sorted(images.items())),
        "errors": dict(sorted(errors.items())),
        "summary": {
            "requested": len(names),
            "available": len(images),
            "downloaded": sum(not i["cache_hit"] for i in images.values()),
            "cached": sum(i["cache_hit"] for i in images.values()),
            "failed": len(errors),
            "bytes": sum(i["bytes"] for i in images.values()),
        },
    }


def cache_all_icons(**options) -> dict:
    """Preload every indexed card variant, P item and drink, and save a manifest."""
    result = cache_images(indexed_images(), **options)
    manifest = {"repository": "https://github.com/surisuririsu/gakumas-tools", **result}
    _atomic_write(
        Path(result["cache_dir"]) / "manifest.json",
        json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download all pinned Arena card/item/drink icons")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--offline", action="store_true", help="check existing cache without HTTP")
    args = parser.parse_args(argv)

    def progress(done, total):
        if done % 100 == 0 or done == total:
            print(f"Images: {done}/{total}", flush=True)

    result = cache_all_icons(
        cache_dir=args.cache_dir,
        workers=args.workers,
        allow_download=not args.offline,
        progress=progress,
    )
    print(json.dumps({"cache_dir": result["cache_dir"], **result["summary"]}, ensure_ascii=True))
    if result["errors"]:
        print(json.dumps(result["errors"], ensure_ascii=True))
        parser.exit(1)


if __name__ == "__main__":
    main()
