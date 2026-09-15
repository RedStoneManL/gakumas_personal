"""Shared data contracts. Only public decision state may enter a trajectory.

Task adapters own episode boundaries and raw score extraction. The learner owns
the fixed positive reward scale and never substitutes engine-shaped rewards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


CONTRACT_VERSION = "gakumas-training-contract-v1"
SCHEMA_VERSION = CONTRACT_VERSION
TASK_NAMES = frozenset({"full_produce", "exam_score"})


@dataclass(frozen=True)
class DecisionContext:
    """A snapshot plus an ordered tuple of currently legal action payloads."""

    task: str
    kind: str
    observation: dict[str, Any]
    candidates: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class PolicySelection:
    """Probability and value under the frozen policy that collected this choice."""

    action_index: int
    log_prob: float
    value: float
    policy_version: int
    encoded: Any = None


@dataclass(frozen=True)
class Transition:
    decision: DecisionContext
    selection: PolicySelection


@dataclass
class Episode:
    """One actual game termination, including normal in-game failures.

    ``termination`` is a task-specific diagnostic string, never a reward flag.
    Execution errors and artificial decision limits must raise instead of being
    represented as a normally terminated episode with an invented zero score.
    """

    task: str
    seed: int
    transitions: list[Transition]
    raw_score: float
    termination: str
    metadata: dict[str, Any] = field(default_factory=dict)


Policy = Callable[[DecisionContext], PolicySelection]


class Task(Protocol):
    def run_episode(
        self, policy: Policy, *, seed: int, policy_version: int
    ) -> Episode:
        """Run through a real task boundary with one frozen behavior policy."""
        ...
