"""实况 JSON 契约：身份、事实、选择和输入事务均显式版本化。"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

CONTRACT_VERSION = "arena-live/1"


class WireModel(BaseModel):
    """拒绝拼错字段、非有限数值及对象顶层修改。"""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ObservedValue(WireModel):
    """当前观察中的事实；未知值只能是 null，估计另存。"""

    value: JsonValue = None
    status: Literal["observed", "unknown"] = "unknown"
    evidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_fact(self) -> Self:
        """已知值必须可追溯，未知值不能伪装成零。"""
        if self.status == "unknown" and self.value is not None:
            raise ValueError("unknown must have a null value")
        if self.status == "observed" and (self.value is None or not self.evidence):
            raise ValueError("observed requires a value and evidence")
        return self


class EntityRef(WireModel):
    """定义、变体和具体副本分开；槽位不属于永久身份。"""

    instance_id: str = Field(min_length=1)
    kind: Literal["card", "drink", "item", "support", "memory", "option"]
    definition_id: str | None = None
    upgrade_count: int | None = Field(default=None, ge=0)
    customize_ids: tuple[str, ...] | None = None
    variant_fingerprint: str | None = None
    label: str = ""
    evidence: tuple[str, ...] = ()


class Inventory(WireModel):
    """只覆盖命名区域；partial/unknown 不能当完整资产集合。"""

    coverage: Literal["complete", "partial", "unknown"]
    entities: tuple[EntityRef, ...] = ()

    @model_validator(mode="after")
    def unique_instances(self) -> Self:
        """同一区域中的两个副本必须使用不同实例 ID。"""
        ids = [entity.instance_id for entity in self.entities]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate inventory instance_id")
        if self.coverage == "unknown" and self.entities:
            raise ValueError("unknown inventory cannot contain entities; use partial")
        return self


class SupportSetup(WireModel):
    """逐槽支援配置，不用统一等级覆盖实测等级。"""

    instance_id: str
    support_card_id: str | None = None
    level: int | None = Field(default=None, ge=1)
    borrowed: bool | None = None


class MemorySetup(WireModel):
    """生成来源与使用限制独立；数值快照不参与初始属性加算。"""

    instance_id: str
    source_idol_card_id: str | None = None
    allowed_character_ids: tuple[str, ...] | None = None
    card: EntityRef | None = None
    acquisition_phase: Literal["ProduceStart", "EndAuditionMid"] | None = None
    ability_ids: tuple[str, ...] | None = None
    ability_levels: tuple[int, ...] | None = None
    contest_snapshot: dict[str, ObservedValue] = Field(default_factory=dict)
    evidence: tuple[str, ...] = ()


class RunLoadout(WireModel):
    """实测编成入口；未读成长等级保留 None，不套训练默认值。"""

    idol_card_id: str | None = None
    producer_level: int | None = Field(default=None, ge=0)
    idol_rank: int | None = Field(default=None, ge=0)
    dearness_level: int | None = Field(default=None, ge=0)
    potential_level: int | None = Field(default=None, ge=0)
    prima_stella_level: int | None = Field(default=None, ge=0)
    use_after_item: bool | None = None
    supports: tuple[SupportSetup, ...] = ()
    supports_complete: bool = False
    memories: tuple[MemorySetup, ...] = ()
    memories_complete: bool = False


class RunSetup(WireModel):
    """初始化仅接受已经结算开场效果的实测 checkpoint。"""

    contract_version: Literal["arena-live/1"] = CONTRACT_VERSION
    run_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    adapter_version: str
    game_version: str | None = None
    masterdata_revision: str | None = None
    rules_revision: str | None = None
    checkpoint_mode: Literal["after_initial_effects"] = "after_initial_effects"
    loadout: RunLoadout = Field(default_factory=RunLoadout)
    execution_constraints: dict[str, JsonValue] = Field(default_factory=dict)


class Choice(WireModel):
    """当前页面的一项语义动作，不接受 UI 坐标或策略槽号。"""

    choice_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    targets: tuple[EntityRef, ...] = ()
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    ui_enabled: bool | None = None
    label: str = ""
    evidence: tuple[str, ...] = ()


class PendingDecision(WireModel):
    """中间页面也是独立决策；每个 Choice 表示一次完整语义输入。"""

    decision_id: str = Field(min_length=1)
    kind: Literal[
        "planning", "exam", "school", "card_reward", "consult", "drink_overflow",
        "search", "discard", "upgrade", "delete", "customize", "event", "result",
    ]
    coverage: Literal["complete", "partial", "unknown"]
    choices: tuple[Choice, ...] = ()

    @model_validator(mode="after")
    def unique_choices(self) -> Self:
        """动作身份只在当前 decision 内使用且不重复。"""
        ids = [choice.choice_id for choice in self.choices]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate choice_id")
        return self


class Observation(WireModel):
    """绝对快照；facts 和 inventories 中未出现的字段在此刻未知。"""

    contract_version: Literal["arena-live/1"] = CONTRACT_VERSION
    run_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    revision: int = Field(ge=0, strict=True)
    captured_at: str
    page: str
    stability: Literal["stable", "transition", "preview"]
    terminal: bool = False
    event_watermark: int = Field(default=0, ge=0, strict=True)
    facts: dict[str, ObservedValue] = Field(default_factory=dict)
    inventories: dict[str, Inventory] = Field(default_factory=dict)
    pending_decision: PendingDecision | None = None
    conflicts: tuple[str, ...] = ()


class Command(WireModel):
    """提案绑定当前运行、观察、修订与目标；由 adapter 临执行前核验。"""

    contract_version: Literal["arena-live/1"] = CONTRACT_VERSION
    command_id: str
    run_id: str
    observation_id: str
    revision: int
    decision_id: str
    choice: Choice


class ObservedEvent(WireModel):
    """对账记录，绝不在绝对快照上再次执行事件中的数值差量。"""

    event_id: str = Field(min_length=1)
    sequence: int = Field(ge=1, strict=True)
    command_id: str
    kind: str
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    evidence: tuple[str, ...] = ()


class ActionResult(WireModel):
    """输入回执；confirmed 表示游戏事实确认，不表示鼠标已点击。"""

    contract_version: Literal["arena-live/1"] = CONTRACT_VERSION
    result_id: str = Field(min_length=1)
    run_id: str
    command_id: str
    observation_id: str
    revision: int
    outcome: Literal["confirmed", "not_applied", "uncertain"]
    evidence: tuple[str, ...] = ()


class SessionReport(WireModel):
    """观察消费结果，包含补读字段和冲突。"""

    status: Literal["ready", "inspect", "wait", "halt"]
    observation_id: str | None = None
    revision: int | None = None
    missing: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()


class Decision(WireModel):
    """策略输出四态：Act / Inspect / Wait / Halt。"""

    kind: Literal["Act", "Inspect", "Wait", "Halt"]
    command: Command | None = None
    missing: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
