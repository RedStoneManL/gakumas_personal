"""Rebuild the reviewed manifest; run from the repository root and review its diff.

This records known structural vocabulary, not proof of backend execution parity.
No training-time raw YAML parsing or catalogue-wide neural encoding is needed.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re


def build(root):
    def read(relative):
        return json.loads((root / relative).read_text(encoding="utf-8"))
    produce_path = "design/rl-state-schema-20260910/produce-effect-registry.json"
    exam_path = "design/rl-state-schema-20260910/exam-effect-registry.json"
    native_path = "third_party/gakumas_arena/data/reference/gakumas_tools_effects.json"
    constants_path = "third_party/gakumas_arena/gakumas_arena/_vendor/gakumas_tools/packages/gakumas-engine/constants.js"
    produce, exam, native = map(read, (produce_path, exam_path, native_path))
    node_fields, symbols = defaultdict(set), defaultdict(set)
    def visit(value):
        if isinstance(value, dict):
            kind = value.get("type")
            if kind:
                node_fields[kind].update(value)
                for key in ("op", "name", "lhs"):
                    if isinstance(value.get(key), str):
                        symbols[key].add(value[key])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    for rows in native["tables"].values():
        for row in rows:
            visit(row.get("engine_ast", {}))
    constants = (root / constants_path).read_text(encoding="utf-8")
    fields_text = constants.split("export const ALL_FIELDS = [", 1)[1].split("];", 1)[0]
    fields = re.findall(r'"([^"\n]+)"', fields_text)
    result = {"version": "gakumas-mechanism-compiler/1",
              "sources": {path: hashlib.sha256((root/path).read_bytes()).hexdigest()
                          for path in (produce_path, exam_path, native_path, constants_path)},
              "native_state_fields": fields,
              "native_node_fields": {key: sorted(value) for key, value in node_fields.items()},
              "native_symbols": {key: sorted(value) for key, value in symbols.items()},
              "produce": {row["raw_type"]: {"family": row["family"], "operation": row["operation"],
                          "target": row["target"], "fields": row["required_master_fields"]}
                          for row in produce["entries"]},
              "exam": {row["raw_type"]: {**row["canonical_proposal"], "fields": row["all_source_fields"]}
                       for row in exam["entries"]}}
    return result


if __name__ == "__main__":
    output = Path(__file__).with_name("semantic_manifest.json")
    output.write_text(json.dumps(build(Path.cwd()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
