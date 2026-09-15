"""Authored exams share native scoring/cost/turn rules with explicit choice continuations."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, replace

from gakumas_rl.simulation.exam.constants import MOVE_POSITION_MAP
from gakumas_rl.simulation.exam.effects.context import ExamEffectContext
from gakumas_rl.simulation.exam.effects.registry import EXAM_EFFECT_REGISTRY
from gakumas_rl.simulation.exam.replay import ReplayHooks
from gakumas_rl.simulation.exam.runtime import ExamRuntime


class SelectionRequired(Exception):
    def __init__(self, effect, cards, count):
        self.effect, self.cards, self.count = effect, tuple(cards), count


class AuthoredExamRuntime(ExamRuntime):
    """No duplicate rule implementation; only content selection and extension boundaries."""

    def _base_play_limit(self):
        return super()._base_play_limit() + getattr(self, "content_plays_per_turn", 1) - 1

    def _add_card_to_hold(self, card):
        limit = getattr(self, "content_hold_limit", 2)
        if len(self.hold) >= limit and getattr(self, "content_hold_overflow", "oldest") == "choose":
            candidates = [*self.hold, card]
            selected = self.selection_resolver({"id": "content/hold_overflow"}, candidates, 1)
            if selected[0] is card:
                self.grave.append(card)
                return
            self.hold.remove(selected[0])
            self.grave.append(selected[0])
        self.hold.append(card)
        while len(self.hold) > limit:
            self.grave.append(self.hold.pop(0))
        self._apply_card_move_effects(card, "hold")

    def _apply_exam_effect(self, effect, source):
        kind = effect.get("effectType", "")
        if kind in {
            "ProduceExamEffectType_ExamForcePlayCardSearch",
            "ProduceExamEffectType_ExamForcePlayCardSearchWithCost",
        }:
            search = self.card_searches.first(effect.get("produceCardSearchId", ""))
            if search is None:
                raise ValueError("unknown forced-play search")
            bound = self.resolving_enchant_card
            candidates = [
                c
                for c in self._pool_for_search(search, bound or self.current_card, bound or self.current_card)
                if self._matches_card_search(c, search)
            ]
            pay = kind.endswith("WithCost")
            if pay:
                candidates = [
                    c for c in candidates if ExamEffectContext(self).card_cost_affordable(c)
                ]
            selected = self._select_targets(effect, candidates)
            for card in selected:
                ExamEffectContext(self).force_play_card(card, pay_cost=pay, source=source)
                if self.terminated:
                    break
            return
        handler = self.repository.content_handlers.get(kind) or EXAM_EFFECT_REGISTRY.resolve(kind)
        if handler is None:
            raise ValueError(f"unsupported effectType: {kind}")
        handler(ExamEffectContext(self), effect, source)

    def _build_battle_profile(self, row):
        profile = super()._build_battle_profile(row)
        config = self.repository.battle_config_map.get(row["produceExamBattleConfigId"], {})
        weights = [config[c] for c in ("vocal", "dance", "visual")]
        for color, weight in zip(("vocal", "dance", "visual"), weights):
            profile[color + "_weight"] = weight / sum(weights)
        return profile

    def _apply_card_operation(self, effect):
        if effect.get("effectType") != "ProduceExamEffectType_ExamCardMove":
            return super()._apply_card_operation(effect)
        search = self.card_searches.first(effect.get("produceCardSearchId", ""))
        if search is None:
            raise ValueError("unknown card search")
        candidates = [
            c
            for c in self._pool_for_search(search, self.current_card, self.current_card)
            if self._matches_card_search(c, search)
        ]
        selected = self._select_targets(effect, candidates)
        destination = MOVE_POSITION_MAP[effect["movePositionType"]]
        for card in selected:
            self._move_runtime_card(card, destination)

    def _select_targets(self, effect, candidates):
        mode = effect.get("pickRangeType")
        count = min(self._effect_pick_limit(effect) or len(candidates), len(candidates))
        if mode == "ProducePickRangeType_Select" and count:
            selected = self.selection_resolver(effect, candidates, count)
        elif mode == "ProducePickRangeType_Random" and count:
            indices = self.np_random.choice(len(candidates), size=count, replace=False)
            selected = [candidates[int(i)] for i in indices]
        elif mode == "ProducePickRangeType_All":
            selected = candidates
        elif not candidates:
            selected = []
        else:
            raise ValueError("unsupported target selection mode")
        return selected


def action_key(action):
    return {
        "card": f"card:{action.payload.get('uid')}",
        "drink": f"drink:{action.payload.get('index')}",
    }.get(action.kind, action.kind)


class ContentExam:
    """Offline simulator. Replay a suspended action from its exact pre-action checkpoint.

    No external side effects occur during replay. The checkpoint includes RNG, source instances,
    all counters and effects. Chosen UID sequences replace only explicit selection boundaries.
    This class never accepts or executes live game commands.
    """

    def __init__(
        self,
        content,
        audition_id: str,
        *,
        seed: int = 0,
        deck=None,
        drinks=None,
        stamina=None,
        max_stamina=None,
    ):
        self.content, self.seed = content, seed
        self.spec = next(a for a in content.pack.auditions if a.id == audition_id)
        self._overrides = copy.deepcopy(
            {"deck": deck, "drinks": drinks, "stamina": stamina, "max_stamina": max_stamina}
        )
        repo = content.repository
        base = repo.build_scenario("produce-001")
        scenario = replace(
            base,
            scenario_id=audition_id,
            route_type="authored",
            hif=None,
            audition_sequence=(audition_id,),
            default_stage=audition_id,
            exam_turns=self.spec.turns,
            score_weights=self.spec.weights,
        )
        initial = expand_deck(content, self.spec.deck) if deck is None else copy.deepcopy(deck)
        drink_rows = (
            [repo.produce_drinks.first(d) for d in self.spec.drinks] if drinks is None else drinks
        )
        passives = [(pid, f"stage:{i}") for i, pid in enumerate(self.spec.passives)]
        enchant_specs = []
        for i, item_id in enumerate(self.spec.items):
            item = next((item for item in content.pack.items if item.id == item_id), None)
            if item is not None:
                passives.extend((pid, f"item:{i}:{j}") for j, pid in enumerate(item.passives))
            else:
                from .native import native_item_enchants

                enchant_specs.extend(native_item_enchants(repo, item_id, identity=f"item:{i}"))
        for pid, identity in passives:
            p = next(p for p in content.pack.passives if p.id == pid)
            enchant_specs.append(
                {
                    "enchant_id": pid,
                    "effect_turn": p.turns,
                    "effect_count": p.uses,
                    "source": "produce_item" if identity.startswith("item:") else "content",
                    "source_identity": identity,
                }
            )
        self.runtime = AuthoredExamRuntime(
            repo,
            scenario,
            seed=seed,
            stage_type=audition_id,
            audition_row_id=audition_id,
            battle_kind="exam",
            deck=initial,
            drinks=drink_rows,
            initial_status_enchants=enchant_specs,
            starting_stamina=self.spec.starting_stamina if stamina is None else stamina,
            max_stamina=self.spec.max_stamina if max_stamina is None else max_stamina,
            exam_score_bonus_multiplier=self.spec.score_bonus,
            replay_hooks=ReplayHooks(
                disable_stage_gimmicks=True,
                turn_colors=self.spec.colors,
                score_bonus_percent={
                    c: self.spec.score_bonus * 100 for c in ("vocal", "dance", "visual")
                },
            ),
        )
        self.runtime.selection_resolver = self._resolve
        self.runtime.exam_setting = {
            **self.runtime.exam_setting,
            "handLimit": self.spec.hand_limit,
            "turnStartDistribute": self.spec.turn_draw,
        }
        self.runtime.content_plays_per_turn = self.spec.plays_per_turn
        self.runtime.content_hold_limit = self.spec.hold_limit
        self.runtime.content_hold_overflow = self.spec.hold_overflow
        self.revision = 0
        self.journal = []
        self.pending = None
        self._answers = []
        self._answer_index = 0
        self._action = None
        self._before = self._capture()
        self._execute()

    def _capture(self):
        return copy.deepcopy(
            {
                k: v
                for k, v in vars(self.runtime).items()
                if k not in {"repository", "selection_resolver"}
            }
        )

    def _restore(self):
        repo = self.runtime.repository
        self.runtime.__dict__.clear()
        self.runtime.__dict__.update(copy.deepcopy(self._before))
        self.runtime.repository = repo
        self.runtime.selection_resolver = self._resolve

    def _resolve(self, effect, candidates, count):
        index = self._answer_index
        self._answer_index += 1
        if index >= len(self._answers):
            raise SelectionRequired(effect, candidates, count)
        uids = self._answers[index]
        by_uid = {c.uid: c for c in candidates}
        if len(uids) != count or len(set(uids)) != count or any(u not in by_uid for u in uids):
            raise ValueError("selection changed during deterministic continuation")
        return [by_uid[u] for u in uids]

    def _execute(self):
        self._restore()
        self._answer_index = 0
        self.pending = None
        self._pending_cards = {}
        try:
            if self._action is None:
                self.runtime.reset()
            else:
                self.runtime.step(self._action)
        except SelectionRequired as request:
            self._pending_cards = {c.uid: c for c in request.cards}
            self.pending = {
                "kind": "card_selection",
                "effect_id": request.effect["id"],
                "count": request.count,
                "candidates": [
                    {
                        "id": str(c.uid),
                        "card_id": c.card_id,
                        "upgrade": int(c.base_card.get("upgradeCount", 0)),
                    }
                    for c in request.cards
                ],
            }

    @property
    def complete(self):
        return self.pending is None and self.runtime.terminated

    @property
    def passed(self):
        return self.complete and self.runtime.score >= self.spec.clear_score

    def view(self):
        rt = self.runtime
        return {
            "version": "arena-content-exam/1",
            "visibility": "simulation_full",
            "content_digest": self.content.digest,
            "rules_version": self.content.rules_version,
            "revision": self.revision,
            "turn": rt.turn,
            "max_turns": rt.max_turns,
            "extra_turns": rt.extra_turns,
            "counter_semantics": "arena-exam-counters/1",
            "plays_used": rt.turn_counters["play_count"],
            "plays_remaining": max(0, rt.play_limit - rt.turn_counters["play_count"]),
            "score": rt.score,
            "stamina": rt.stamina,
            "max_stamina": rt.max_stamina,
            "resources": dict(rt.resources),
            "zones": {
                zone: [
                    {
                        "id": str(c.uid),
                        "card_id": c.card_id,
                        "upgrade": c.upgrade_count,
                        "growth": list(c.grow_effect_ids),
                        "status_enchant": c.card_status_enchant_id,
                        "transient_effects": list(c.transient_effect_ids),
                        "transient_triggers": list(c.transient_trigger_ids),
                        "play_count_bonus": c.play_count_bonus,
                    }
                    for c in getattr(rt, zone)
                ]
                for zone in ("hand", "deck", "grave", "lost", "hold", "playing")
            },
            "drinks": [
                {"id": f"drink:{i}", "definition_id": d["id"], "consumed": bool(d.get("_consumed"))}
                for i, d in enumerate(rt.drinks)
            ],
            "enchants": [asdict(e) for e in rt.active_enchants],
            "timed_effects": [
                {
                    "uid": e.uid,
                    "effect_id": e.effect["id"],
                    "remaining_turns": e.remaining_turns,
                    "remaining_count": e.remaining_count,
                    "source": e.source,
                    "applied_turn": e.applied_turn,
                }
                for e in rt.active_effects
            ],
            "scheduled_effects": [asdict(e) for e in rt.scheduled_effects],
            "complete": self.complete,
            "passed": self.passed,
            "pending": copy.deepcopy(self.pending),
            "actions": []
            if self.pending or self.complete
            else [{"id": action_key(a), "label": a.label} for a in rt.legal_actions()],
        }

    def encode(self):
        """Shared native card features + observed/3 passive tensors, with public action mapping.

        This is a feature API, not a new Gym training environment. Multi-select consumers
        must choose the declared count of distinct legal slots before calling choose().
        """
        import numpy as np

        from gakumas_rl.simulation.envs import ActionView, GakumasExamEnv
        from gakumas_rl.simulation.exam.observed_encoding import (
            DEPENDENCIES,
            encode_exam_observation,
            exam_encoder_manifest,
        )

        env = GakumasExamEnv(
            self.content.repository,
            self.runtime.scenario,
            observed_runtime=self.runtime,
            stage_type=self.runtime.stage_type,
            max_hand_cards=max(48, self.spec.hand_limit),
            max_drinks=max(3, len(self.runtime.initial_drinks)),
        )
        env.structural_passives = True
        raw = env._build_observation()
        known = set().union(*DEPENDENCIES.values()) | {
            "exam_stage_type",
            "parameter_buff_multiple_per_turn",
            "score",
            "target_score",
            "exam_enchants",
            "exam_effects",
            "review",
            "aggressive",
            "block",
            "plays_used",
            "plays_remaining",
        }
        mapping = {}
        decision = "exam"
        if self.pending:
            if len(self.pending["candidates"]) > env.max_actions:
                raise ValueError("unsupported content selection encoder capacity")
            raw["action_features"][:] = 0
            raw["action_mask"][:] = 0
            candidates = []
            shared = env._candidate_shared_metrics()
            for i, item in enumerate(self.pending["candidates"]):
                # Preserve boundary targets, including an incoming hold card between zones.
                card = self._pending_cards[int(item["id"])]
                feature = env._card_feature(card, i, True, shared)
                candidates.append(
                    ActionView(item["card_id"], "card_select", feature, {"available": True})
                )
                raw["action_features"][i] = feature
                raw["action_mask"][i] = 1
                mapping[i] = item["id"]
            while len(candidates) < env.max_actions:
                candidates.append(
                    ActionView(
                        "empty", "padding", np.zeros(env.action_feature_dim), {"available": False}
                    )
                )
            env._candidates = candidates
            decision = "search"
        elif not self.complete:
            mapping.update(
                {
                    i: f"card:{c.uid}"
                    for i, c in enumerate(self.runtime.hand)
                    if raw["action_mask"][i]
                }
            )
            mapping.update(
                {
                    env.max_hand_cards + i: f"drink:{i}"
                    for i in range(len(self.runtime.drinks))
                    if raw["action_mask"][env.max_hand_cards + i]
                }
            )
            if raw["action_mask"][-1]:
                mapping[env.max_actions - 1] = "end_turn"
        return {
            "observation": encode_exam_observation(env, known, raw=raw, decision_kind=decision),
            "manifest": exam_encoder_manifest(env),
            "action_ids": mapping,
            "selection_count": self.pending["count"] if self.pending else 0,
            "content_digest": self.content.digest,
            "rules_version": self.content.rules_version,
            "revision": self.revision,
        }

    def act(self, action_id: str, *, revision: int):
        if revision != self.revision:
            raise ValueError("stale exam revision")
        if self.pending or self.complete:
            raise ValueError("exam requires a selection or is complete")
        action = next((a for a in self.runtime.legal_actions() if action_key(a) == action_id), None)
        if action is None:
            raise ValueError("illegal exam action")
        self._before = self._capture()
        self._action, self._answers = action, []
        try:
            self._execute()
        except Exception:
            self._restore()
            raise
        self.journal.append({"action": action_id})
        self.revision += 1
        return self.view()

    def choose(self, ids: list[str], *, revision: int):
        if revision != self.revision or self.pending is None:
            raise ValueError("stale selection or no pending choice")
        available = {c["id"] for c in self.pending["candidates"]}
        if (
            len(ids) != self.pending["count"]
            or len(set(ids)) != len(ids)
            or any(i not in available for i in ids)
        ):
            raise ValueError("invalid selection")
        pending_state, pending = self._capture(), copy.deepcopy(self.pending)
        pending_cards = self._pending_cards
        self._answers.append([int(i) for i in ids])
        try:
            self._execute()
        except Exception:
            self._answers.pop()
            self.runtime.__dict__.update(pending_state)
            self.pending = pending
            self._pending_cards = pending_cards
            raise
        self.journal.append({"selection": list(ids)})
        self.revision += 1
        return self.view()

    def snapshot(self):
        payload = {
            "version": "arena-content-exam-session/1",
            "digest": self.content.digest,
            "audition": self.spec.id,
            "seed": self.seed,
            "overrides": copy.deepcopy(self._overrides),
            "journal": copy.deepcopy(self.journal),
        }
        payload["integrity"] = checksum(payload)
        return payload

    @classmethod
    def restore(cls, content, snapshot):
        data = copy.deepcopy(snapshot)
        integrity = data.pop("integrity", None)
        if (
            integrity != checksum(data)
            or data.get("digest") != content.digest
            or data.get("version") != "arena-content-exam-session/1"
        ):
            raise ValueError("content/version/integrity mismatch")
        result = cls(content, data["audition"], seed=data["seed"], **data["overrides"])
        for entry in data["journal"]:
            if set(entry) == {"action"}:
                result.act(entry["action"], revision=result.revision)
            elif set(entry) == {"selection"}:
                result.choose(entry["selection"], revision=result.revision)
            else:
                raise ValueError("invalid journal entry")
        return result


def checksum(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def expand_deck(content, copies):
    rows = []
    for spec in copies:
        row = next(
            c
            for c in content.repository.produce_cards.all(spec.card)
            if int(c.get("upgradeCount", 0)) == spec.upgrade
        )
        rows.extend(copy.deepcopy(row) for _ in range(spec.copies))
    return rows
