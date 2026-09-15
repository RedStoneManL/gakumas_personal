"""可序列化事务账本；不承担 adapter 的文件持久化或 UI 执行。"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .contracts import ActionResult, Command, Observation, ObservedEvent, RunSetup, WireModel


class ObservationEntry(WireModel):
    """一次绝对观察。"""
    operation: Literal['observe'] = 'observe'
    observation: Observation


class CommandEntry(WireModel):
    """记录原命令，恢复时不能重新询问 policy。"""
    operation: Literal['propose', 'submit']
    command: Command


class ResultEntry(WireModel):
    """包含 next_observation 的原始结果包，支持精确去重。"""
    operation: Literal['result'] = 'result'
    result: ActionResult
    events: tuple[ObservedEvent, ...] = ()
    next_observation: Observation | None = None


SessionEntry = Annotated[ObservationEntry | CommandEntry | ResultEntry, Field(discriminator='operation')]


def ledger_digest(setup: RunSetup, entries: tuple[SessionEntry, ...]) -> str:
    """完整性校验，不是对不可信输入的身份认证。"""
    body = {'setup': setup.model_dump(mode='json'),
            'entries': [entry.model_dump(mode='json') for entry in entries]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class SessionSnapshot(WireModel):
    """同版本账本的原子快照；调用方负责安全落盘及新观察补读。"""
    version: Literal['arena-session/1'] = 'arena-session/1'
    setup: RunSetup
    entries: tuple[SessionEntry, ...]
    sha256: str

    @model_validator(mode='after')
    def check_integrity(self):
        """截断、损坏或遗漏命令的账本不能猜测恢复。"""
        if not self.entries or not isinstance(self.entries[0], ObservationEntry):
            raise ValueError('snapshot must start with an observation')
        if self.sha256 != ledger_digest(self.setup, self.entries):
            raise ValueError('session snapshot checksum mismatch')
        return self
