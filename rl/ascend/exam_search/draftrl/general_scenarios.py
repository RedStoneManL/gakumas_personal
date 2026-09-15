"""Public, exogenous research courses for the general deck + exam policy.

This is a deliberately bounded training distribution, not a reconstruction of
every live game mode. Apply ``prepare_memory_mode``, ``scenarios.assign``, then
``augment`` in that order. Pass
one scene index per complete idol x sleep-scenario block (currently 15 games),
and keep that index continuous across training rollouts. Consecutive scenes
pair no HIF memory with optional HIF memory on the same public course. The first
twelve scenes cover both memory modes and every drink capacity, global
multiplier and turn-count family.

Evaluation uses a fixed 216-scene grid and its own fixed public-course RNG;
neither a training counter nor the provided seed changes an evaluation scene.
The seed is used only by the TRAINING public-course sampler, never inserted
into the entry or public task context. The native deck shuffle remains Arena's
independent concern. Full turn order is public, as it is in the user's game.
"""
from __future__ import annotations

import copy
import math
import random
from collections import Counter

from .deck_size import counted_size


SCHEMA = "generalist-public-research-course/3"
COLORS = ("vocal", "dance", "visual")
DRINK_CAPACITIES = (0, 0, 1, 2, 3, 4)
GLOBAL_MULTIPLIERS = (0.5, 1.0, 1.5)
TURN_COUNTS = (9, 10, 12)
COURSE_GRID_SIZE = 108
MEMORY_MODES = ("none", "hif")
EVALUATION_GRID_SIZE = COURSE_GRID_SIZE * len(MEMORY_MODES)
DECK_MIN = 18
DECK_MAX = 25
QUOTAS = {
    9: {"balanced": (4, 3, 2), "concentrated": (5, 2, 2)},
    10: {"balanced": (4, 3, 3), "concentrated": (5, 3, 2)},
    12: {"balanced": (5, 4, 3), "concentrated": (6, 3, 3)},
}
_EVAL_RELATIVE = (
    (1.0, 1.0, 1.0),
    (1.1, 1.0, 0.9),
    (0.9, 1.0, 1.1),
    (0.95, 1.1, 0.95),
    (1.05, 0.9, 1.05),
)


def prepare_memory_mode(profile_entry, spec, scene_index):
    """Apply the exogenous memory rule BEFORE mandatory-card coverage.

    This only switches HIF ``memory_abilities``. Native card effects, idol
    P-items, persistent effects and all card candidates remain untouched.
    Empty abilities in the none branch also prevent the coverage scheduler
    from injecting a memory trigger card. A legal ordinary card can still be
    selected there, including cards whose native effects remove sleepiness.
    Always call with a fresh base profile; a disabled pool cannot be restored.
    """
    if not isinstance(scene_index, int) or isinstance(scene_index, bool) or scene_index < 0:
        raise ValueError("scene index must be a nonnegative integer")
    entry, result_spec = copy.deepcopy(profile_entry), copy.deepcopy(spec)
    mode = MEMORY_MODES[scene_index % len(MEMORY_MODES)]
    memory = result_spec.setdefault("memory", {})
    if mode == "none":
        entry["memory_abilities"] = []
        memory.update(capacity=0, abilities=[])
    else:
        if not memory.get("abilities"):
            raise ValueError("hif memory mode requires the original legal ability pool")
        memory["capacity"] = 4
        entry.setdefault("memory_abilities", [])
    result_spec["memory_mode"] = mode
    return entry, result_spec, {"memory_mode": mode, "memory_capacity": memory["capacity"]}


def _priority(context):
    """Course role comes from the base task, never from a perturbed outcome."""
    stage = context["stage"]
    explicit = context.get("attribute_priority")
    if explicit is not None:
        if len(explicit) != 3 or set(explicit) != set(COLORS):
            raise ValueError("attribute_priority must contain all three colors once")
        return tuple(explicit)
    counts = stage["turnCounts"]
    criteria = stage.get("criteria", {})
    values = context["scoring"]["values"]
    by_color = dict(zip(COLORS, values))
    return tuple(sorted(COLORS, key=lambda c: (
        -counts.get(c, 0), -criteria.get(c, 0), -by_color[c], COLORS.index(c))))


