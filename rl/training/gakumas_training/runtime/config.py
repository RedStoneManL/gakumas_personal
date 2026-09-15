from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any

from ..algorithms import PPOConfig
from ..contracts import TASK_NAMES
from ..device import device_kind


# None means no application-imposed upper bound. Keep the mapping for status
# consumers; positive integer and cross-field validation still applies.
EXECUTION_LIMITS = dict.fromkeys(("workers", "episodes_per_update", "minibatch_size", "microbatch_size"))


def validate_execution_settings(settings, *, base=None):
    """Validate only execution controls; reward/model/PPO semantics stay fixed."""
    if not isinstance(settings, dict) or set(settings) - EXECUTION_LIMITS.keys():
        raise ValueError("Unknown execution settings; only workers and episode/batch sizes may change")
    value = {**(base or {}), **settings}
    if set(value) != EXECUTION_LIMITS.keys():
        raise ValueError("Execution settings must contain all four execution controls")
    for name in EXECUTION_LIMITS:
        if type(value[name]) is not int or value[name] < 1:
            raise ValueError(f"{name} must be a positive integer")
    if value["microbatch_size"] > value["minibatch_size"]:
        raise ValueError("microbatch_size must not exceed minibatch_size")
    return value


def initial_execution_settings(config):
    return validate_execution_settings({"workers": config.workers,
        "episodes_per_update": config.episodes_per_update,
        "minibatch_size": config.ppo.minibatch_size, "microbatch_size": config.ppo.microbatch_size})


@dataclass(frozen=True)
class RunConfig:
    task: str
    score_scale: float = 150000.0
    seed: int = 91000000
    episodes_per_update: int = 2
    eval_every_updates: int = 1
    eval_episodes: int = 1
    eval_seed: int = 191000000
    device: str = "cpu"
    workers: int = 1
    torch_threads: int = 2
    ppo: PPOConfig = field(default_factory=PPOConfig)
    model: dict[str, Any] = field(default_factory=dict)
    task_config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        device_kind(self.device)
        if type(self.torch_threads) is not int or self.torch_threads < 1:
            raise ValueError("torch_threads must be a positive integer")
        if self.task not in TASK_NAMES:
            raise ValueError(f"Unknown training task: {self.task}")
        if not math.isfinite(self.score_scale) or self.score_scale <= 0:
            raise ValueError("score_scale must be a fixed finite positive constant")
        initial_execution_settings(self)
        if self.episodes_per_update < 1 or self.eval_episodes < 1 or self.eval_every_updates < 0:
            raise ValueError("Invalid episode/evaluation counts")
        if self.seed < 0 or self.eval_seed < 0:
            raise ValueError("Seeds must be nonnegative")
        if self.seed <= self.eval_seed < self.seed + self.episodes_per_update or (
                self.eval_seed <= self.seed < self.eval_seed + self.eval_episodes):
            raise ValueError("Training and evaluation seed intervals overlap")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RunConfig":
        value = dict(value)
        value["ppo"] = PPOConfig(**value.get("ppo", {}))
        return cls(**value)
