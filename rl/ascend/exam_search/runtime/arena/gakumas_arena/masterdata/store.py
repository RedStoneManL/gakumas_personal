"""Access layer over the datamined master DB (vertesan/gakumasu-diff).

Design:
- The dump is a directory of <Table>.yaml files (list of row dicts). We never edit it.
- YAML parsing of the big tables is slow, so each table is converted once to JSON under
  <dump>/../masterdata_json/ (see tools/masterdata/build_cache.py); loads are lazy and memoised.
- `MasterData.table("ProduceCard")` -> list[dict]; `MasterData.by_id("ProduceCard")` -> dict[id, row].
- Higher layers (data/, engine/) build typed views on top of this; nothing else reads YAML.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

Row = dict[str, Any]

_REPO_ROOT = Path(__file__).resolve().parents[2]


def default_dump_dir() -> Path:
    return Path(os.environ.get("GAKUMAS_MASTERDATA_DIR", _REPO_ROOT / "data" / "raw" / "gakumasu-diff"))


def cache_dir_for(dump: Path) -> Path:
    return dump.parent / "masterdata_json"


def _load_yaml(path: Path) -> list[Row]:
    import yaml  # local import: only needed when the JSON cache is missing

    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    with path.open(encoding="utf-8") as f:
        data = yaml.load(f, Loader=loader)
    return data or []


def convert_table(dump: Path, table: str, force: bool = False) -> Path:
    src = dump / f"{table}.yaml"
    dst = cache_dir_for(dump) / f"{table}.json"
    if force or not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        dst.parent.mkdir(parents=True, exist_ok=True)
        rows = _load_yaml(src)
        try:
            import orjson

            dst.write_bytes(orjson.dumps(rows))
        except ImportError:
            dst.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return dst


class MasterData:
    def __init__(self, dump_dir: Path | str | None = None):
        self.dump = Path(dump_dir) if dump_dir else default_dump_dir()
        if not self.dump.is_dir():
            raise FileNotFoundError(
                f"master data dump not found at {self.dump}; run tools/masterdata/fetch.sh "
                "or set GAKUMAS_MASTERDATA_DIR")
        self._tables: dict[str, list[Row]] = {}
        self._index: dict[str, dict[str, Row]] = {}

    # ---- discovery ----
    def table_names(self) -> list[str]:
        return sorted(p.stem for p in self.dump.glob("*.yaml"))

    def __contains__(self, table: str) -> bool:
        return (self.dump / f"{table}.yaml").exists()

    # ---- access ----
    def table(self, name: str) -> list[Row]:
        if name not in self._tables:
            path = convert_table(self.dump, name)
            try:
                import orjson

                self._tables[name] = orjson.loads(path.read_bytes())
            except ImportError:
                self._tables[name] = json.loads(path.read_text(encoding="utf-8"))
        return self._tables[name]

    def by_id(self, name: str, key: str = "id") -> dict[str, Row]:
        k = f"{name}:{key}"
        if k not in self._index:
            idx: dict[str, Row] = {}
            for row in self.table(name):
                idx.setdefault(str(row[key]), row)  # first wins for duplicate keys
            self._index[k] = idx
        return self._index[k]

    def get(self, name: str, row_id: str, key: str = "id") -> Row | None:
        return self.by_id(name, key).get(row_id)

    def where(self, table: str, **eq: Any) -> Iterator[Row]:
        for row in self.table(table):
            if all(row.get(f) == v for f, v in eq.items()):
                yield row

    def group_by(self, name: str, key: str) -> dict[Any, list[Row]]:
        out: dict[Any, list[Row]] = {}
        for row in self.table(name):
            out.setdefault(row.get(key), []).append(row)
        return out

    def enum_values(self, name: str, field: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.table(name):
            v = row.get(field)
            if isinstance(v, str):
                counts[v] = counts.get(v, 0) + 1
        return dict(sorted(counts.items()))


@lru_cache(maxsize=1)
def shared() -> MasterData:
    """Process-wide singleton for convenience in scripts/tests."""
    return MasterData()