def _relative_factors(base_by_rank, raw):
    """Keep multiplier mean fixed while modestly perturbing the color ratio.

    The weighted mean is one, so only ``GLOBAL_MULTIPLIERS`` changes the overall
    scale by design. A near-tied base profile can need a smaller perturbation to
    retain its declared color priority. All resulting factors stay in [0.8,1.2].
    Percent rounding is still performed by this adapter and may introduce a
    sub-percentage rounding difference; exact score invariance is not claimed.
    """
    total = sum(base_by_rank)
    for amount in (1.0, 0.5, 0.25, 0.125, 0.0):
        weights = [1.0 + amount * (v - 1.0) for v in raw]
        mean = sum(v * w for v, w in zip(base_by_rank, weights)) / total
        factors = [w / mean for w in weights]
        values = [v * f for v, f in zip(base_by_rank, factors)]
        if (all(0.8 <= f <= 1.2 for f in factors)
                and values[0] >= values[1] >= values[2]):
            return factors
    raise ValueError("base scoring values contradict the declared color priority")


def augment(profile_entry, spec, index, seed, training=True):
    """Return a fresh ``(entry, spec, metadata)`` without changing card legality.

    Call after existing mandatory-sleep/card-coverage assignment, because those
    cards must count toward the public 18--25 slot bounds. Prima exemptions,
    candidates, plan restrictions, unique/Switch rules and guidance resources
    are copied unchanged. This sampler does not choose cards or drinks itself.

    The runner must use ``metadata['capacity']`` for drink masking and skip the
    drink-selection phase entirely when it is zero. It must multiply the base
    profile score scale by ``metadata['score_normalizer_multiplier']``. Encode
    ``spec['generalist_task']`` in the wrapper's policy-only global node, without
    adding keys to Arena's strictly validated entry context. Exam observations
    already expose actual scoring, turn order, held drinks and legal actions.
    Diagnostic IDs are intentionally not policy
    input; all meaningful constraints and the resolved turn order are public.
    """
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise ValueError("scene index must be a nonnegative integer")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    entry, result_spec = copy.deepcopy(profile_entry), copy.deepcopy(spec)
    memory_mode = MEMORY_MODES[index % len(MEMORY_MODES)]
    memory_capacity = 0 if memory_mode == "none" else 4
    if result_spec.get("memory_mode") != memory_mode:
        raise ValueError("call prepare_memory_mode before scenarios.assign and augment")
    memory = result_spec.get("memory", {})
    if memory.get("capacity") != memory_capacity:
        raise ValueError("memory capacity contradicts the exogenous memory mode")
    if memory_mode == "none" and (memory.get("abilities") or entry.get("memory_abilities")):
        raise ValueError("none memory mode cannot contain HIF abilities")
    context = entry["context"]
    if context["scoring"].get("mode") != "percent":
        raise ValueError("research courses require explicit percent scoring")
    base_values = context["scoring"]["values"]
    if (len(base_values) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float))
            or not math.isfinite(v) or v <= 0 for v in base_values)):
        raise ValueError("three positive finite base multipliers are required")
    if context["scoring"].get("support_bonus", 0) != 0:
        raise ValueError("a nonzero support bonus needs an explicit normalization contract")
    if entry["resources"]["drinks"]:
        raise ValueError("augment must precede drink selection; no fixed drinks are discarded")

    scene_grid_index = index if training else index % EVALUATION_GRID_SIZE
    grid_index = scene_grid_index // len(MEMORY_MODES)
    capacity = DRINK_CAPACITIES[grid_index % len(DRINK_CAPACITIES)]
    multiplier = GLOBAL_MULTIPLIERS[(grid_index + grid_index // 6) % 3]
    turn_count = TURN_COUNTS[(2 * grid_index + grid_index // 3
                             + grid_index // 6 + grid_index // 18) % 3]
    quota_family = ("balanced", "concentrated")[(grid_index // 2) % 2]
    priority = _priority(context)
    base_by_rank = [base_values[COLORS.index(c)] for c in priority]
    rng = random.Random((seed + 971000003) if training else (671000003 + grid_index))
    raw_relative = ([rng.uniform(0.9, 1.1) for _ in COLORS] if training else
                    _EVAL_RELATIVE[grid_index % len(_EVAL_RELATIVE)])
    factors_by_rank = _relative_factors(base_by_rank, raw_relative)
    relative = dict(zip(priority, factors_by_rank))
    actual_values = [max(1, round(v * multiplier * relative[c]))
                     for c, v in zip(COLORS, base_values)]

    quotas = dict(zip(priority, QUOTAS[turn_count][quota_family]))
    # Research family: primary or secondary first, then a shuffled legal middle.
    # The last three colors retain third -> secondary -> primary. No hidden
    # draw order is generated here, and no future-color information is withheld.
    first = priority[1] if rng.random() < 0.15 else priority[0]
    tail = list(reversed(priority))
    remaining = Counter(quotas)
    remaining[first] -= 1
    remaining.subtract(tail)
    if any(v < 0 for v in remaining.values()):
        raise ValueError("turn quota cannot support the fixed opening and tail")
    middle = [c for c in COLORS for _ in range(remaining[c])]
    rng.shuffle(middle)
    turn_types = [first, *middle, *tail]

    stage = context["stage"]
    stage["turnCounts"] = quotas
    stage["firstTurns"] = {c: float(c == first) for c in COLORS}
    stage["linkTurnCounts"] = []
    context["turn_types"] = turn_types
    context["scoring"]["values"] = actual_values
    counted_fixed = counted_size(entry["cards"], result_spec)
    if counted_fixed > DECK_MIN:
        raise ValueError("mandatory counted cards already exceed the smallest research deck")
    result_spec.update(min_cards=DECK_MIN, max_cards=DECK_MAX,
                       min_free_slots=DECK_MIN - counted_fixed,
                       max_free_slots=DECK_MAX - counted_fixed,
                       fixed_cards=copy.deepcopy(entry["cards"]),
                       drink_capacity=capacity)
    public_context = {
        "objective": "maximize_exam_score",
        "counted_deck_min": DECK_MIN,
        "counted_deck_max": DECK_MAX,
        "drink_capacity": capacity,
        "memory_mode": memory_mode,
        "memory_capacity": memory_capacity,
        "attribute_priority": list(priority),
        "base_turn_count": turn_count,
        "turn_counts": dict(quotas),
        "turn_types": list(turn_types),
        "score_percents": list(actual_values),
        "prima_stella_counts_toward_deck_bound": False,
        "prima_stella_available": False,
        "support_card_limit": result_spec['support_card_limit'],
        "support_cards_count_toward_deck_bound": True,
    }
    result_spec["generalist_task"] = copy.deepcopy(public_context)
    entry.setdefault("source", {}).update(kind="constrained_curriculum", family=SCHEMA)
    metadata = {
        "schema": SCHEMA,
        "course_id": f"research-{turn_count}t-{quota_family}-x{multiplier:g}-drinks{capacity}-memory-{memory_mode}",
        "memory_mode": memory_mode,
        "memory_capacity": memory_capacity,
        "capacity": capacity,
        "drink_capacity": capacity,
        "multiplier_scale": multiplier,
        "score_normalizer_multiplier": multiplier,
        "relative_multiplier_factors": relative,
        "base_score_percents": list(base_values),
        "score_percents": list(actual_values),
        "turn_count": turn_count,
        "quota_family": quota_family,
        "turn_counts": dict(quotas),
        "turn_types": list(turn_types),
        "priority": list(priority),
        "min_cards": DECK_MIN,
        "max_cards": DECK_MAX,
        "counted_fixed_cards": counted_fixed,
        "physical_fixed_cards": len(entry["cards"]),
        "public_context": public_context,
        "distribution_is_live_mode_replica": False,
        "evaluation_grid_index": None if training else scene_grid_index,
    }
    return entry, result_spec, metadata
