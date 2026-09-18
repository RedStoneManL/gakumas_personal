"""Precompile public native semantics once, before sampling or inference.

This does not launch training or an exam. Compiling a definition does not add it
to a profile's legal card pool. All existing construction masks remain intact.
"""
from __future__ import annotations

import argparse
import copy
import itertools
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from draftrl.native_semantics import NativeSemantics, NativeSemanticsError


def variant_key(card):
    return (int(card["definition_id"]), tuple(sorted((str(k), int(v)) for k, v in card.get("customizations", {}).items())))


def guidance_variants(definition_id, rule):
    """Finite per-card superset of budget-legal guidance states.

    Global P/free-slot limits are intentionally not baked into semantics. They
    continue to be enforced by Guidance.actions; every allowed successor is in
    this per-card closure irrespective of the other cards' allocations.
    """
    maximum = rule["max_guidance"]
    tracks = sorted(rule["tracks"])
    levels = [range(min(rule["tracks"][key]["max"], maximum) + 1) for key in tracks]
    for choice in itertools.product(*levels):
        if sum(choice) <= maximum:
            yield {"definition_id": int(definition_id),
                   "customizations": {key: level for key, level in zip(tracks, choice) if level}, "growth": {}}


_PROGRAM_FIELDS = frozenset({"effects", "actions", "cost", "conditions", "declaration", "program", "dsl"})


def collect_programs(value):
    """Collect explicit DSL declarations, never descriptions or identifiers.

    Catalog card/P-item AST lists are already native programs and need no
    parsing. String declarations in memory/bindings/stage effects are parsed.
    Support patch snippets are included if a future profile contains them.
    """
    found = set()

    def visit(node, path=()):
        if isinstance(node, dict):
            for key, child in node.items():
                if isinstance(child, str) and (
                    key in _PROGRAM_FIELDS or (key in {"old", "new", "before"} and "patches" in path and node.get("op") != "condition")
                ):
                    found.add(child)
                visit(child, path + (key,))
        elif isinstance(node, list):
            for child in node:
                visit(child, path)

    visit(value)
    return sorted(found)


def semantic_requests(catalog, profiles, extra=()):
    """Whole base catalog + all profile variants + explicit fixed/forced cards."""
    cards = {}

    def add(card):
        normalized = {"definition_id": int(card["definition_id"]),
                      "customizations": copy.deepcopy(card.get("customizations", {})), "growth": {}}
        cards[variant_key(normalized)] = normalized

    for definition in catalog["cards"]:
        add({"definition_id": definition["id"]})

    def explicit_cards(value):
        if isinstance(value, dict):
            if "definition_id" in value and "customizations" in value:
                add(value)
            for child in value.values():
                explicit_cards(child)
        elif isinstance(value, list):
            for child in value:
                explicit_cards(child)

    for profile in profiles:
        spec = profile["spec"]
        for definition_id, rule in spec["guidance"]["card_rules"].items():
            for card in guidance_variants(definition_id, rule):
                add(card)
        explicit_cards(profile)
    explicit_cards(extra)
    ordered = [cards[key] for key in sorted(cards)]
    return ordered, collect_programs([catalog, profiles, extra])


def prepare_catalogue(output, *, catalog_path=None, profiles_path=None, node=None, extra_paths=(), rebuild=False):
    catalog_path = Path(catalog_path or HERE / "setup/catalog.json")
    profiles_path = Path(profiles_path or HERE / "setup/profiles.json")
    output = Path(output)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    profiles = json.loads(profiles_path.read_text(encoding="utf-8-sig"))
    extra = [json.loads(Path(path).read_text(encoding="utf-8-sig")) for path in extra_paths]
    cards, programs = semantic_requests(catalog, profiles, extra)
    bridge = NativeSemantics(node=node)
    reused = False
    if output.exists() and not rebuild:
        try:
            bridge.load(output)
            reused = True
        except NativeSemanticsError as error:
            if "version mismatch" not in str(error):
                raise
            # Rebuilding an obsolete cache is an explicit preparation action;
            # hot-path consumers still reject it rather than compiling on miss.
    started = time.monotonic()
    result = bridge.prepare(cards=cards, programs=programs)
    bridge.dump(output)
    return {
        "output": str(output.resolve()), "source_sha256": bridge.version,
        "profiles": [row["id"] for row in profiles], "base_definitions": len(catalog["cards"]),
        "card_variants": len(cards), "dsl_programs": len(programs),
        "native_batches": result["native_calls"], "rng_calls_delta": result["rng_calls_delta"],
        "reused_compatible_cache": reused, "bytes": output.stat().st_size,
        "seconds": round(time.monotonic() - started, 3),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "setup/relational_semantics.json")
    parser.add_argument("--catalog", type=Path, default=HERE / "setup/catalog.json")
    parser.add_argument("--profiles", type=Path, default=HERE / "setup/profiles.json")
    parser.add_argument("--extra", type=Path, action="append", default=[], help="Additional public entries/configs with fixed cards or DSL declarations")
    parser.add_argument("--node", help="Optional Node executable")
    parser.add_argument("--rebuild", action="store_true", help="Ignore an existing semantic cache")
    args = parser.parse_args(argv)
    report = prepare_catalogue(args.output, catalog_path=args.catalog, profiles_path=args.profiles,
                               node=args.node, extra_paths=args.extra, rebuild=args.rebuild)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
