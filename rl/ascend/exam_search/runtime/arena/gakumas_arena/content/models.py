"""Versioned, declarative content. JSON/YAML never imports or executes Python."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ContentId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]*/[a-zA-Z0-9_.-]+$")]
Positive = Annotated[int, Field(gt=0, strict=True)]
Nonnegative = Annotated[int, Field(ge=0, strict=True)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Definition(Model):
    id: ContentId
    name: str = ""


class Effect(Definition):
    """An operation and validated arguments; reusable by any effect source."""

    operation: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Growth(Definition):
    effect_type: str
    value: Nonnegative


class Search(Definition):
    zone: Literal["hand", "deck", "deck_grave", "hold", "lost", "not_lost", "playing", "target"]
    card_ids: tuple[str, ...] = ()
    card_kind: Literal["any", "active", "mental", "trouble"] = "any"
    self_only: bool = False


class Trigger(Definition):
    phase: str
    field: str = "ProduceExamFieldStatusType_Unknown"
    value: Nonnegative = 0
    search: str = ""
    every: Positive | None = None


class Passive(Definition):
    trigger: str
    effects: tuple[str, ...] = Field(min_length=1)
    turns: Positive | None = None
    uses: Positive | None = None


class Cost(Model):
    resource: Literal[
        "stamina",
        "penetrate",
        "concentration",
        "good_condition",
        "excellent_condition",
        "good_impression",
        "motivation",
        "full_power",
    ] = "stamina"
    amount: Nonnegative = 0


class EffectUse(Model):
    effect: str
    condition: str


class MovementEffect(Model):
    destination: Literal["hand", "hold"]
    effects: tuple[str, ...] = Field(min_length=1)


class Card(Definition):
    kind: Literal["active", "mental", "trouble"] = "mental"
    plan: Literal["common", "sense", "logic", "anomaly"] = "common"
    rarity: Literal["N", "R", "SR", "SSR"] = "R"
    upgrade: Nonnegative = 0
    cost: Cost = Field(default_factory=Cost)
    condition: str = ""
    effects: tuple[str | EffectUse, ...] = ()
    on_move: MovementEffect | None = None
    after_play: Literal["discard", "exhaust", "hold", "deck_bottom"] = "discard"
    opening: bool = False


class Drink(Definition):
    effects: tuple[str, ...] = Field(min_length=1)


class Item(Definition):
    passives: tuple[str, ...] = Field(min_length=1)


class Condition(Model):
    field: str
    comparison: Literal["ge", "gt", "le", "lt", "eq", "ne"] = "ge"
    value: float


class ScenarioResource(Model):
    initial: float = 0
    minimum: float = 0
    maximum: float | None = None

    @model_validator(mode="after")
    def within_bounds(self):
        if self.initial < self.minimum or (
            self.maximum is not None and self.initial > self.maximum
        ):
            raise ValueError("resource initial value outside bounds")
        return self


class Branch(Model):
    conditions: tuple[Condition, ...] = Field(min_length=1)
    next_node: str


class ResourceCost(Model):
    field: Literal["stamina", "produce_points"]
    amount: Nonnegative


class FlowEffect(Model):
    """Produce effects are shared by events, training, hooks and exam rewards."""

    operation: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Option(Model):
    id: str = Field(min_length=1)
    label: str
    conditions: tuple[Condition, ...] = ()
    costs: tuple[ResourceCost, ...] = ()
    effects: tuple[FlowEffect, ...] = ()
    next_node: str | None = None


class Event(Definition):
    options: tuple[Option, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_options(self):
        if len({o.id for o in self.options}) != len(self.options):
            raise ValueError("duplicate option id")
        return self


class Training(Definition):
    costs: tuple[ResourceCost, ...] = ()
    effects: tuple[FlowEffect, ...] = ()
    conditions: tuple[Condition, ...] = ()
    # With an audition, the lesson is played through ExamRuntime before effects are awarded.
    audition: str | None = None
    failure_effects: tuple[FlowEffect, ...] = ()


class CardCopy(Model):
    card: str
    upgrade: Nonnegative = 0
    copies: Positive = 1


class Audition(Definition):
    """Exact user-authored score-threshold stage, independent of official NPC estimates."""

    turns: Positive
    clear_score: Annotated[float, Field(ge=0)]
    perfect_score: Annotated[float, Field(gt=0)] | None = None
    weights: tuple[float, float, float] = (1, 1, 1)
    colors: tuple[Literal["vocal", "dance", "visual"], ...] = ()
    deck: tuple[CardCopy, ...] = Field(min_length=1)
    drinks: tuple[str, ...] = ()
    items: tuple[str, ...] = ()
    passives: tuple[str, ...] = ()
    starting_stamina: Positive = 30
    max_stamina: Positive = 30
    score_bonus: Annotated[float, Field(ge=0)] = 1
    hand_limit: Positive = 5
    turn_draw: Positive = 3
    plays_per_turn: Positive = 1
    hold_limit: Positive = 2
    hold_overflow: Literal["oldest", "choose"] = "oldest"
    success_effects: tuple[FlowEffect, ...] = ()
    failure_effects: tuple[FlowEffect, ...] = ()

    @model_validator(mode="after")
    def consistent_stage(self):
        if min(self.weights) < 0 or sum(self.weights) <= 0:
            raise ValueError("weights must be nonnegative with a positive sum")
        if self.starting_stamina > self.max_stamina:
            raise ValueError("starting_stamina exceeds max_stamina")
        if self.perfect_score is not None and self.perfect_score < self.clear_score:
            raise ValueError("perfect_score must be >= clear_score")
        if self.colors and len(self.colors) != self.turns:
            raise ValueError("colors must contain exactly one entry per base turn")
        return self


class Node(Model):
    id: str = Field(min_length=1)
    kind: Literal["event", "training", "audition", "effects", "branch", "end"]
    content: str | None = None
    effects: tuple[FlowEffect, ...] = ()
    next_node: str | None = None
    failure_node: str | None = None
    branches: tuple[Branch, ...] = ()

    @model_validator(mode="after")
    def node_shape(self):
        if (self.kind in {"event", "training", "audition"}) != (self.content is not None):
            raise ValueError("event/training/audition nodes require content; other nodes forbid it")
        if self.kind == "end" and (self.next_node or self.failure_node or self.effects):
            raise ValueError("end nodes cannot contain transitions or effects")
        if self.kind != "audition" and self.failure_node is not None:
            raise ValueError("failure_node is only valid on audition nodes")
        if (self.kind == "branch") != bool(self.branches):
            raise ValueError("branches are required only on branch nodes")
        return self


class Scenario(Definition):
    base: str = "produce-001"
    parameter_limit: Positive = 2000
    drink_limit: Positive = 3
    start: str
    nodes: tuple[Node, ...] = Field(min_length=1)
    initial: dict[str, float] = Field(default_factory=dict)
    resources: dict[str, ScenarioResource] = Field(default_factory=dict)
    inventory_mode: Literal["scenario", "audition"] | None = None
    deck: tuple[CardCopy, ...] = ()
    drinks: tuple[str, ...] = ()
    # Ordered reusable effect lists at stable workflow boundaries.
    hooks: dict[Literal["start", "before_node", "after_node", "finish"], tuple[FlowEffect, ...]] = (
        Field(default_factory=dict)
    )


class ContentPack(Model):
    schema_version: Literal["arena-content/1"] = "arena-content/1"
    namespace: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    revision: str = Field(min_length=1)
    synthetic: bool = True
    effects: tuple[Effect, ...] = ()
    growth: tuple[Growth, ...] = ()
    searches: tuple[Search, ...] = ()
    triggers: tuple[Trigger, ...] = ()
    passives: tuple[Passive, ...] = ()
    cards: tuple[Card, ...] = ()
    drinks: tuple[Drink, ...] = ()
    items: tuple[Item, ...] = ()
    events: tuple[Event, ...] = ()
    training: tuple[Training, ...] = ()
    auditions: tuple[Audition, ...] = ()
    scenarios: tuple[Scenario, ...] = ()

    @model_validator(mode="after")
    def unique_namespaced_ids(self):
        for section in (
            "effects",
            "growth",
            "searches",
            "triggers",
            "passives",
            "cards",
            "drinks",
            "items",
            "events",
            "training",
            "auditions",
            "scenarios",
        ):
            seen = set()
            for item in getattr(self, section):
                if not item.id.startswith(self.namespace + "/"):
                    raise ValueError(f"{section}: {item.id} must use namespace {self.namespace}/")
                key = (item.id, item.upgrade) if section == "cards" else item.id
                if key in seen:
                    raise ValueError(f"{section}: duplicate definition {key}")
                seen.add(key)
        return self
