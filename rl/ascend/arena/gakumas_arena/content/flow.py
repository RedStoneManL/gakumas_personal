"""Generic authored produce flow: options, exact rewards, training and playable auditions."""

from __future__ import annotations

import copy
import operator
from collections import Counter, deque
from dataclasses import replace

from gakumas_rl.simulation.produce.runtime import ProduceRuntime

from .compiler import INITIAL_FIELDS, produce_gain_row
from .exam import ContentExam, checksum, expand_deck
from .models import FlowEffect

COMPARISONS = {
    "ge": operator.ge,
    "gt": operator.gt,
    "le": operator.le,
    "lt": operator.lt,
    "eq": operator.eq,
    "ne": operator.ne,
}


class ContentSession:
    """Configured flow interpreter reusing ProduceRuntime's resource/reward semantics.

    There is no weekly action sampling or inferred event reward in this entry point.
    All choice boundaries are explicit. Save/restore replays a versioned local journal;
    live transactions continue to use LiveSession, unchanged.
    """

    def __init__(self, content, scenario_id: str, *, seed: int = 0):
        self.content, self.seed = content, seed
        self.spec = next(s for s in content.pack.scenarios if s.id == scenario_id)
        self.nodes = {n.id: n for n in self.spec.nodes}
        self.events = {e.id: e for e in content.pack.events}
        self.training = {t.id: t for t in content.pack.training}
        rules = replace(
            content.repository.build_scenario(self.spec.base),
            hif=None,
            route_type="authored",
            parameter_growth_limit=self.spec.parameter_limit,
            drink_limit=self.spec.drink_limit,
        )
        self.runtime = ProduceRuntime(content.repository, rules, seed=seed)
        self.runtime.state = self.runtime._base_state()
        self.runtime.state.update({k: 0.0 for k in INITIAL_FIELDS})
        self.runtime.state.update(stamina=30.0, max_stamina=30.0)
        self.runtime.state.update(self.spec.initial)
        self.runtime.state.update(
            {key: value.initial for key, value in self.spec.resources.items()}
        )
        if not 0 <= self.runtime.state["stamina"] <= self.runtime.state["max_stamina"]:
            raise ValueError("initial stamina must be within [0, max_stamina]")
        self.runtime.deck = expand_deck(content, self.spec.deck)
        self.runtime.drinks = [
            copy.deepcopy(content.repository.produce_drinks.first(d)) for d in self.spec.drinks
        ]
        self._instance = 0
        for row in self.runtime.deck + self.runtime.drinks:
            self._identify(row)
        self.node = self.spec.start
        self.revision = 0
        self.complete = False
        self.pending = None
        self.exam = None
        self._exam_context = None
        self.journal = []
        self._queue = deque()
        self._queue.extend(self._effects(self.spec.hooks.get("start", ()), "content"))
        self._queue.append({"type": "enter", "node": self.node})
        self._check_drink_overflow()
        self._drain()

    def _identify(self, row):
        self._instance += 1
        row["_content_instance_id"] = f"entity:{self._instance}"

    def _effects(self, effects, source):
        return [
            {"type": "effect", "effect": e.model_dump(mode="json"), "source": source}
            for e in effects
        ]

    def _prepend(self, commands):
        self._queue.extendleft(reversed(commands))

    def _conditions(self, conditions):
        return all(
            COMPARISONS[c.comparison](self.runtime.state[c.field], c.value) for c in conditions
        )

    def _costs(self, costs):
        total = Counter()
        for cost in costs:
            total[cost.field] += cost.amount
        return total

    def _affordable(self, costs):
        return all(self.runtime.state[k] >= amount for k, amount in self._costs(costs).items())

    def _pay(self, costs, source):
        if not self._affordable(costs):
            raise ValueError("insufficient resources")
        for field, amount in self._costs(costs).items():
            kind = {"stamina": "StaminaReduceFix", "produce_points": "ProducePointReduceFix"}[field]
            self.runtime._apply_produce_effect(
                {
                    "produceEffectType": "ProduceEffectType_" + kind,
                    "effectValueMin": amount,
                    "effectValueMax": amount,
                },
                source,
            )

    def _finish_node(self, destination):
        self._prepend(
            self._effects(self.spec.hooks.get("after_node", ()), "content")
            + [{"type": "enter", "node": destination}]
        )

    def _drain(self):
        count = 0
        while self._queue and self.pending is None and self.exam is None and not self.complete:
            count += 1
            if count > 10000:
                raise ValueError("flow exceeded 10000 automatic operations")
            command = self._queue.popleft()
            kind = command["type"]
            if kind == "effect":
                self._effect(FlowEffect.model_validate(command["effect"]), command["source"])
            elif kind == "enter":
                self.node = command["node"]
                node = self.nodes[self.node]
                self._prepend(
                    self._effects(self.spec.hooks.get("before_node", ()), "content")
                    + self._effects(node.effects, "content")
                    + [{"type": "open"}]
                )
            elif kind == "open":
                self._open_node()
            elif kind == "finish":
                self._finish_node(command["node"])
            elif kind == "complete":
                self.complete = True
            else:
                raise ValueError(f"unknown continuation {kind}")

    def _open_node(self):
        node = self.nodes[self.node]
        if node.kind == "end":
            self._prepend(
                self._effects(self.spec.hooks.get("finish", ()), "content") + [{"type": "complete"}]
            )
        elif node.kind == "effects":
            self._finish_node(node.next_node)
        elif node.kind == "branch":
            destination = next(
                (b.next_node for b in node.branches if self._conditions(b.conditions)),
                node.next_node,
            )
            self._finish_node(destination)
        elif node.kind == "event":
            options = self.events[node.content].options
            self.pending = {
                "kind": "event",
                "count": 1,
                "optional": False,
                "candidates": [
                    {
                        "id": o.id,
                        "label": o.label,
                        "enabled": self._conditions(o.conditions) and self._affordable(o.costs),
                    }
                    for o in options
                ],
            }
        elif node.kind == "training":
            training = self.training[node.content]
            self.pending = {
                "kind": "training",
                "count": 1,
                "optional": False,
                "candidates": [
                    {
                        "id": training.id,
                        "label": training.name or training.id,
                        "enabled": self._conditions(training.conditions)
                        and self._affordable(training.costs),
                    }
                ],
            }
        elif node.kind == "audition":
            self._start_exam(node.content, "audition")

    def _start_exam(self, audition_id, context):
        self._exam_context = context
        # An explicit scenario deck is the current persistent deck, including event edits.
        # Without one, the stage's declared deck is used.
        deck = self.runtime.deck if self.uses_scenario_inventory else None
        drinks = self.runtime.drinks if self.uses_scenario_inventory else None
        self.exam = ContentExam(
            self.content,
            audition_id,
            seed=int(self.runtime.np_random.integers(0, 2**31)),
            deck=deck,
            drinks=drinks,
            stamina=self.runtime.state["stamina"],
            max_stamina=self.runtime.state["max_stamina"],
        )
        self._finish_exam_if_complete()

    def _finish_exam_if_complete(self):
        if self.exam is None or not self.exam.complete:
            return
        exam, self.exam = self.exam, None
        self.runtime.state["stamina"] = exam.runtime.stamina
        if self.uses_scenario_inventory:
            self.runtime.drinks = [
                copy.deepcopy(d) for d in exam.runtime.drinks if not d.get("_consumed")
            ]
        node = self.nodes[self.node]
        effects = exam.spec.success_effects if exam.passed else exam.spec.failure_effects
        destination = node.next_node if exam.passed else (node.failure_node or node.next_node)
        if self._exam_context == "training":
            training = self.training[node.content]
            effects = (*effects, *(training.effects if exam.passed else training.failure_effects))
        self._prepend(self._effects(effects, "content") + [{"type": "finish", "node": destination}])

    @property
    def uses_scenario_inventory(self):
        return (
            self.spec.inventory_mode == "scenario"
            if self.spec.inventory_mode
            else bool(self.spec.deck)
        )

    def _effect(self, effect, source):
        op = self.content.mechanisms.flow[effect.operation]
        params = op.parameters.model_validate(effect.arguments)
        values = op.compile(params)
        handler = self.content.mechanisms.flow_handlers.get(effect.operation)
        if handler is not None:
            handler(self, params)
        elif effect.operation == "gain":
            self.runtime._apply_produce_effect(produce_gain_row(values), source)
        elif effect.operation == "grant_card":
            row = self._variant(values["id"], values["upgrade"])
            for _ in range(values["copies"]):
                card = copy.deepcopy(row)
                self._identify(card)
                self.runtime.deck.append(card)
        elif effect.operation == "grant_drink":
            drink = copy.deepcopy(self.content.repository.produce_drinks.first(values["id"]))
            self._identify(drink)
            self.runtime.drinks.append(drink)
            self._check_drink_overflow()
        elif effect.operation == "card_reward":
            self.pending = {
                "kind": "card_reward",
                "count": 1,
                "optional": params.optional,
                "candidates": [
                    {"id": str(i), "card_id": cid, "enabled": True}
                    for i, cid in enumerate(params.cards)
                ],
            }
        elif effect.operation == "choose_card":
            cards = self.runtime.deck
            if params.action == "upgrade":
                cards = [
                    c
                    for c in cards
                    if self._variant(c["id"], int(c.get("upgradeCount", 0)) + 1, required=False)
                ]
            count = min(params.count, len(cards))
            if count:
                self.pending = {
                    "kind": "deck_choice",
                    "action": params.action,
                    "count": count,
                    "optional": params.optional,
                    "candidates": [
                        {"id": c["_content_instance_id"], "card_id": c["id"], "enabled": True}
                        for c in cards
                    ],
                }
        elif effect.operation == "resource":
            spec = self.spec.resources[params.field]
            value = max(self.runtime.state[params.field] + params.delta, spec.minimum)
            if spec.maximum is not None:
                value = min(value, spec.maximum)
            self.runtime.state[params.field] = value
        else:
            raise ValueError(f"unsupported flow operation: {effect.operation}")

    def _variant(self, card_id, upgrade, *, required=True):
        row = next(
            (
                c
                for c in self.content.repository.produce_cards.all(card_id)
                if int(c.get("upgradeCount", 0)) == upgrade
            ),
            None,
        )
        if required and row is None:
            raise ValueError(f"unknown card variant {card_id} +{upgrade}")
        return row

    def _check_drink_overflow(self):
        excess = len(self.runtime.drinks) - self.runtime.scenario.drink_limit
        if excess > 0:
            self.pending = {
                "kind": "drink_overflow",
                "count": excess,
                "optional": False,
                "candidates": [
                    {"id": d["_content_instance_id"], "drink_id": d["id"], "enabled": True}
                    for d in self.runtime.drinks
                ],
            }

    def view(self):
        return {
            "version": "arena-content-flow/1",
            "content_digest": self.content.digest,
            "rules_version": self.content.rules_version,
            "revision": self.revision,
            "node": self.node,
            "complete": self.complete,
            "state": {
                k: self.runtime.state[k]
                for k in sorted(INITIAL_FIELDS | self.spec.resources.keys())
            },
            "deck": [
                {
                    "id": c["_content_instance_id"],
                    "card_id": c["id"],
                    "upgrade": int(c.get("upgradeCount", 0)),
                }
                for c in self.runtime.deck
            ],
            "drinks": [
                {"id": d["_content_instance_id"], "drink_id": d["id"]} for d in self.runtime.drinks
            ],
            "pending": copy.deepcopy(self.pending),
            "exam": self.exam.view() if self.exam else None,
        }

    def choose(self, ids: list[str], *, revision: int):
        if revision != self.revision or self.pending is None:
            raise ValueError("stale revision or no pending flow choice")
        pending = self.pending
        available = {c["id"] for c in pending["candidates"] if c.get("enabled", True)}
        if (len(ids) != pending["count"] and not (not ids and pending["optional"])) or (
            len(set(ids)) != len(ids) or any(i not in available for i in ids)
        ):
            raise ValueError("invalid or disabled choice")
        # Roll back the entire caller operation if a trusted extension or later transition fails.
        before = self.snapshot()
        try:
            self._choose(ids, pending)
            self._drain()
        except Exception:
            restored = self.restore(self.content, before)
            self.__dict__.update(restored.__dict__)
            raise
        self.journal.append({"choice": list(ids)})
        self.revision += 1
        return self.view()

    def _choose(self, ids, pending):
        self.pending = None
        kind = pending["kind"]
        node = self.nodes[self.node]
        if kind == "event":
            option = next(o for o in self.events[node.content].options if o.id == ids[0])
            self._pay(option.costs, "content")
            self._prepend(
                self._effects(option.effects, "content")
                + [{"type": "finish", "node": option.next_node or node.next_node}]
            )
        elif kind == "training":
            training = self.training[node.content]
            self._pay(training.costs, "content")
            if training.audition:
                self._start_exam(training.audition, "training")
            else:
                self._prepend(
                    self._effects(training.effects, "content")
                    + [{"type": "finish", "node": node.next_node}]
                )
        elif kind == "card_reward" and ids:
            choice = next(c for c in pending["candidates"] if c["id"] == ids[0])
            self._effect(
                FlowEffect(operation="grant_card", arguments={"id": choice["card_id"]}), "content"
            )
        elif kind == "deck_choice":
            for uid in ids:
                index = next(
                    i for i, c in enumerate(self.runtime.deck) if c["_content_instance_id"] == uid
                )
                card = self.runtime.deck[index]
                if pending["action"] == "remove":
                    self.runtime.deck.pop(index)
                elif pending["action"] == "upgrade":
                    row = copy.deepcopy(
                        self._variant(card["id"], int(card.get("upgradeCount", 0)) + 1)
                    )
                    row["_content_instance_id"] = uid
                    self.runtime.deck[index] = row
                else:
                    row = copy.deepcopy(card)
                    self._identify(row)
                    self.runtime.deck.append(row)
        elif kind == "drink_overflow":
            self.runtime.drinks = [
                d for d in self.runtime.drinks if d["_content_instance_id"] not in ids
            ]

    def exam_act(self, action_id: str, *, revision: int):
        return self._exam_input({"exam_action": action_id}, revision)

    def exam_choose(self, ids: list[str], *, revision: int):
        return self._exam_input({"exam_selection": list(ids)}, revision)

    def _exam_input(self, entry, revision):
        if revision != self.revision or self.exam is None:
            raise ValueError("stale revision or no active exam")
        before = self.snapshot()
        try:
            if "exam_action" in entry:
                self.exam.act(entry["exam_action"], revision=self.exam.revision)
            else:
                self.exam.choose(entry["exam_selection"], revision=self.exam.revision)
            self._finish_exam_if_complete()
            self._drain()
        except Exception:
            restored = self.restore(self.content, before)
            self.__dict__.update(restored.__dict__)
            raise
        self.journal.append(entry)
        self.revision += 1
        return self.view()

    def snapshot(self):
        payload = {
            "version": "arena-content-session/1",
            "digest": self.content.digest,
            "scenario": self.spec.id,
            "seed": self.seed,
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
            or data.get("version") != "arena-content-session/1"
        ):
            raise ValueError("content/version/integrity mismatch")
        result = cls(content, data["scenario"], seed=data["seed"])
        for entry in data["journal"]:
            if set(entry) == {"choice"}:
                result.choose(entry["choice"], revision=result.revision)
            elif set(entry) == {"exam_action"}:
                result.exam_act(entry["exam_action"], revision=result.revision)
            elif set(entry) == {"exam_selection"}:
                result.exam_choose(entry["exam_selection"], revision=result.revision)
            else:
                raise ValueError("invalid flow journal entry")
        return result
