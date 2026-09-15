"""Versioned HIF ending products and ticket-backed regeneration candidates.

Master data defines identities and effects. Server-only lottery distributions
are explicit, replaceable planning parameters; they are never called golden.
Generation uses its own seed and does not advance the produce or exam RNG.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import random
from typing import Mapping

from gakumas_rl.idol_config import apply_card_customizations
from gakumas_rl.loadout import ProduceMemoryCardSpec, ProduceMemorySpec


SCHEMA = "arena-hif-memory-products/1"
PRODUCT_SCHEMA = "arena-hif-memory-product/1"
RULESET = "hif-ending-memory-planning/1"
HIF_GROUP = "produce_group-003"
START = "ProduceMemoryProduceCardPhaseType_ProduceStart"
MID = "ProduceMemoryProduceCardPhaseType_EndAuditionMid"


class MemoryGenerationError(ValueError):
    """Invalid lottery configuration, source state, product, or selection."""


@dataclass(frozen=True)
class MemoryGenerationConfig:
    """Unknown probabilities and slot counts are planning defaults, not data facts.

    A run awards one ordinary memory. ``regeneration_count`` buys additional
    candidates with tickets; selection still awards exactly one product.
    """

    regeneration_count: int = 0
    tickets_available: int = 0
    max_regenerations: int = 3
    ordinary_ability_count: int = 3
    hif_ability_count: int = 1
    contest_card_count: int = 6
    contest_item_count: int = 1
    upgrade_retention_probability: float = 0.5
    customize_retention_probability: float = 0.5
    initial_phase_probability: float = 0.5
    performance_bias: float = 1.0
    include_initial_cards: bool = True
    include_idol_cards: bool = False
    include_support_cards: bool = False
    # Full master ids override default individual weights, including zero.
    card_weights: dict[str, float] = field(default_factory=dict)
    ability_weights: dict[str, float] = field(default_factory=dict)
    ordinary_rarity_weights: dict[str, float] = field(default_factory=lambda: {
        "SkillRarity_R": 4.0, "SkillRarity_Sr": 3.0,
        "SkillRarity_Ssr": 2.0, "SkillRarity_Ur": 1.0})
    event_id: str = ""
    event_expires_at: int | None = None


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _config(value):
    try:
        cfg = value if isinstance(value, MemoryGenerationConfig) else MemoryGenerationConfig(**(value or {}))
    except TypeError as error:
        raise MemoryGenerationError(str(error)) from error
    for name in ("regeneration_count", "tickets_available", "max_regenerations", "ordinary_ability_count",
                 "hif_ability_count", "contest_card_count", "contest_item_count"):
        n = getattr(cfg, name)
        if type(n) is not int or n < 0 or n > 1000:
            raise MemoryGenerationError(f"{name} must be an integer in 0..1000")
    if cfg.regeneration_count > min(cfg.tickets_available, cfg.max_regenerations):
        raise MemoryGenerationError("Regeneration exceeds available tickets or configured per-produce limit")
    for name in ("upgrade_retention_probability", "customize_retention_probability", "initial_phase_probability"):
        n = getattr(cfg, name)
        if isinstance(n, bool) or not isinstance(n, (float, int)) or not math.isfinite(n) or not 0 <= n <= 1:
            raise MemoryGenerationError(f"{name} must be finite and in 0..1")
    if not isinstance(cfg.performance_bias, (int, float)) or not math.isfinite(cfg.performance_bias) or cfg.performance_bias < 0:
        raise MemoryGenerationError("performance_bias must be finite and nonnegative")
    for name in ("card_weights", "ability_weights", "ordinary_rarity_weights"):
        weights = getattr(cfg, name)
        if not isinstance(weights, Mapping):
            raise MemoryGenerationError(f"{name} must be a mapping")
        for key, weight in weights.items():
            if not isinstance(key, str) or isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight < 0:
                raise MemoryGenerationError(f"Invalid {name} weight: {key}")
    for name in ("include_initial_cards", "include_idol_cards", "include_support_cards"):
        if type(getattr(cfg, name)) is not bool:
            raise MemoryGenerationError(f"{name} must be a boolean")
    if cfg.event_expires_at is not None and (type(cfg.event_expires_at) is not int or not cfg.event_id):
        raise MemoryGenerationError("event_expires_at requires an event_id and integer Unix seconds")
    return cfg


def _choose(rng, entries, weights, count, *, replace=False):
    candidates = [(e, float(w)) for e, w in zip(entries, weights) if w > 0]
    if not replace and count > len(candidates):
        raise MemoryGenerationError(f"Requested {count} draws from {len(candidates)} positive-weight candidates")
    if count and not candidates:
        raise MemoryGenerationError("No positive-weight candidates")
    result = []
    for _ in range(count):
        total = sum(w for _, w in candidates)
        if not math.isfinite(total):
            raise MemoryGenerationError("Lottery weight total must be finite")
        draw = rng.random() * total
        chosen = len(candidates) - 1
        for i, (_, weight) in enumerate(candidates):
            draw -= weight
            if draw < 0:
                chosen = i
                break
        result.append(candidates[chosen][0])
        if not replace:
            candidates.pop(chosen)
    return result


def _ability_rows(repository):
    ordinary, exclusive = [], []
    for ability in repository.load_table("MemoryAbility").rows:
        groups = ability.get("produceGroupIds") or []
        if groups and HIF_GROUP not in groups:
            continue
        level = int(ability.get("level") or 1)
        skill = next((s for s in repository.load_table("ProduceSkill").all(ability["skillId"])
                      if int(s.get("level") or 1) == level), None)
        if skill is None:
            raise MemoryGenerationError(f"Missing memory skill: {ability['skillId']}@{level}")
        row = {"id": ability["id"], "level": level, "skill_id": skill["id"],
               "rarity": skill["rarity"], "plan_type": skill.get("planType"),
               "produce_group_ids": list(groups), "unique_activation": bool(ability.get("isUniqueActivation")),
               "evaluation": ability.get("evaluation", 0),
               "effect_ids": [skill[f"produceEffectId{i}"] for i in (1, 2, 3) if skill.get(f"produceEffectId{i}")],
               "source": {"table": "MemoryAbility", "skill_table": "ProduceSkill"}}
        (exclusive if HIF_GROUP in groups else ordinary).append(row)
    return ordinary, exclusive


def _card(repository, row, index):
    card_id = str(row.get("id") or "")
    upgrade = int(row.get("upgradeCount") or 0)
    master = repository.card_row_by_upgrade(card_id, upgrade, fallback_to_canonical=False)
    if master is None:
        raise MemoryGenerationError(f"Invalid final card variant: {card_id}@{upgrade}")
    customs = list(row.get("customizedProduceCardCustomizeIds") or [])
    try:
        apply_card_customizations(repository, master, tuple(customs))
    except (ValueError, KeyError) as error:
        raise MemoryGenerationError(str(error)) from error
    return {"card_id": card_id, "instance_id": row.get("instance_id") or f"final-deck:{index:04d}",
            "upgrade_count": upgrade, "customize_ids": customs, "name": master["name"],
            "rarity": master["rarity"], "plan_type": master["planType"],
            "category": master["category"], "initial_card": bool(master.get("isInitialDeckProduceCard")),
            "origin_idol_card_id": master.get("originIdolCardId", ""),
            "origin_support_card_id": master.get("originSupportCardId", ""),
            "no_deck_duplication": bool(master.get("noDeckDuplication")),
            "source": {"zone": "final_permanent_deck", "deck_index": index,
                       "memory_id": row.get("memory_id", ""), "memory_source": row.get("memory_source", "")},
            # Keep complete final state for audit, independently of lottery retention.
            "source_instance": deepcopy(row)}


def _inherit_card(repository, card, rng, cfg, *, phase=False):
    result = deepcopy(card)
    source_upgrade = card["upgrade_count"]
    if source_upgrade and rng.random() >= cfg.upgrade_retention_probability:
        result["upgrade_count"] = 0
    # A subset must remain a legal sequence; retaining repeated customize IDs
    # means their resulting level, not orphaned references to higher levels.
    retained = []
    if result["upgrade_count"]:
        for customize_id in card["customize_ids"]:
            if rng.random() < cfg.customize_retention_probability:
                retained.append(customize_id)
    result["customize_ids"] = retained
    master = repository.card_row_by_upgrade(card["card_id"], result["upgrade_count"], fallback_to_canonical=False)
    if master is None:
        raise MemoryGenerationError(f"No unupgraded memory variant: {card['card_id']}")
    applied = apply_card_customizations(repository, master, tuple(retained))
    result["name"] = master["name"]
    result["grow_effect_ids"] = list(applied.get("growEffectIds") or [])
    result["retention"] = {"source_upgrade_count": source_upgrade,
                           "source_customize_ids": list(card["customize_ids"]),
                           "model": "configured-retention/v1",
                           "other_source_growth_inherited": False}
    if phase:
        result["phase_type"] = START if rng.random() < cfg.initial_phase_probability else MID
    return result


def _seal(product, index):
    product["content_sha256"] = _digest(product)
    product["candidate_id"] = f"memory:{index:04d}:{product['content_sha256'][:20]}"
    return product


def generate_hif_memory_products(runtime, *, seed=0, config=None):
    """Generate from an accepted terminal state; no mutation and no hidden RNG draw.

    Final candidates may have equal contents. Regeneration spends one configured
    ticket per extra candidate; only ``select_memory_candidate`` awards a memory.
    """
    cfg = _config(config)
    if type(seed) is not int:
        raise MemoryGenerationError("Memory generation seed must be an integer")
    if runtime.hif is None or not runtime.final_summary:
        raise MemoryGenerationError("Memory generation requires an accepted HIF terminal summary")
    repository = runtime.repository
    summary = deepcopy(runtime.final_summary)
    summary.pop("memory_products", None)  # May be attached by an export consumer.
    stage = "selection" if runtime.hif.is_selection else "final"
    source = {"produce_id": runtime.scenario.produce_id, "stage": stage,
              "idol_card_id": runtime.idol_loadout.idol_card_id if runtime.idol_loadout else "",
              "final_summary": summary, "parameters": {k: float(runtime.state.get(k) or 0) for k in
                  ("vocal", "dance", "visual", "max_stamina", "star_quality")},
              "event_id": cfg.event_id, "event_expires_at": cfg.event_expires_at}
    batch = {"schema_version": SCHEMA, "ruleset": RULESET, "seed": seed, "source": source,
             "config": asdict(cfg), "candidates": [], "award_count": 0,
             "ticket_ledger": {"available": cfg.tickets_available, "spent": 0, "remaining": cfg.tickets_available},
             "approximations": [], "official_probability_model": False}
    if (getattr(getattr(runtime, "hif_lifecycle", None), "status", None) == "abandoned"
            or summary.get("ending_type") == "abandoned"):
        batch["no_product_reason"] = "produce_abandoned"
        batch["batch_id"] = f"hif-memory-batch:{_digest(batch)[:24]}"
        return json.loads(_json(batch))
    if stage == "selection":
        if cfg.regeneration_count:
            raise MemoryGenerationError("Ordinary-memory regeneration tickets do not apply to selection handoff")
        if not summary.get("route_clear"):
            batch["no_product_reason"] = "selection_not_cleared"
        else:
            payload = asdict(runtime.hif.export_selection_memory())
            # These are excluded explicitly even if old handoff versions stored drinks.
            payload["drink_ids"] = []
            payload.setdefault("metadata", {}).update(event_id=cfg.event_id, event_expires_at=cfg.event_expires_at)
            product = {"schema_version": PRODUCT_SCHEMA, "kind": "hif_selection_handoff",
                       "source": source, "handoff": payload,
                       "legality": {"route_clear_required": True, "usable_produce_ids": ["produce-008"],
                                    "event_id": cfg.event_id, "event_expires_at": cfg.event_expires_at},
                       "excluded_carry": ["produce_points", "drinks", "current_stamina"]}
            batch["candidates"] = [_seal(product, 0)]
            batch["award_count"] = 1
    else:
        _generate_final(runtime, source, cfg, seed, batch)
    batch["batch_id"] = f"hif-memory-batch:{_digest(batch)[:24]}"
    # Dataclass snapshots contain tuples; canonical JSON is also the wire type.
    return json.loads(_json(batch))


def _generate_final(runtime, source, cfg, seed, batch):
    repository = runtime.repository
    rng = random.Random(seed)
    cards = [_card(repository, row, i) for i, row in enumerate(runtime.deck)]
    ordinary, exclusive = _ability_rows(repository)
    all_ability_ids = {a["id"] for a in ordinary + exclusive}
    unknown_abilities = set(cfg.ability_weights) - all_ability_ids
    if unknown_abilities:
        raise MemoryGenerationError(f"Weight references a non-HIF memory ability: {sorted(unknown_abilities)}")
    if set(cfg.card_weights) - {c["card_id"] for c in cards}:
        raise MemoryGenerationError("Card weight references a card absent from the final permanent deck")
    plan = runtime.idol_loadout.stat_profile.plan_type if runtime.idol_loadout else None
    ordinary = [a for a in ordinary if a["plan_type"] in ("ProducePlanType_Common", plan)]
    # HIF exclusive ability targets intentionally ignore PLv, switches and deck.
    inheritable = [c for c in cards if c["category"] != "ProduceCardCategory_Trouble"
                   and (cfg.include_initial_cards or not c["initial_card"])
                   and (cfg.include_idol_cards or not c["origin_idol_card_id"])
                   and (cfg.include_support_cards or not c["origin_support_card_id"])]
    score = float(source["final_summary"].get("produce_result", {}).get("score") or 0)
    grades = sorted([r for r in repository.load_table("ProduceGrade").rows if r["produceGroupId"] == HIF_GROUP],
                    key=lambda r: r["threshold"])
    grade = max((r for r in grades if r["threshold"] <= score), key=lambda r: r["threshold"], default=grades[0])
    quality = min(max(score / max(float(grades[-1]["threshold"]), 1), 0), 1)
    rarity_order = {"SkillRarity_R": 0, "SkillRarity_Sr": 1, "SkillRarity_Ssr": 2, "SkillRarity_Ur": 3}
    stats = source["parameters"]
    def ability_weight(a):
        if a["id"] in cfg.ability_weights:
            return cfg.ability_weights[a["id"]]
        rarity = rarity_order.get(a["rarity"], 0)
        weight = cfg.ordinary_rarity_weights.get(a["rarity"], 1.0) * (1 + cfg.performance_bias * quality * rarity)
        for stat in ("vocal", "dance", "visual"):
            if stat in a["skill_id"]:
                weight *= 1 + cfg.performance_bias * stats[stat] / max(1, *(stats[k] for k in ("vocal", "dance", "visual")))
                break
        return weight
    # Custom P items live in runtime.customize_items and are deliberately absent.
    items = []
    for active in runtime.active_produce_items:
        row = repository.produce_items.first(active.item_id)
        if row is None:
            raise MemoryGenerationError(f"Unknown permanent P item: {active.item_id}")
        items.append({"item_id": active.item_id, "name": row["name"],
                      "source": getattr(active, "source", "produce"), "source_state": asdict(active)})
    batch["pool_audit"] = {"final_card_instances": len(cards), "inheritable_card_instances": len(inheritable),
                           "ordinary_abilities": len(ordinary), "hif_abilities": len(exclusive),
                           "hif_ability_unlock_filter": False, "hif_ability_card_switch_filter": False,
                           "hif_ability_deck_filter": False,
                           "master_semantics_sha256": _digest({"abilities": ordinary + exclusive, "grades": grades})}
    batch["approximations"] = [
        "Server lottery weights and slot counts are configurable planning values.",
        "Ordinary ability rarity/stat bias is configured, not the server performance table.",
        "Card origin eligibility, upgrade/customize retention and acquisition phase probabilities are configured.",
        "Non-custom permanent growth is retained in source evidence but not inherited by the ordinary memory card.",
        "Contest card/item counts and sampling are configured; custom P items are excluded by official rule.",
        "Maximum regeneration count defaults to 3 as a configurable planning limit.",
    ]
    for index in range(cfg.regeneration_count + 1):
        picked = _choose(rng, inheritable, [cfg.card_weights.get(c["card_id"], 1) for c in inheritable],
                         1 if inheritable else 0)
        produce_card = _inherit_card(repository, picked[0], rng, cfg, phase=True) if picked else None
        abilities = _choose(rng, ordinary, [ability_weight(a) for a in ordinary], cfg.ordinary_ability_count)
        abilities += _choose(rng, exclusive, [cfg.ability_weights.get(a["id"], 1) for a in exclusive], cfg.hif_ability_count)
        contest_pool = [c for c in cards if c["category"] != "ProduceCardCategory_Trouble"]
        contest_cards = [_inherit_card(repository, c, rng, cfg) for c in _choose(
            rng, contest_pool, [1] * len(contest_pool), min(cfg.contest_card_count, len(contest_pool)))]
        contest_items = _choose(rng, items, [1] * len(items), min(cfg.contest_item_count, len(items)))
        product = {"schema_version": PRODUCT_SCHEMA, "kind": "hif_final_memory", "source": source,
                   "grade": grade["grade"], "grade_threshold": grade["threshold"],
                   "produce_card": produce_card, "abilities": deepcopy(abilities),
                   "contest": {"parameters": {k: int(stats[k]) for k in ("vocal", "dance", "visual")},
                               "stamina": int(stats["max_stamina"]), "cards": contest_cards,
                               "items": deepcopy(contest_items)},
                   "legality": {"ability_groups_checked": True, "card_variants_checked": True,
                                "allowed_character_ids": [], "generation_source_does_not_restrict_character": True},
                   "generation": {"attempt": index, "regeneration_ticket_cost": int(index > 0),
                                  "ruleset": RULESET, "official_probability_model": False,
                                  "custom_pitems_included": False},
                   "source_deck_instances": deepcopy(cards)}
        validate_memory_product(repository, product)
        batch["candidates"].append(_seal(product, index))
    batch["award_count"] = 1
    batch["ticket_ledger"] = {"available": cfg.tickets_available, "spent": cfg.regeneration_count,
                              "remaining": cfg.tickets_available - cfg.regeneration_count}


def validate_memory_product(repository, product, *, event_id=None, now=None):
    """Validate material identities/customization, and optional event eligibility."""
    if product.get("schema_version") != PRODUCT_SCHEMA:
        raise MemoryGenerationError("Unsupported memory product schema")
    if "content_sha256" in product:
        material = {k: v for k, v in product.items() if k not in ("content_sha256", "candidate_id")}
        if _digest(material) != product["content_sha256"]:
            raise MemoryGenerationError("Memory product content checksum mismatch")
    source = product.get("source", {})
    if product.get("kind") == "hif_selection_handoff":
        if source.get("produce_id") != "produce-007" or not source.get("final_summary", {}).get("route_clear"):
            raise MemoryGenerationError("Selection handoff requires a cleared selection run")
        restriction = product.get("legality", {})
        if event_id is not None and restriction.get("event_id") not in ("", event_id):
            raise MemoryGenerationError("Selection memory belongs to another event")
        expiry = restriction.get("event_expires_at")
        if now is not None and expiry is not None and now >= expiry:
            raise MemoryGenerationError("Event selection memory expired and is no longer usable")
        handoff = product["handoff"]
        if handoff.get("source_produce_id") != "produce-007":
            raise MemoryGenerationError("Invalid selection handoff source")
        for index, row in enumerate(handoff.get("deck_instances") or []):
            _card(repository, row, index)
        return True
    if product.get("kind") != "hif_final_memory" or source.get("produce_id") != "produce-008":
        raise MemoryGenerationError("Ordinary HIF memory requires a final-stage source")
    source_idol = source.get("idol_card_id")
    if source_idol and repository.load_table("IdolCard").first(source_idol) is None:
        raise MemoryGenerationError(f"Unknown source idol: {source_idol}")
    seen = set()
    for ability in product["abilities"]:
        key = (ability["id"], ability["level"])
        if key in seen:
            raise MemoryGenerationError("Duplicate memory ability in one product")
        seen.add(key)
        row = next((a for a in repository.load_table("MemoryAbility").all(key[0]) if int(a["level"]) == key[1]), None)
        if row is None or row.get("produceGroupIds") and HIF_GROUP not in row["produceGroupIds"]:
            raise MemoryGenerationError(f"Invalid HIF memory ability: {key}")
    for card in ([product["produce_card"]] if product.get("produce_card") else []) + product["contest"]["cards"]:
        row = repository.card_row_by_upgrade(card["card_id"], card["upgrade_count"], fallback_to_canonical=False)
        if row is None:
            raise MemoryGenerationError(f"Invalid memory card variant: {card['card_id']}")
        try:
            apply_card_customizations(repository, row, tuple(card["customize_ids"]))
        except (ValueError, KeyError) as error:
            raise MemoryGenerationError(str(error)) from error
        if card.get("phase_type") not in (None, START, MID):
            raise MemoryGenerationError("Invalid memory card acquisition phase")
    for item in product["contest"]["items"]:
        if repository.produce_items.first(item["item_id"]) is None:
            raise MemoryGenerationError(f"Invalid memory P item: {item['item_id']}")
    return True


def filter_memory_candidates(batch, *, card_ids=(), ability_ids=(), excluded_ability_ids=(),
                             minimum_upgrade=0, required_customize_ids=(), kinds=()):
    """Hard filters for RL objectives; no arbitrary scalar 'memory quality' score."""
    if batch.get("schema_version") != SCHEMA:
        raise MemoryGenerationError("Unsupported memory candidate schema")
    result = []
    for product in batch["candidates"]:
        if kinds and product["kind"] not in kinds:
            continue
        card = product.get("produce_card") or {}
        ability_set = {a["id"] for a in product.get("abilities", [])}
        if card_ids and card.get("card_id") not in card_ids:
            continue
        if not set(ability_ids) <= ability_set or set(excluded_ability_ids) & ability_set:
            continue
        if card.get("upgrade_count", 0) < minimum_upgrade or not set(required_customize_ids) <= set(card.get("customize_ids", [])):
            continue
        result.append(deepcopy(product))
    return result


def select_memory_candidate(batch, candidate_id, *, repository=None, event_id=None, now=None):
    """Return a single awarded product and receipt; never award all reroll results."""
    if batch.get("schema_version") != SCHEMA or batch.get("award_count") != 1:
        raise MemoryGenerationError("This batch has no selectable memory")
    matches = [p for p in batch["candidates"] if p["candidate_id"] == candidate_id]
    if len(matches) != 1:
        raise MemoryGenerationError("Select an exact candidate_id from this batch")
    product = deepcopy(matches[0])
    material = {k: v for k, v in product.items() if k not in ("content_sha256", "candidate_id")}
    if _digest(material) != product.get("content_sha256"):
        raise MemoryGenerationError("Memory product content checksum mismatch")
    if repository is not None:
        validate_memory_product(repository, product, event_id=event_id, now=now)
    return {"schema_version": "arena-hif-memory-award/1", "batch_id": batch["batch_id"],
            "selected_candidate_id": candidate_id, "product": product,
            "discarded_candidate_ids": [p["candidate_id"] for p in batch["candidates"] if p["candidate_id"] != candidate_id],
            "ticket_ledger": deepcopy(batch["ticket_ledger"])}


def memory_spec_from_product(repository, product):
    """Lossless produce-relevant export; contest instance details stay in product."""
    validate_memory_product(repository, product)
    if product["kind"] != "hif_final_memory":
        raise MemoryGenerationError("Use selection_memory_from_product for a selection handoff")
    card = product.get("produce_card")
    spec = None if card is None else ProduceMemoryCardSpec(
        card_id=card["card_id"], upgrade_count=card["upgrade_count"],
        customize_ids=tuple(card["customize_ids"]), phase_type=card["phase_type"])
    contest = product["contest"]
    return ProduceMemorySpec(memory_id=product.get("candidate_id", ""),
        idol_card_id=product["source"]["idol_card_id"], grade=product["grade"], produce_card=spec,
        ability_ids=tuple(a["id"] for a in product["abilities"]),
        ability_levels=tuple(a["level"] for a in product["abilities"]),
        **contest["parameters"], stamina=contest["stamina"],
        exam_battle_produce_card_ids=tuple(c["card_id"] for c in contest["cards"]),
        exam_battle_produce_item_ids=tuple(i["item_id"] for i in contest["items"]))


def selection_memory_from_product(repository, product, *, event_id="", now=None):
    from gakumas_rl.simulation.produce.hif import HifSelectionMemory
    validate_memory_product(repository, product, event_id=event_id, now=now)
    if product["kind"] != "hif_selection_handoff":
        raise MemoryGenerationError("Expected a selection handoff")
    return HifSelectionMemory(**deepcopy(product["handoff"]))
