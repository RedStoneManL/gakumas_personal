"""Arena 实况数据契约与本地会话桥。"""

from .contracts import (
    CONTRACT_VERSION,
    ActionResult,
    Choice,
    Command,
    Decision,
    EntityRef,
    Inventory,
    MemorySetup,
    Observation,
    ObservedEvent,
    ObservedValue,
    PendingDecision,
    RunLoadout,
    RunSetup,
    SessionReport,
    SupportSetup,
)
from .exam import ExamBackend, ExamCardState, ExamSelection, ExamTimedEffect, LiveBackend
from .issues import LiveIssue, classify_issue, classify_issues
from .loadout import to_loadout_config
from .passive import ExamEnchantState
from .planning import PlanningBackend
from .recovery import SessionSnapshot
from .session import DecisionBackend, LiveSession, MissingFields, PreparedDecision, ProtocolError

__all__ = [
    "CONTRACT_VERSION",
    "ActionResult",
    "Choice",
    "Command",
    "Decision",
    "DecisionBackend",
    "EntityRef",
    "ExamBackend",
    "ExamCardState",
    "ExamEnchantState",
    "ExamSelection",
    "ExamTimedEffect",
    "Inventory",
    "LiveBackend",
    "LiveIssue",
    "LiveSession",
    "MemorySetup",
    "MissingFields",
    "Observation",
    "ObservedEvent",
    "ObservedValue",
    "PendingDecision",
    "PlanningBackend",
    "PreparedDecision",
    "ProtocolError",
    "RunLoadout",
    "RunSetup",
    "SessionReport",
    "SessionSnapshot",
    "SupportSetup",
    "classify_issue",
    "classify_issues",
    "to_loadout_config",
]
