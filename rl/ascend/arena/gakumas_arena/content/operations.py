"""Content operations compile to the existing rule engine, never per-card handlers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import Field

from gakumas_rl.simulation.exam.ids import ExamEffect

from .models import Model, Nonnegative, Positive


class Amount(Model):
    amount: Nonnegative


class Turns(Model):
    turns: Positive


class Count(Model):
    amount: Positive


class Score(Amount):
    hits: Positive = 1


class Modifier(Model):
    permille: Nonnegative
    turns: Positive | None = None


class Reference(Model):
    id: str = Field(min_length=1)


class Delay(Reference):
    turns: Positive


class Move(Model):
    search: str = Field(min_length=1)
    destination: Literal["hand", "discard", "hold", "exhaust", "deck_top", "deck_bottom"]
    mode: Literal["select", "all", "random"] = "select"
    count: Positive = 1


class Grow(Model):
    search: str = Field(min_length=1)
    growth: str = Field(min_length=1)


class Native(Model):
    effect_type: str
    value1: int = Field(default=0, strict=True)
    value2: int = Field(default=0, strict=True)
    count: int = Field(default=0, strict=True)
    turns: int = Field(default=0, strict=True)


class ForcePlay(Model):
    search: str = Field(min_length=1)
    count: Positive = 1
    mode: Literal["select", "random", "all"] = "select"
    pay_cost: bool = False


class CardGrant(Reference):
    upgrade: Nonnegative = 0
    copies: Positive = 1


class CardChoice(Model):
    action: Literal["remove", "upgrade", "duplicate"]
    count: Positive = 1
    optional: bool = False


class RewardChoice(Model):
    cards: tuple[str, ...] = Field(min_length=1)
    optional: bool = True


class ProduceGain(Model):
    field: Literal[
        "vocal",
        "dance",
        "visual",
        "stamina",
        "max_stamina",
        "produce_points",
        "vocal_growth",
        "dance_growth",
        "visual_growth",
    ]
    amount: Nonnegative


class ResourceDelta(Model):
    field: str = Field(pattern=r"^scenario\.[a-z][a-z0-9_]*$")
    delta: float


DESTINATIONS = {
    "hand": "Hand",
    "discard": "Grave",
    "hold": "Hold",
    "exhaust": "Lost",
    "deck_top": "DeckFirst",
    "deck_bottom": "DeckLast",
}
PRODUCE_GAINS = {
    "vocal": "VocalAddition",
    "dance": "DanceAddition",
    "visual": "VisualAddition",
    "stamina": "StaminaRecoverFix",
    "max_stamina": "MaxStaminaAddition",
    "produce_points": "ProducePointAddition",
    "vocal_growth": "VocalGrowthRateAddition",
    "dance_growth": "DanceGrowthRateAddition",
    "visual_growth": "VisualGrowthRateAddition",
}


@dataclass(frozen=True)
class Operation:
    parameters: type[Model]
    compile: Callable[[Any], dict[str, Any]]
    description: str
    references: tuple[tuple[str, str], ...] = ()


class Mechanisms:
    """Explicit host-owned extension registry. No plugin paths in untrusted JSON.

    A new compiler may combine existing primitives without new runtime code. Truly new
    semantics require a handler as well, installed on this registry only.
    """

    def __init__(self):
        self.exam: dict[str, Operation] = {}
        self.handlers: dict[str, Callable] = {}
        self.flow: dict[str, Operation] = {}
        self.flow_handlers: dict[str, Callable] = {}
        self.revision = "arena-mechanisms/1"

    def register_exam(
        self,
        name: str,
        operation: Operation,
        *,
        effect_type: str | None = None,
        handler: Callable | None = None,
    ) -> None:
        if name in self.exam or (effect_type and effect_type in self.handlers):
            raise ValueError(f"mechanism already registered: {name}")
        if (effect_type is None) != (handler is None):
            raise ValueError("effect_type and handler must be supplied together")
        self.exam[name] = operation
        if effect_type:
            self.handlers[effect_type] = handler

    def register_flow(self, name: str, operation: Operation, handler: Callable) -> None:
        if name in self.flow:
            raise ValueError(f"flow mechanism already registered: {name}")
        self.flow[name], self.flow_handlers[name] = operation, handler

    def catalog(self) -> dict:
        return {
            "version": self.revision,
            "exam": {
                name: {
                    "description": op.description,
                    "arguments": op.parameters.model_json_schema(),
                    "references": [list(ref) for ref in op.references],
                }
                for name, op in sorted(self.exam.items())
            },
            "flow": {
                name: {
                    "description": op.description,
                    "arguments": op.parameters.model_json_schema(),
                }
                for name, op in sorted(self.flow.items())
            },
        }


def _value(kind):
    return lambda p: {"effectType": kind, "effectValue1": p.amount}


def _turns(kind):
    return lambda p: {"effectType": kind, "effectTurn": p.turns}


def builtins() -> Mechanisms:
    m = Mechanisms()
    for name, kind in {
        "concentration": ExamEffect.LESSON_BUFF,
        "good_impression": ExamEffect.REVIEW,
        "motivation": ExamEffect.CARD_PLAY_AGGRESSIVE,
        "block": ExamEffect.BLOCK,
        "block_fixed": ExamEffect.BLOCK_FIX,
        "recover_stamina": ExamEffect.STAMINA_RECOVER,
        "damage_stamina": ExamEffect.STAMINA_REDUCE,
        "draw": ExamEffect.CARD_DRAW,
        "extra_turn": ExamEffect.EXTRA_TURN,
        "full_power": ExamEffect.FULL_POWER_POINT,
    }.items():
        schema = Count if name in {"draw", "extra_turn"} else Amount
        m.register_exam(name, Operation(schema, _value(kind), "Add amount using native rules."))
    for name, kind in {
        "good_condition": ExamEffect.PARAMETER_BUFF,
        "excellent_condition": ExamEffect.PARAMETER_BUFF_MULTIPLE_PER_TURN,
        "half_cost": ExamEffect.STAMINA_CONSUMPTION_DOWN,
    }.items():
        m.register_exam(name, Operation(Turns, _turns(kind), "Add duration in turns."))
    m.register_exam(
        "score",
        Operation(
            Score,
            lambda p: {
                "effectType": ExamEffect.LESSON,
                "effectValue1": p.amount,
                "effectCount": p.hits,
            },
            "Native score pipeline; concentration/good condition, hits and rounding are shared.",
        ),
    )
    m.register_exam(
        "extra_action",
        Operation(
            Count,
            lambda p: {"effectType": ExamEffect.PLAYABLE_VALUE_ADD, "effectCount": p.amount},
            "Additional player action windows in this turn.",
        ),
    )
    m.register_exam(
        "score_multiplier",
        Operation(
            Modifier,
            lambda p: {
                "effectType": ExamEffect.LESSON_VALUE_MULTIPLE,
                "effectValue1": p.permille,
                "effectTurn": p.turns if p.turns is not None else -1,
            },
            "Additive bonus, 1000 = +100%.",
        ),
    )
    m.register_exam(
        "passive",
        Operation(
            Reference,
            lambda p: {"effectType": ExamEffect.STATUS_ENCHANT, "produceExamStatusEnchantId": p.id},
            "Install a reusable passive with its declared duration/count.",
            (("id", "passives"),),
        ),
    )
    m.register_exam(
        "delay",
        Operation(
            Delay,
            lambda p: {
                "effectType": ExamEffect.EFFECT_TIMER,
                "chainProduceExamEffectId": p.id,
                "effectValue1": p.turns,
            },
            "Schedule an effect after N turns.",
            (("id", "effects"),),
        ),
    )
    m.register_exam(
        "move_card",
        Operation(
            Move,
            lambda p: {
                "effectType": ExamEffect.CARD_MOVE,
                "produceCardSearchId": p.search,
                "movePositionType": "ProduceCardMovePositionType_" + DESTINATIONS[p.destination],
                "pickRangeType": "ProducePickRangeType_" + p.mode.title(),
                "pickCountType": "ProducePickCountType_Unknown",
                "pickCountMin": 0 if p.mode == "all" else p.count,
                "pickCountMax": 0 if p.mode == "all" else p.count,
            },
            "Select/all/random card movement; selection pauses authored exams.",
            (("search", "searches"),),
        ),
    )
    m.register_exam(
        "grow_card",
        Operation(
            Grow,
            lambda p: {
                "effectType": ExamEffect.ADD_GROW_EFFECT,
                "produceCardSearchId": p.search,
                "produceCardGrowEffectIds": [p.growth],
            },
            "Apply growth to all matching cards.",
            (("search", "searches"), ("growth", "growth")),
        ),
    )
    m.register_exam(
        "force_play",
        Operation(
            ForcePlay,
            lambda p: {
                "effectType": ExamEffect.FORCE_PLAY_CARD_SEARCH_WITH_COST
                if p.pay_cost
                else ExamEffect.FORCE_PLAY_CARD_SEARCH,
                "produceCardSearchId": p.search,
                "pickRangeType": "ProducePickRangeType_" + p.mode.title(),
                "pickCountMin": 0 if p.mode == "all" else p.count,
                "pickCountMax": 0 if p.mode == "all" else p.count,
            },
            "Explicit extra full card use; optionally pay cost, never consume a player action window.",
            (("search", "searches"),),
        ),
    )
    m.register_exam(
        "native_scalar",
        Operation(
            Native,
            lambda p: {
                "effectType": p.effect_type,
                "effectValue1": p.value1,
                "effectValue2": p.value2,
                "effectCount": p.count,
                "effectTurn": p.turns,
            },
            "Advanced scalar native effect. Type and required shape are checked at compile time.",
        ),
    )
    # Flow handlers are deliberately explicit; no eval(), dynamic import or implicit no-op.
    for name, schema, description, references in (
        ("gain", ProduceGain, "Shared ProduceEffect gain; growth amounts use permille.", ()),
        (
            "grant_card",
            CardGrant,
            "Add exact card variants to the produce deck.",
            (("id", "cards"),),
        ),
        (
            "grant_drink",
            Reference,
            "Add a drink; overflow pauses for an explicit discard.",
            (("id", "drinks"),),
        ),
        ("choose_card", CardChoice, "Pause for deck removal/upgrade/duplication.", ()),
        ("card_reward", RewardChoice, "Pause for a configured card reward.", ()),
        (
            "resource",
            ResourceDelta,
            "Adjust a declared scenario resource, clamped to its bounds.",
            (),
        ),
    ):
        m.flow[name] = Operation(
            schema, lambda p: p.model_dump(mode="json"), description, references
        )
    return m
