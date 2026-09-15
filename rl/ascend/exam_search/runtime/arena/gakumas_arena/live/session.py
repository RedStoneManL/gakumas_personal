"""单运行实况事务桥；没有 UI 输入，也不调用 seeded step 推进真实游戏。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import numpy as np

from ..policies.base import Policy
from .contracts import (
    ActionResult,
    Choice,
    Command,
    Decision,
    Observation,
    ObservedEvent,
    RunSetup,
    SessionReport,
)
from .recovery import CommandEntry, ObservationEntry, ResultEntry, SessionSnapshot, ledger_digest


class ProtocolError(ValueError):
    """陈旧输入、身份冲突或事务顺序错误；失败时不消费状态。"""


class MissingFields(ValueError):
    """引擎绑定所需字段尚未齐全。"""

    def __init__(self, *fields: str) -> None:
        """记录供 adapter 补读的精确字段路径。"""
        self.fields = tuple(fields)
        super().__init__(", ".join(fields))


@dataclass
class PreparedDecision:
    """共用 encoder 的输出及动作槽到本次观察语义动作的对应。"""

    env: Any
    observation: dict[str, np.ndarray]
    info: dict[str, Any]
    choices: dict[int, Choice]
    encoder_manifest: dict[str, Any]


class DecisionBackend(Protocol):
    """Arena 侧消费事实、校验游戏合法性和编码；不能自行生成实机候选。"""

    def prepare(self, setup: RunSetup, observation: Observation) -> PreparedDecision:
        """返回策略输入；缺少合法性或编码所需事实则抛 MissingFields。"""
        ...


class LiveSession:
    """内存内一次培育；调用者应持久化 JSON 输入日志用于重建和审计。"""

    def __init__(
        self, policy: Policy, backend: DecisionBackend | None = None,
        *, command_id_factory: Callable[[], str] | None = None,
    ) -> None:
        """绑定现有 Policy；无引擎绑定时只允许观察和补读。"""
        self.policy = policy
        self._command_id_factory = command_id_factory or (lambda: str(uuid4()))
        self.backend = backend
        self.setup: RunSetup | None = None
        self.observation: Observation | None = None
        self._observations: dict[str, Observation] = {}
        self._command: Command | None = None
        self._command_state: str = "idle"
        self._results: dict[str, tuple[Any, ...]] = {}
        self.events: dict[str, ObservedEvent] = {}
        self._event_sequences: dict[int, str] = {}
        self._prepared: PreparedDecision | None = None
        self._ledger = []

    def initialize(self, run_setup: RunSetup, observed_checkpoint: Observation) -> SessionReport:
        """接收已经结算的起点，不 reset 模拟环境或叠加开场效果。"""
        if self.setup is not None:
            raise ProtocolError("session already initialized")
        if run_setup.run_id != observed_checkpoint.run_id:
            raise ProtocolError("run_id mismatch")
        self.setup = run_setup.model_copy(deep=True)
        self.policy.reset()
        return self.observe(observed_checkpoint)

    def _validate_observation(self, observation: Observation) -> bool:
        """验证单调修订与重放身份，返回是否为完全相同的重复观察。"""
        if self.setup is None or observation.run_id != self.setup.run_id:
            raise ProtocolError("run_id mismatch or uninitialized session")
        old = self._observations.get(observation.observation_id)
        if old is not None:
            if old != observation:
                raise ProtocolError("observation_id reused with different content")
            if old != self.observation:
                raise ProtocolError("stale observation")
            return True
        if self.observation is not None:
            if observation.revision <= self.observation.revision:
                raise ProtocolError("stale revision")
            if observation.event_watermark < self.observation.event_watermark:
                raise ProtocolError("event watermark regressed")
        return False

    def observe(self, observation: Observation) -> SessionReport:
        """用新绝对快照替换旧事实；不把旧值或局部列表补成当前真值。"""
        if not self._validate_observation(observation):
            self.observation = observation.model_copy(deep=True)
            self._observations[observation.observation_id] = self.observation
            self._ledger.append(ObservationEntry(observation=self.observation.model_copy(deep=True)))
            self._prepared = None
            if self._command_state == "proposed":
                self._command = None
                self._command_state = "idle"
        return self._report()

    def _report(self) -> SessionReport:
        """先检查事务和可见性，再要求引擎完成规则合法性验证。"""
        current = self.observation
        if current is None:
            return SessionReport(status="inspect", missing=("initialize",))
        common = {"observation_id": current.observation_id, "revision": current.revision}
        if self._command_state == "uncertain":
            return SessionReport(status="inspect", missing=("action_result.resolution",), **common)
        if self._command_state == "submitted":
            return SessionReport(status="wait", **common)
        if current.conflicts:
            return SessionReport(status="inspect", conflicts=current.conflicts, **common)
        if current.terminal:
            return SessionReport(status="halt", **common)
        if current.stability != "stable":
            return SessionReport(status="wait", **common)
        pending = current.pending_decision
        if pending is None:
            return SessionReport(status="inspect", missing=("pending_decision",), **common)
        if pending.coverage != "complete":
            return SessionReport(status="inspect", missing=("pending_decision.coverage",), **common)
        missing = tuple(
            f"choices.{choice.choice_id}.ui_enabled"
            for choice in pending.choices if choice.ui_enabled is None
        )
        if missing:
            return SessionReport(status="inspect", missing=missing, **common)
        if self.backend is None:
            return SessionReport(status="inspect", missing=("arena.engine_binding",), **common)
        if self._prepared is None:
            try:
                prepared = self.backend.prepare(self.setup, current.model_copy(deep=True))
                self._validate_prepared(prepared)
            except MissingFields as exc:
                return SessionReport(status="inspect", missing=exc.fields, **common)
            self._prepared = prepared
        return SessionReport(status="ready", **common)

    def _validate_prepared(self, prepared: PreparedDecision) -> None:
        """双向校验掩码与语义表，禁止 backend 捏造或替换当前目标。"""
        pending = self.observation.pending_decision
        choices = {choice.choice_id: choice for choice in pending.choices}
        mask = np.asarray(prepared.observation["action_mask"])
        if mask.ndim != 1 or not np.isfinite(mask).all():
            raise ProtocolError("invalid action mask")
        if not prepared.encoder_manifest:
            raise ProtocolError("encoder manifest required")
        ids = []
        for index in np.flatnonzero(mask > 0.5):
            choice = prepared.choices.get(int(index))
            if choice is None or choices.get(choice.choice_id) != choice or not choice.ui_enabled:
                raise ProtocolError("engine action does not match an enabled observed choice")
            ids.append(choice.choice_id)
        if len(ids) != len(set(ids)):
            raise ProtocolError("duplicate action mapping")
        if not ids:
            raise MissingFields("arena.legal_actions")

    def decide(self) -> Decision:
        """调用既有 Policy.act，并把瞬时 action index 还原为稳定语义目标。"""
        report = self._report()
        if report.status != "ready":
            return Decision(
                kind={"inspect": "Inspect", "wait": "Wait", "halt": "Halt"}[report.status],
                missing=report.missing, reasons=report.conflicts,
            )
        if self._command_state == "proposed":
            return Decision(kind="Act", command=self._command.model_copy(deep=True))
        prepared = self._prepared
        if prepared.info.get("partial_observation") and not self.policy.supports_partial_observations:
            return Decision(kind="Inspect", missing=("policy.supports_partial_observations",))
        index = int(self.policy.act(prepared.env, prepared.observation, prepared.info))
        mask = prepared.observation["action_mask"]
        if index not in prepared.choices or index < 0 or index >= len(mask) or mask[index] <= 0.5:
            raise ProtocolError("policy selected an illegal action")
        current = self.observation
        command_id = self._command_id_factory()
        if self._command_id_used(command_id):
            raise ProtocolError('command_id already used in this session')
        self._command = Command(
            command_id=command_id, run_id=current.run_id,
            observation_id=current.observation_id, revision=current.revision,
            decision_id=current.pending_decision.decision_id,
            choice=prepared.choices[index].model_copy(deep=True),
        )
        self._command_state = "proposed"
        self._ledger.append(CommandEntry(operation='propose', command=self._command.model_copy(deep=True)))
        return Decision(kind="Act", command=self._command.model_copy(deep=True))

    def _command_id_used(self, command_id: str) -> bool:
        """包含已失效和已完成提案，避免恢复后计数器重启造成歧义。"""
        return any(isinstance(entry, CommandEntry) and entry.operation == 'propose'
                   and entry.command.command_id == command_id for entry in self._ledger)

    def mark_submitted(self, command: Command) -> None:
        """adapter 临输入前调用；过期提案不得提交，同一提交幂等。"""
        if command != self._command:
            raise ProtocolError("unknown or changed command")
        if self._command_state in {"submitted", "uncertain"}:
            return
        if self._command_state != "proposed" or (
            command.observation_id != self.observation.observation_id
            or command.revision != self.observation.revision
        ):
            raise ProtocolError("stale command")
        self._command_state = "submitted"
        self._ledger.append(CommandEntry(operation='submit', command=command.model_copy(deep=True)))

    def accept_result(
        self, action_result: ActionResult, observed_events: tuple[ObservedEvent, ...] = (),
        next_observation: Observation | None = None,
    ) -> SessionReport:
        """原子消费回执；事件仅存证，确认后的绝对快照是唯一状态更新源。"""
        package = (action_result, tuple(observed_events), next_observation)
        existing = self._results.get(action_result.result_id)
        if existing is not None:
            if existing != package:
                raise ProtocolError("result_id reused with different content")
            return self._report()
        command = self._command
        if command is None or self._command_state not in {"submitted", "uncertain"}:
            raise ProtocolError("result requires a submitted command")
        for field in ("command_id", "run_id", "observation_id", "revision"):
            if getattr(action_result, field) != getattr(command, field):
                raise ProtocolError(f"result {field} mismatch")
        if action_result.outcome != "uncertain":
            if not action_result.evidence or next_observation is None:
                raise ProtocolError("resolved result requires evidence and a next observation")
            if next_observation.revision <= command.revision:
                raise ProtocolError("result snapshot must follow submitted observation")
        if next_observation is not None:
            self._validate_observation(next_observation)
        if observed_events and (action_result.outcome != "confirmed" or next_observation is None):
            raise ProtocolError("events require a confirmed result and covering snapshot")
        event_ids = dict(self.events)
        sequences = dict(self._event_sequences)
        for event in observed_events:
            if event.command_id != command.command_id:
                raise ProtocolError("event command mismatch")
            if event.sequence > next_observation.event_watermark:
                raise ProtocolError("snapshot does not include event")
            if event.sequence <= self._observations[command.observation_id].event_watermark:
                raise ProtocolError("event must follow submitted observation")
            if event.event_id in event_ids and event_ids[event.event_id] != event:
                raise ProtocolError("event_id reused with different content")
            if event.sequence in sequences and sequences[event.sequence] != event.event_id:
                raise ProtocolError("event sequence collision")
            event_ids[event.event_id] = event.model_copy(deep=True)
            sequences[event.sequence] = event.event_id
        self.events = event_ids
        self._event_sequences = sequences
        self._results[action_result.result_id] = (
            action_result.model_copy(deep=True),
            tuple(event.model_copy(deep=True) for event in observed_events),
            next_observation.model_copy(deep=True) if next_observation is not None else None,
        )
        self._command_state = "uncertain" if action_result.outcome == "uncertain" else "idle"
        self._ledger.append(ResultEntry(result=action_result.model_copy(deep=True),
            events=tuple(event.model_copy(deep=True) for event in observed_events),
            next_observation=next_observation.model_copy(deep=True) if next_observation is not None else None))
        if self._command_state == "idle":
            self._command = None
        if next_observation is not None:
            return self.observe(next_observation)
        return self._report()

    @property
    def pending_command(self) -> Command | None:
        """返回原始提案/未决命令的副本；恢复后供 adapter 对账，不表示允许重发输入。"""
        return self._command.model_copy(deep=True) if self._command is not None else None

    @property
    def command_state(self) -> str:
        """公共事务状态：idle / proposed / submitted / uncertain。"""
        return self._command_state

    def snapshot(self) -> SessionSnapshot:
        """返回版本化 JSON 可序列化快照，调用方负责持久化。"""
        if self.setup is None or self.observation is None:
            raise ProtocolError('cannot snapshot an uninitialized session')
        entries = tuple(entry.model_copy(deep=True) for entry in self._ledger)
        setup = self.setup.model_copy(deep=True)
        return SessionSnapshot(setup=setup, entries=entries, sha256=ledger_digest(setup, entries))

    @classmethod
    def restore(cls, snapshot: SessionSnapshot | dict[str, Any] | str, policy: Policy,
                backend: DecisionBackend | None = None, *, command_id_factory=None) -> LiveSession:
        """重放已存事实/命令账本；不调用 policy.act，不重放游戏输入或模拟 step。"""
        if isinstance(snapshot, str):
            saved = SessionSnapshot.model_validate_json(snapshot)
        else:
            saved = SessionSnapshot.model_validate(
                snapshot.model_dump(mode='json') if isinstance(snapshot, SessionSnapshot) else snapshot)
        session = cls(policy, backend, command_id_factory=command_id_factory)
        first = saved.entries[0]
        session.initialize(saved.setup, first.observation)
        for entry in saved.entries[1:]:
            if isinstance(entry, ObservationEntry):
                session.observe(entry.observation)
            elif isinstance(entry, ResultEntry):
                session.accept_result(entry.result, entry.events, entry.next_observation)
            elif entry.operation == 'submit':
                session.mark_submitted(entry.command)
            else:
                command = entry.command
                current = session.observation
                pending = current.pending_decision
                if (session._command_state != 'idle' or current.stability != 'stable'
                        or session._command_id_used(command.command_id)
                        or pending is None or command.run_id != saved.setup.run_id
                        or command.observation_id != current.observation_id or command.revision != current.revision
                        or command.decision_id != pending.decision_id or command.choice not in pending.choices
                        or not command.choice.ui_enabled):
                    raise ProtocolError('cannot restore command: inconsistent observation/transaction')
                session._command = command.model_copy(deep=True)
                session._command_state = 'proposed'
                session._ledger.append(entry.model_copy(deep=True))
        # 精确重放并确认去重记录/观察顺序未被遗漏或偷偷归一化。
        if session.snapshot() != saved:
            raise ProtocolError('session ledger did not replay exactly')
        return session
