"""Deck presentation independent of the native worker and simulation.

Public entry point: ``write_deck_preview(entry_or_cards, 'deck.html')``.
Original artwork is cached locally and embedded in the HTML by default.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .preview_images import GITHUB_IMAGES, INDEXES, REVISION, cache_images

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "preview_assets"
DATA = ROOT / "_vendor/gakumas_tools/packages/gakumas-data/json"
CDN_IMAGES = "https://gkimg.ris.moe"
TYPES = {"active": "主动", "mental": "精神", "trouble": "麻烦"}
PLANS = {"sense": "Sense", "logic": "Logic", "anomaly": "Anomaly", "free": "通用"}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _table(name: str) -> dict:
    return {r["id"]: r for r in _read(DATA / f"{name}.json")}


def _object(value, path):
    if not isinstance(value, dict):
        raise TypeError(f"{path}: expected a JSON object")
    return value


def _integer(value, path):
    if type(value) is not int or value < 1:
        raise ValueError(f"{path}: expected a positive golden definition ID")
    return value


def deck_preview_data(
    entry_or_cards: dict | list,
    *,
    title: str = "我的卡组",
    idol_id: int | None = None,
    image_source: str = "local",
    cache_dir: str | Path | None = None,
    allow_download: bool = True,
) -> dict:
    """Return a JSON-compatible view model, preserving input order and copies.

    Accept an Arena entry with ``cards`` or a list of integer golden IDs / card
    instance dictionaries. ``idol_id`` is a golden P-idol ID (e.g. 140), not a
    character ID. Unknown definitions remain visible placeholders; this is not
    gameplay validation. Input is never mutated or used to initialize an exam.
    """
    if image_source not in {"local", "github", "gktools_cdn"}:
        raise ValueError("image_source: expected local, github or gktools_cdn")
    if not isinstance(title, str):
        raise TypeError("title: expected a string")
    entry = copy.deepcopy(entry_or_cards if isinstance(entry_or_cards, dict) else {})
    cards = (
        entry.get("cards") if isinstance(entry_or_cards, dict) else copy.deepcopy(entry_or_cards)
    )
    if not isinstance(cards, list):
        raise TypeError("cards: expected an Arena entry with cards, or a list of cards")
    if len(cards) > 4096:
        raise ValueError("cards: preview supports at most 4096 instances")
    # Also rejects non-JSON values and NaN before anything reaches an HTML document.
    json.dumps([entry, cards], allow_nan=False)
    context = _object(entry.get("context", {}), "context")
    resources = _object(entry.get("resources", {}), "resources")
    p_idol_id = idol_id if idol_id is not None else context.get("idol_id")
    if p_idol_id is not None:
        _integer(p_idol_id, "idol_id")
    p_idol = _table("p_idols").get(p_idol_id)
    character_id = p_idol["idolId"] if p_idol else 6  # upstream's default artwork
    character = _table("idols").get(character_id) if p_idol else None
    definitions = _table("skill_cards")
    customizations = _read(DATA / "customizations.json")
    custom_by_key = {key: c for c in customizations for key in (str(c["id"]), c["alias"])}
    indexes = {kind: set(_read(ASSETS / filename)) for kind, filename in INDEXES.items()}
    icon_keys = indexes["skillCards"]

    def urls(kind, key):
        if image_source == "gktools_cdn":
            folder = {"skillCards": "skill_cards", "pItems": "p_items", "pDrinks": "p_drinks"}[kind]
            return f"{CDN_IMAGES}/{folder}/icons/{key}.webp"
        return f"{GITHUB_IMAGES}/{kind}/icons/{key}.png"

    def skill_icon(card_id):
        for key in (f"{card_id}_{character_id}", f"{card_id}_6", str(card_id)):
            if key in icon_keys:
                return urls("skillCards", key)
        return None

    result = []
    for index, raw in enumerate(cards):
        c = {"definition_id": raw} if type(raw) is int else _object(raw, f"cards[{index}]")
        card_id = _integer(c.get("definition_id"), f"cards[{index}].definition_id")
        definition = definitions.get(card_id)
        instance_id = c.get("instance_id", f"entry:{index:03d}")
        if not isinstance(instance_id, str) or not instance_id:
            raise ValueError(f"cards[{index}].instance_id: expected a nonempty string")
        custom = _object(c.get("customizations", {}), f"cards[{index}].customizations")
        growth = _object(c.get("growth", {}), f"cards[{index}].growth")
        bindings = c.get("bindings", [])
        if not isinstance(bindings, list):
            raise TypeError(f"cards[{index}].bindings: expected an array")
        labels = []
        for key, level in custom.items():
            if type(level) is not int or level < 0:
                raise ValueError(
                    f"cards[{index}].customizations.{key}: expected a nonnegative level"
                )
            if level:
                name = custom_by_key.get(str(key), {}).get("name", str(key))
                labels.append({"name": name, "level": level, "key": str(key)})
        result.append(
            {
                "index": index + 1,
                "definition_id": card_id,
                "instance_id": instance_id,
                "name": definition["name"] if definition else f"未知卡牌 #{card_id}",
                "known": definition is not None,
                "rarity": definition["rarity"] if definition else "?",
                "type": definition["type"] if definition else "unknown",
                "type_label": TYPES.get(definition["type"], definition["type"])
                if definition
                else "未知",
                "plan": definition["plan"] if definition else "unknown",
                "upgraded": bool(definition and definition["upgraded"]),
                "icon_url": skill_icon(card_id) if definition else None,
                "customization_labels": labels,
                "growth": growth,
                "bindings": bindings,
                "definition": definition,
                "input": c,
            }
        )
    definition_counts = Counter(c["definition_id"] for c in result)
    instance_counts = Counter(c["instance_id"] for c in result)
    for c in result:
        c["copies"] = definition_counts[c["definition_id"]]
        c["duplicate_instance_id"] = instance_counts[c["instance_id"]] > 1

    def accessories(ids, table, kind):
        if not isinstance(ids, list):
            raise TypeError(f"{table}: expected a list of golden IDs")
        records = _table(table)
        found = []
        for i, raw in enumerate(ids):
            key = _integer(raw, f"{table}[{i}]")
            d = records.get(key)
            found.append(
                {
                    "id": key,
                    "name": d["name"] if d else f"未知 #{key}",
                    "icon_url": urls(kind, key) if d and str(key) in indexes[kind] else None,
                }
            )
        return found

    source_files = [
        DATA / f"{n}.json"
        for n in ("skill_cards", "customizations", "p_idols", "idols", "p_items", "p_drinks")
    ]
    source_files.extend(ASSETS / filename for filename in INDEXES.values())
    model = {
        "schema_version": "arena-deck-preview/1",
        "title": title,
        "preset": entry.get("preset"),
        "boundary": context.get("boundary"),
        "idol": {
            "p_idol_id": p_idol_id,
            "character_id": character_id if p_idol else None,
            "name": character["name"] if character else None,
            "title": p_idol["title"] if p_idol else None,
        },
        "plan": PLANS.get(context.get("plan"), context.get("plan")),
        "resources": resources,
        "scoring": context.get("scoring"),
        "cards": result,
        "p_items": accessories(entry.get("p_items", []), "p_items", "pItems"),
        "drinks": accessories(resources.get("drinks", []), "p_drinks", "pDrinks"),
        "summary": {
            "cards": len(result),
            "definitions": len(definition_counts),
            "upgraded": sum(c["upgraded"] for c in result),
            "customized": sum(bool(c["customization_labels"]) for c in result),
            "unknown": sum(not c["known"] for c in result),
            "missing_icons": sum(c["icon_url"] is None for c in result),
            "duplicate_instance_ids": sum(n > 1 for n in instance_counts.values()),
        },
        "source": {
            "repository": "https://github.com/surisuririsu/gakumas-tools",
            "revision": REVISION,
            "image_source": image_source,
            "files_sha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files
            },
        },
    }
    if image_source == "local":
        entities = model["cards"] + model["p_items"] + model["drinks"]
        urls_to_names = {
            c["icon_url"]: c["icon_url"][len(GITHUB_IMAGES) + 1 :]
            for c in entities
            if c["icon_url"]
        }
        cached = cache_images(
            urls_to_names.values(), cache_dir=cache_dir, allow_download=allow_download
        )
        encoded = {
            name: "data:image/png;base64,"
            + base64.b64encode(Path(info["path"]).read_bytes()).decode("ascii")
            for name, info in cached["images"].items()
        }
        for entity in entities:
            url = entity["icon_url"]
            if url:
                name = urls_to_names[url]
                entity["icon_source_url"] = url
                entity["icon_sha256"] = cached["images"].get(name, {}).get("sha256")
                entity["icon_url"] = encoded.get(name)
        model["summary"]["missing_icons"] = sum(c["icon_url"] is None for c in model["cards"])
        model["source"]["local_images"] = cached["summary"]
        model["source"]["image_errors"] = cached["errors"]
    return model


def render_deck_html(entry_or_cards: dict | list, **options: Any) -> str:
    """Render a standalone interactive HTML string; options match deck_preview_data."""
    model = deck_preview_data(entry_or_cards, **options)
    payload = json.dumps(model, ensure_ascii=False, allow_nan=False)
    # Script raw-text closing tags must never be constructible from input strings.
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    template = (ASSETS / "deck.html").read_text(encoding="utf-8")
    return template.replace("__DECK_TITLE__", html.escape(model["title"], quote=True)).replace(
        "__DECK_DATA__", payload
    )


def write_deck_preview(entry_or_cards: dict | list, output: str | Path, **options: Any) -> Path:
    """Write standalone HTML and return its absolute path. Does not open a browser."""
    document = render_deck_html(entry_or_cards, **options)
    path = Path(output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="将 Arena 入场 JSON 或卡牌数组渲染为图标卡组")
    parser.add_argument("input", type=Path, help="UTF-8 JSON: Arena entry or cards array")
    parser.add_argument("-o", "--output", required=True, type=Path, help="output HTML file")
    parser.add_argument("--title", default="我的卡组")
    parser.add_argument("--idol-id", type=int, help="golden P-idol ID for character artwork")
    parser.add_argument(
        "--image-source", choices=["local", "github", "gktools_cdn"], default="local"
    )
    parser.add_argument("--cache-dir", type=Path, help="shared local image cache root")
    parser.add_argument("--offline", action="store_true", help="use only already cached images")
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        parser.error("input JSON and output HTML must be different files")
    if args.offline and args.image_source != "local":
        parser.error("--offline requires --image-source local")
    try:
        path = write_deck_preview(
            _read(args.input),
            args.output,
            title=args.title,
            idol_id=args.idol_id,
            image_source=args.image_source,
            cache_dir=args.cache_dir,
            allow_download=not args.offline,
        )
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"deck preview: {error}\n")
    print(path)


if __name__ == "__main__":
    main()
