"""Run a golden simulator config or a gktools loadout URL query."""

import argparse
import json
from pathlib import Path

from . import DEFAULT_SEED, find_effects, loadout_from_query, run_exam


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path)
    source.add_argument("--query")
    source.add_argument("--find", help="Find structured effects by a Japanese name or substring")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.find:
        result = find_effects(args.find)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(json.dumps(result, ensure_ascii=True))
        return
    config = (
        json.loads(args.config.read_text(encoding="utf-8"))
        if args.config
        else loadout_from_query(args.query)
    )
    result = run_exam(config, seed=args.seed)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "rules_version": result["rules_version"],
                "score": result["score"],
                "log_entries": len(result["logs"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
