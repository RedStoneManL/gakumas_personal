"""Versioned, searchable real master content; no game access and no per-card rule code.

Run ``python -m gakumas_arena.catalogue --help``. The SQLite export carries normalized
definitions and foreign-key edges; original YAML files remain the source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict, deque
from dataclasses import asdict
from pathlib import Path

from gakumas_arena.content.native import NATIVE_EXAM_CAPABILITY_VERSION, inspect_native_exam

VERSION = "arena-catalogue/1"
SOURCE_URL = "https://github.com/vertesan/gakumasu-diff"
KINDS = {
    "cards": "ProduceCard",
    "drinks": "ProduceDrink",
    "p_items": "ProduceItem",
    "custom_items": "ProduceCustomizeItem",
    "idols": "IdolCard",
    "supports": "SupportCard",
    "characters": "Character",
    "items": "Item",
    "memory_abilities": "MemoryAbility",
    "memory_gifts": "MemoryGift",
    "card_customizations": "ProduceCardCustomize",
}
VARIANTS = {"cards": "upgradeCount", "card_customizations": "customizeCount"}
EXAM_TABLES = {"ProduceCard", "ProduceDrink", "ProduceItem"}
REFERENCE_ALIASES = {
    "skillId": "ProduceSkill",
    "secondProduceCardId": "ProduceCard",
    "beforeProduceItemId": "ProduceItem",
    "afterProduceItemId": "ProduceItem",
    "beforeLevelLimitProduceItemId": "ProduceItem",
    "afterLevelLimitProduceItemId": "ProduceItem",
    "originIdolCardId": "IdolCard",
    "originPrimaStellaIdolCardId": "IdolCard",
    "originSupportCardId": "SupportCard",
    "originCharacterId": "Character",
    "chainProduceExamEffectId": "ProduceExamEffect",
    "chainProduceExamEffectIds": "ProduceExamEffect",
    "targetProduceCardId": "ProduceCard",
    "fieldStatusProduceCardSearchIds": "ProduceCardSearch",
    "pickCountReferenceProduceCardSearchId": "ProduceCardSearch",
    "playEffectProduceExamTriggerId": "ProduceExamTrigger",
    "targetPlayEffectProduceExamTriggerIds": "ProduceExamTrigger",
    "targetPlayProduceExamEffectIds": "ProduceExamEffect",
    "playProduceExamTriggerId": "ProduceExamTrigger",
    "moveProduceExamEffectIds": "ProduceExamEffect",
    "moveProduceExamTriggerIds": "ProduceExamTrigger",
    "upgradeProduceCardSearchId": "ProduceCardSearch",
    "originalIdolCardSkinId": "IdolCardSkin",
    "examBattleProduceItemIds": "ProduceItem",
}


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def normalized(value):
    """Keep native numeric/enum/reference fields; omit presentation descriptions, never parse prose."""
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if "description" not in k.lower()}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


class Catalogue:
    def __init__(self, repository=None):
        if repository is None:
            from gakumas_arena.env import get_repository

            repository = get_repository()
        self.repository = repository
        self.tables = {}
        self.edges = {}
        self.entries = []
        self.by_key = {}
        self._inspection = {}
        # Include every table in the pinned dump. This preserves support skill level,
        # event rewards and resource references without guessing their ownership from IDs.
        self.paths = {p.stem: p for p in sorted(repository.assets_dir.glob("*.yaml"))}
        self.table_names = set(self.paths)
        self._by_id = {}
        for kind, table in KINDS.items():
            for row in self.table(table):
                self.entries.append(self._entry(kind, table, row))
        self.entries.sort(key=lambda e: e["key"])
        self.by_key = {e["key"]: e for e in self.entries}

    def table(self, name):
        if name not in self.tables:
            self.tables[name] = [normalized(r) for r in self.repository.load_table(name).rows]
            index = defaultdict(list)
            for row in self.tables[name]:
                if row.get("id") is not None:
                    index[str(row["id"])].append(row)
            self._by_id[name] = index
        return self.tables[name]

    def references(self, row):
        """Return typed native ID references with their exact source property path.

        ID lookup intentionally retains ALL variants. Resolved runtime selection still
        requires upgrade/customization/skill level, not first(id).
        """
        refs = []

        def walk(value, path="", object_table=None):
            if isinstance(value, list):
                for i, item in enumerate(value):
                    walk(item, f"{path}.{i}", object_table)
            elif isinstance(value, dict):
                for field, item in value.items():
                    fp = f"{path}.{field}".lstrip(".")
                    target = REFERENCE_ALIASES.get(field)
                    stem = field.removesuffix("Ids").removesuffix("Id")
                    if field[-1:].isdigit():
                        stem = field[:-1].removesuffix("Id")
                    candidate = stem[:1].upper() + stem[1:]
                    if candidate in self.table_names and field != "id":
                        target = target or candidate
                    if field == "id" and object_table:
                        target = object_table
                    if target and isinstance(item, (str, list)):
                        for key in item if isinstance(item, list) else [item]:
                            if isinstance(key, str) and key:
                                refs.append({"table": target, "id": key, "path": fp})
                    nested = {
                        "produceCard": "ProduceCard",
                        "examBattleProduceCards": "ProduceCard",
                        "memoryAbilities": "MemoryAbility",
                    }.get(field)
                    walk(item, fp, nested)

        walk(row)
        return refs

    def _entry(self, kind, table, row):
        rid = str(row["id"])
        variant_field = VARIANTS.get(kind)
        variant = int(row.get(variant_field, 0)) if variant_field else None
        key = f"{kind}/{rid}" + (f"@{variant}" if variant is not None else "")
        name = str(
            row.get("name") or (str(row.get("lastName", "")) + str(row.get("firstName", ""))) or rid
        )
        translated = (
            {
                "cards": self.repository.produce_card_localization,
                "drinks": self.repository.produce_drink_localization,
                "p_items": self.repository.produce_item_localization,
            }.get(kind, {})
            .get(rid, {})
            .get("name")
        )
        issues = []
        if table in EXAM_TABLES:
            signature = (
                table,
                canonical({k: v for k, v in row.items() if k not in {"name", "assetId", "order"}}),
            )
            if signature not in self._inspection:
                self._inspection[signature] = [
                    asdict(i) for i in inspect_native_exam(self.repository, table, row)
                ]
            issues = self._inspection[signature]
        status = (
            "unsupported" if issues else "eligible" if table in EXAM_TABLES else "not_applicable"
        )
        refs = self.references(row)
        self.edges[key] = refs
        return {
            "key": key,
            "kind": kind,
            "table": table,
            "id": rid,
            "variant": variant,
            "variant_field": variant_field,
            "name": translated or name,
            "name_ja": name,
            "plan": row.get("planType"),
            "rarity": row.get("rarity"),
            "category": row.get("category", row.get("type")),
            "hidden": bool(row.get("libraryHidden", False)),
            "limited": bool(row.get("isLimited", False)),
            "view_start_time": row.get("viewStartTime"),
            "offline_exam": status,
            "issues": issues,
            "validation": "definition_inspected" if table in EXAM_TABLES else "catalogued",
            "real_game_verified": False,
            "references": refs,
        }

    def search(self, query="", *, kind=None, plan=None, status=None, include_hidden=True):
        query = query.casefold()
        return [
            dict(e)
            for e in self.entries
            if (kind is None or e["kind"] == kind)
            and (plan is None or e["plan"] == plan)
            and (status is None or e["offline_exam"] == status)
            and (include_hidden or not e["hidden"])
            and (not query or query in " ".join((e["key"], e["name"], e["name_ja"])).casefold())
        ]

    def definition(self, key):
        entry = self.by_key[key]
        candidates = [r for r in self.table(entry["table"]) if r.get("id") == entry["id"]]
        if entry["variant_field"]:
            candidates = [
                r for r in candidates if int(r.get(entry["variant_field"], 0)) == entry["variant"]
            ]
        if len(candidates) != 1:
            raise ValueError(f"ambiguous native definition: {key}")
        return candidates[0]

    def inspect(self, key):
        """Direct relations plus transitive MECHANISM closure, not all flavour assets."""
        entry = self.by_key[key]
        queue = deque(self.references(self.definition(key)))
        definitions, missing, seen = [], [], set()
        follow = {
            "ProduceExamEffect",
            "ProduceExamTrigger",
            "ProduceExamStatusEnchant",
            "ProduceCardStatusEnchant",
            "ProduceCardGrowEffect",
            "ProduceCardSearch",
            "ProduceDrinkEffect",
            "ProduceItemEffect",
            "ProduceEffect",
            "ProduceTrigger",
            "ProduceSkill",
            "ProduceCardCustomize",
        }
        while queue:
            ref = queue.popleft()
            pair = ref["table"], ref["id"]
            if pair in seen or ref["table"] not in follow:
                continue
            seen.add(pair)
            self.table(ref["table"])
            rows = self._by_id[ref["table"]].get(ref["id"], [])
            if not rows:
                missing.append(ref)
            for row in rows:
                definitions.append({"table": ref["table"], "row": row})
                queue.extend(self.references(row))
        owners = [
            e["key"]
            for e in self.entries
            if any(r["table"] == entry["table"] and r["id"] == entry["id"] for r in e["references"])
        ]
        return {
            "entry": entry,
            "definition": self.definition(key),
            "referenced_by": owners,
            "mechanism_definitions": definitions,
            "missing_references": missing,
            "live_definition_issues": [
                asdict(i)
                for i in inspect_native_exam(
                    self.repository, entry["table"], self.definition(key), live=True
                )
            ]
            if entry["table"] in EXAM_TABLES
            else None,
        }

    def manifest(self):
        assets = self.repository.assets_dir
        revision = subprocess.check_output(
            ["git", "-C", str(assets), "rev-parse", "HEAD"], text=True
        ).strip()
        files = {
            name + ".yaml": hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in self.paths.items()
        }
        data_hash = hashlib.sha256(canonical(files).encode()).hexdigest()
        counts = {}
        for kind in KINDS:
            rows = [e for e in self.entries if e["kind"] == kind]
            counts[kind] = {
                "definitions": len(rows),
                "unique_ids": len({e["id"] for e in rows}),
                "hidden_definitions": sum(e["hidden"] for e in rows),
                "offline_exam": dict(Counter(e["offline_exam"] for e in rows)),
            }
        issues = Counter(i["mechanism"] for e in self.entries for i in e["issues"])
        return {
            "schema_version": VERSION,
            "source": {
                "url": SOURCE_URL,
                "revision": revision,
                "data_sha256": data_hash,
                "files": files,
            },
            "counts": counts,
            "entry_count": len(self.entries),
            "capability_version": NATIVE_EXAM_CAPABILITY_VERSION,
            "mechanism_issues": dict(issues.most_common()),
            "scope": "all rows in the pinned community dump; not a claim of current obtainability",
            "eligibility": "static offline exam integration check; no numerical or live fidelity certification",
            "omitted_fields": "keys containing description (display text/templates only)",
            "live_scope": "existing arena-live contracts still apply; catalogue is not observed state",
            "references": [
                {"url": "https://gktools.ris.moe/en/dex", "role": "independent reference"},
                {
                    "url": "https://seesaawiki.jp/gakumasu/",
                    "role": "wiki cross-check; prose not copied",
                },
            ],
        }

    def export(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        manifest = self.manifest()
        payload = {
            "schema_version": VERSION,
            "source_revision": manifest["source"]["revision"],
            "data_sha256": manifest["source"]["data_sha256"],
            "capability_version": manifest["capability_version"],
            "entries": self.entries,
        }
        write_json(directory / "catalogue.json", payload)
        db_path = directory / "catalogue.sqlite3"
        # A dedicated generated database only; replace its schema transactionally.
        with sqlite3.connect(db_path) as db:
            db.executescript("""
                DROP TABLE IF EXISTS metadata; DROP TABLE IF EXISTS entries;
                DROP TABLE IF EXISTS definitions; DROP TABLE IF EXISTS relations;
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE entries (key TEXT PRIMARY KEY, kind TEXT, native_id TEXT, variant INTEGER,
                    name TEXT, name_ja TEXT, offline_exam TEXT, payload TEXT NOT NULL);
                CREATE TABLE definitions (table_name TEXT, row_key TEXT, native_id TEXT, payload TEXT NOT NULL,
                    PRIMARY KEY(table_name, row_key));
                CREATE TABLE relations (source_table TEXT, source_row_key TEXT, target_table TEXT, target_id TEXT, field_path TEXT);
                CREATE INDEX definitions_lookup ON definitions(table_name, native_id);
                CREATE INDEX relations_reverse ON relations(target_table, target_id);
            """)
            db.execute("INSERT INTO metadata VALUES (?, ?)", ("manifest", canonical(manifest)))
            db.executemany(
                "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?)",
                [
                    (
                        e["key"],
                        e["kind"],
                        e["id"],
                        e["variant"],
                        e["name"],
                        e["name_ja"],
                        e["offline_exam"],
                        canonical(e),
                    )
                    for e in self.entries
                ],
            )
            table_counts = {}
            for name in sorted(self.table_names):
                # Localization/Help/Story text isn't necessary for numeric content reuse.
                if not name.startswith(
                    ("Produce", "Exam", "IdolCard", "SupportCard", "Memory", "Character")
                ) and name not in {"Item", "LimitItem"}:
                    continue
                rows = self.table(name)
                table_counts[name] = len(rows)
                occurrences = Counter()
                for row in rows:
                    raw = canonical(row)
                    digest = hashlib.sha256(raw.encode()).hexdigest()
                    occurrences[digest] += 1
                    row_key = digest + ":" + str(occurrences[digest])
                    db.execute(
                        "INSERT INTO definitions VALUES (?,?,?,?)",
                        (name, row_key, str(row.get("id", "")), raw),
                    )
                    db.executemany(
                        "INSERT INTO relations VALUES (?,?,?,?,?)",
                        [
                            (name, row_key, r["table"], r["id"], r["path"])
                            for r in self.references(row)
                        ],
                    )
            manifest["exported_tables"] = table_counts
            db.execute("UPDATE metadata SET value=? WHERE key='manifest'", (canonical(manifest),))
        for name in ("catalogue.json", "catalogue.sqlite3"):
            manifest.setdefault("artifacts", {})[name] = hashlib.sha256(
                (directory / name).read_bytes()
            ).hexdigest()
        write_json(directory / "manifest.json", manifest)
        return manifest


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Arena 真实内容目录（不操作游戏）")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("search")
    s.add_argument("query", nargs="?", default="")
    s.add_argument("--kind", choices=KINDS)
    s.add_argument("--plan")
    s.add_argument("--status", choices=("eligible", "unsupported", "not_applicable"))
    s.add_argument("--visible-only", action="store_true")
    s.add_argument("--limit", type=int, default=30)
    sub.add_parser("inspect").add_argument("key", help="e.g. cards/p_card-01-act-1_002@0")
    sub.add_parser("summary")
    sub.add_parser("export").add_argument("directory")
    sub.add_parser("verify").add_argument("manifest")
    for p in sub.choices.values():
        p.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        catalogue = Catalogue()
        if args.command == "search":
            found = catalogue.search(
                args.query,
                kind=args.kind,
                plan=args.plan,
                status=args.status,
                include_hidden=not args.visible_only,
            )
            result = {"total": len(found), "entries": found[: max(0, args.limit)]}
        elif args.command == "inspect":
            result = catalogue.inspect(args.key)
        elif args.command == "export":
            result = catalogue.export(args.directory)
        elif args.command == "verify":
            expected = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            current = catalogue.manifest()
            changed = sorted(
                k
                for k in expected["source"]["files"].keys() | current["source"]["files"].keys()
                if expected["source"]["files"].get(k) != current["source"]["files"].get(k)
            )
            artifact_changes = []
            for name, digest in expected.get("artifacts", {}).items():
                path = Path(args.manifest).parent / name
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    artifact_changes.append(name)
            result = {
                "valid": not changed
                and not artifact_changes
                and expected.get("capability_version") == current["capability_version"]
                and expected["source"]["revision"] == current["source"]["revision"],
                "capability_version_changed": expected.get("capability_version")
                != current["capability_version"],
                "changed_files": changed,
                "changed_artifacts": artifact_changes,
                "current_revision": current["source"]["revision"],
            }
        else:
            result = catalogue.manifest()
        if args.output:
            write_json(args.output, result)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("valid") is False else 0
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
