"""python -m gakumas_arena.content: author, validate, inspect and run content offline."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from .compiler import ContentError, compile_pack
from .models import ContentPack
from .operations import builtins


def dump(value, output=None):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Arena 内容创作工具；离线运行，无游戏操作")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="创建包含卡牌/事件/训练/试镜/剧本的完整样例")
    init.add_argument("path")
    init.add_argument("--namespace", default="my_pack")
    for name in ("schema", "catalog"):
        sub.add_parser(name).add_argument("--output")
    for name in ("validate", "inspect", "demo", "export"):
        command = sub.add_parser(name)
        command.add_argument("path")
        command.add_argument("--output")
        if name == "inspect":
            command.add_argument(
                "section",
                choices=(
                    "cards",
                    "effects",
                    "triggers",
                    "passives",
                    "growth",
                    "searches",
                    "drinks",
                    "items",
                    "events",
                    "training",
                    "auditions",
                    "scenarios",
                ),
            )
            command.add_argument("id")
        if name == "demo":
            command.add_argument("--scenario")
            command.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.command == "schema":
            dump(ContentPack.model_json_schema(), args.output)
        elif args.command == "catalog":
            dump(builtins().catalog(), args.output)
        elif args.command == "init":
            path = Path(args.path)
            if path.exists():
                raise ValueError("init refuses to overwrite an existing file")
            starter = Path(__file__).with_name("starter.json").read_text(encoding="utf-8")
            # JSON value replacement only; namespace is validated before writing.
            value = json.loads(starter.replace('"starter/', '"' + args.namespace + "/"))
            value["namespace"] = args.namespace
            pack = ContentPack.model_validate(value)
            dump(pack.model_dump(mode="json"), path)
            print(str(path.resolve()))
        else:
            content = compile_pack(args.path)
            if args.command == "validate":
                dump(
                    {
                        "valid": True,
                        "digest": content.digest,
                        "synthetic": content.pack.synthetic,
                        "counts": {
                            name: len(getattr(content.pack, name))
                            for name in (
                                "cards",
                                "effects",
                                "passives",
                                "events",
                                "training",
                                "auditions",
                                "scenarios",
                            )
                        },
                    },
                    args.output,
                )
            elif args.command == "inspect":
                found = [
                    row.model_dump(mode="json")
                    for row in getattr(content.pack, args.section)
                    if row.id == args.id
                ]
                if not found:
                    raise ValueError("definition not found")
                dump(found, args.output)
            elif args.command == "export":
                dump(
                    {
                        "schema_version": "arena-content-compiled/1",
                        "digest": content.digest,
                        "pack": content.pack.model_dump(mode="json"),
                        "tables": content.repository._content_rows,
                    },
                    args.output,
                )
            elif args.command == "demo":
                sid = args.scenario or content.pack.scenarios[0].id
                session = content.create_scenario(sid, seed=args.seed)
                trace = [session.view()]
                # Explicit external demo policy. The runtime never chooses a target itself.
                for _ in range(500):
                    if session.complete:
                        break
                    view = session.view()
                    if view["pending"]:
                        p = view["pending"]
                        choices = [c["id"] for c in p["candidates"] if c.get("enabled", True)]
                        session.choose(choices[: p["count"]], revision=session.revision)
                    elif view["exam"]["pending"]:
                        p = view["exam"]["pending"]
                        session.exam_choose(
                            [c["id"] for c in p["candidates"]][: p["count"]],
                            revision=session.revision,
                        )
                    else:
                        session.exam_act(
                            view["exam"]["actions"][0]["id"], revision=session.revision
                        )
                    trace.append(session.view())
                if not session.complete:
                    raise ValueError("demo exceeded 500 decisions")
                dump(
                    {
                        "synthetic": True,
                        "real_game_verified": False,
                        "trace": trace,
                        "snapshot": session.snapshot(),
                    },
                    args.output,
                )
    except (ContentError, ValidationError, ValueError, KeyError, StopIteration, OSError) as exc:
        if isinstance(exc, ContentError):
            errors = [asdict(i) for i in exc.issues]
        else:
            errors = [{"path": "content", "message": str(exc), "category": "contract"}]
        dump({"valid": False, "issues": errors})
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
