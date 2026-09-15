"""Freeze the reviewed search experiment before adapting it; never overwrite a port."""
import hashlib
import json
from pathlib import Path
import shutil


def main():
    here = Path(__file__).resolve().parent
    source = here.parent / "generalist-search-soft-value"
    target = here / "exam_search"
    if target.exists():
        raise FileExistsError("exam_search already exists; refusing to overwrite adapted code")
    roots = ("draftrl", "runtime/shared", "runtime/arena", "setup", "tests")
    suffixes = {".py", ".json", ".yaml", ".yml", ".mjs", ".js", ".md", ".txt"}
    excluded = {".git", ".venv", "__pycache__", "node_modules", "build", "runs", ".pytest_cache"}
    files = [*source.glob('*.py'), source / "training-config.json"]
    for root in roots:
        files.extend(p for p in (source / root).rglob("*") if p.is_file()
                     and not set(p.relative_to(source).parts) & excluded
                     and (p.suffix in suffixes or p.name == "LICENSE"))
    records = []
    for path in sorted(files):
        relative = path.relative_to(source)
        data = path.read_bytes()
        out = target / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, out)
        if out.read_bytes() != data or path.read_bytes() != data:
            raise RuntimeError(f"Source changed during import: {relative}")
        records.append({"path": relative.as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    record = {"source": "rl/generalist-search-soft-value", "checkpoint_included": False,
              "scope": "Frozen code, setup and Arena; modifications are tracked separately in Git", "files": records}
    (here / "source-import.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(files), "bytes": sum(r['bytes'] for r in records)}))


if __name__ == "__main__":
    main()
