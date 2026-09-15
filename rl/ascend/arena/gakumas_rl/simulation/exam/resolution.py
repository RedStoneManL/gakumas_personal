"""Shared effect groups, frozen trigger eligibility, and prepared card execution.

2026-09-08 reference R01/R03/R09. Numeric effect values remain live. A group
boundary drains prepared plays; nested resource/movement events resolve inline.
The FIFO tie-break between several prepared cards is provisional (reference U07).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from functools import wraps

from .constants import NEGATIVE_TIMED_EFFECT_TYPES, PHASE_TURN_VALUE
from .ids import ExamEffect

TRIGGER_ORDER_POLICY = "stable_id_lexicographic/1"


def trigger_order_key(enchant):
    """Provisional ordering within one phase, independent of UI/source kind.

    Definition ID and source identity use case-sensitive Unicode lexicographic
    order; numeric instance UID breaks exact ties. Keep this policy separate
    from phase order, effect text order, and prepared-card FIFO execution.
    """
    return enchant.enchant_id, enchant.source_identity or "", enchant.uid


@dataclass
class PreparedPlay:
    card_uid: int
    pay_cost: bool
    source: str = "effect"


@dataclass
class ResolutionState:
    """All additional continuation state is captured together by previews/replay."""

    depth: int = 0
    draining: bool = False
    prepared: deque[PreparedPlay] = field(default_factory=deque)
    encore_registered: set[tuple[int, str]] = field(default_factory=set)
    full_power_ready: bool | None = None
    deferred_full_power_release: bool = False
    return_hold_after_draw: bool = False
    scheduled_source_card_uid: int | None = None
    last_played_card_uid: int | None = None
    negative_order: dict[tuple[str, str], int] = field(default_factory=dict)


def effect_group(method):
    """Drain only after successful completion of the outermost effect group.

    A choice interruption unwinds depth but does not drain. ContentExam restores
    its pre-action checkpoint and replays the exact answers, including this state.
    """

    @wraps(method)
    def grouped(runtime, *args, **kwargs):
        runtime.resolution.depth += 1
        try:
            result = method(runtime, *args, **kwargs)
        finally:
            runtime.resolution.depth -= 1
        if runtime.resolution.depth == 0:
            drain_prepared_plays(runtime)
        return result

    return grouped


def prepare_play(runtime, card, *, pay_cost, source="effect"):
    runtime.resolution.prepared.append(PreparedPlay(card.uid, pay_cost, source))
    runtime._record_event(
        "card_prepared",
        {
            "card_uid": card.uid,
            "pay_cost": pay_cost,
            "source": source,
        },
    )
    if runtime.resolution.depth == 0:
        drain_prepared_plays(runtime)


def drain_prepared_plays(runtime):
    state = runtime.resolution
    if state.draining or state.depth or runtime.terminated:
        return
    state.draining = True
    processed = 0
    try:
        while state.prepared and not runtime.terminated:
            processed += 1
            if processed > 1024:
                raise RuntimeError("unsupported automatic-play chain exceeds 1024 uses")
            request = state.prepared.popleft()
            card = runtime._card_by_uid(request.card_uid)
            if card is None:
                raise RuntimeError(f"prepared card instance disappeared: {request.card_uid}")
            if request.pay_cost:
                from .effects.context import ExamEffectContext

                if not ExamEffectContext(runtime).card_cost_affordable(card):
                    # U04: provisional cancel-at-execution policy, never partial payment.
                    runtime._record_event(
                        "prepared_play_unaffordable",
                        {
                            "card_uid": card.uid,
                            "policy": "cancel_before_payment",
                        },
                    )
                    continue
            body_enabled = runtime._card_play_condition_matches(card)
            previous = (
                runtime.current_card,
                list(runtime.playing),
                runtime._current_play_uid_floor,
            )
            runtime._detach_card(card)
            # Restore the outer card only on success. A nested choice must expose
            # the in-progress card until replay restores the original checkpoint.
            runtime._play_card(
                card,
                pay_cost=request.pay_cost,
                consume_play_window=False,
                body_enabled=body_enabled,
            )
            runtime.current_card, runtime.playing, runtime._current_play_uid_floor = previous
    finally:
        state.draining = False


def collect_phase_batch(
    runtime,
    phase_type,
    phase_value=None,
    acting_card=None,
    effect_types=None,
    status_change_origin=None,
):
    """Evaluate every listener before any selected listener mutates game state."""
    event = {
        "phase_type": phase_type,
        "phase_value": runtime.turn
        if phase_value is None and phase_type in PHASE_TURN_VALUE
        else phase_value,
        "acting_card": acting_card,
        "effect_types": effect_types or [],
        "status_change_origin": runtime._status_change_origin(status_change_origin),
    }
    selected, decisions, grows = [], [], []
    item_keys = set()
    # Deterministic default, not a claim about the game's exact trigger order.
    ordered = sorted(runtime.active_enchants, key=trigger_order_key)
    for enchant in ordered:
        if enchant.uid in runtime._resolving_enchant_uids:
            continue
        if enchant.remaining_count is not None and enchant.remaining_count <= 0:
            continue
        if enchant.once_per_turn and enchant.last_fired_turn == runtime.turn:
            continue
        bound = (
            runtime._card_by_uid(enchant.bound_card_uid)
            if enchant.bound_card_uid is not None
            else None
        )
        if enchant.bound_card_uid is not None and bound is None:
            continue
        trigger = runtime.repository.exam_trigger_map.get(enchant.trigger_id)
        if not trigger or phase_type not in trigger.get("phaseTypes", []):
            continue
        item_key = (enchant.source_identity or enchant.enchant_id, phase_type, event["phase_value"])
        eligible = bool(runtime._trigger_matches(trigger, event, acting_card=acting_card))
        if enchant.source == "produce_item" and item_key in item_keys:
            eligible = False
        decisions.append(
            {"enchant_uid": enchant.uid, "enchant_id": enchant.enchant_id, "eligible": eligible}
        )
        if eligible:
            if enchant.source == "produce_item":
                item_keys.add(item_key)
            selected.append((enchant, bound, tuple(enchant.effect_ids)))
    for card in list(runtime.hand) + list(runtime.hold) + list(runtime.deck) + list(runtime.grave):
        row = (
            runtime.card_status_enchants.first(card.card_status_enchant_id)
            if card.card_status_enchant_id
            else None
        )
        trigger = (
            runtime.repository.exam_trigger_map.get(str(row.get("produceExamTriggerId") or ""))
            if row
            else None
        )
        if trigger and runtime._trigger_matches(
            trigger, event, acting_card=acting_card, target_card=card
        ):
            grows.append((card, row))
    batch_id = len(runtime.event_log) + 1
    runtime._record_event(
        "trigger_batch",
        {
            "batch_id": batch_id,
            "phase": phase_type,
            "phase_value": event["phase_value"],
            "trigger_order_policy": TRIGGER_ORDER_POLICY,
            "decisions": decisions,
            "condition_state": {
                "stamina": runtime.stamina,
                "resources": {k: v for k, v in runtime.resources.items() if v},
            }
            if decisions
            else None,
        },
    )
    return batch_id, phase_type, selected, grows


def clear_negative_states(runtime, kinds=None):
    """Clear the requested number of complete status kinds, newest first."""
    present = {}
    for timed in runtime.active_effects:
        kind = str(timed.effect.get("effectType") or "")
        if kind in NEGATIVE_TIMED_EFFECT_TYPES:
            key = (kind, "")
            present[key] = max(
                present.get(key, -1), timed.uid, runtime.resolution.negative_order.get(key, -1)
            )
    for search_id, count in runtime.forbidden_card_search_ids.items():
        if count > 0:
            key = (ExamEffect.GIMMICK_PLAY_CARD_LIMIT, search_id)
            present[key] = runtime.resolution.negative_order.get(key, -1)
    for kind, amount in (
        (ExamEffect.GIMMICK_SLEEPY, runtime.resources["sleepy"]),
        (ExamEffect.GIMMICK_START_TURN_CARD_DRAW_DOWN, runtime.start_turn_draw_penalty),
    ):
        if amount > 0:
            key = (kind, "")
            present[key] = runtime.resolution.negative_order.get(key, -1)
    ordered = sorted(present, key=lambda key: present[key], reverse=True)
    selected = ordered if kinds is None else ordered[: max(int(kinds), 0)]
    for kind, search_id in selected:
        runtime.active_effects = [
            e for e in runtime.active_effects if e.effect.get("effectType") != kind
        ]
        if kind == ExamEffect.GIMMICK_PLAY_CARD_LIMIT:
            runtime.forbidden_card_search_ids.pop(search_id, None)
        elif kind == ExamEffect.GIMMICK_SLEEPY:
            runtime.resources["sleepy"] = 0.0
        elif kind == ExamEffect.GIMMICK_START_TURN_CARD_DRAW_DOWN:
            runtime.start_turn_draw_penalty = 0
        elif kind == ExamEffect.PANIC:
            runtime.panic_cost_overrides = {}
        runtime.resolution.negative_order.pop((kind, search_id), None)
    runtime._sync_forbidden_search_resources()
    runtime._sync_effect_resources()
    runtime._record_event("negative_status_recovered", {"kinds": [list(key) for key in selected]})


def execute_phase_batch(runtime, batch):
    batch_id, phase_type, selected, grows = batch
    # Reserve use counts before nested events. Eligibility and numeric reads are
    # separate: a subsequent change in resources does not cancel this batch.
    for enchant, _, _ in selected:
        enchant.last_fired_turn = runtime.turn
        if enchant.remaining_count is not None:
            enchant.remaining_count -= 1
    for enchant, bound, effect_ids in selected:
        if runtime.terminated:
            break
        runtime._resolving_enchant_uids.add(enchant.uid)
        runtime._record_event(
            "enchant_triggered",
            {
                "batch_id": batch_id,
                "enchant_id": enchant.enchant_id,
                "trigger_phase": phase_type,
                "effect_ids": list(effect_ids),
                "source": enchant.source,
                "source_identity": enchant.source_identity,
            },
        )
        previous = runtime.resolving_enchant_card
        runtime.resolving_enchant_card = bound
        try:
            for effect_id in effect_ids:
                effect = runtime.repository.exam_effect_map.get(effect_id)
                if effect:
                    runtime._apply_exam_effect(effect, source=f"enchant:{enchant.enchant_id}")
                if runtime.terminated:
                    break
        finally:
            runtime.resolving_enchant_card = previous
            runtime._resolving_enchant_uids.discard(enchant.uid)
    runtime.active_enchants = [
        e for e in runtime.active_enchants if e.remaining_count is None or e.remaining_count > 0
    ]
    for card, row in grows:
        if runtime.terminated:
            break
        runtime._apply_card_status_enchant(card, row)
