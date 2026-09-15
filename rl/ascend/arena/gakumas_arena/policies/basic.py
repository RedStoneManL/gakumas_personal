"""随机与启发式基线：包装 ``gakumas_arena.sim`` 已有的策略函数。"""
from __future__ import annotations

from typing import Any

import numpy as np

from ..env import GakumasExamEnv, legal_actions
from ..sim import heuristic_exam_policy, heuristic_produce_policy
from .base import Policy


class RandomPolicy(Policy):
    """在合法动作槽上均匀随机（受种子控制）。"""

    name = "random"
    supports_partial_observations = True

    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed
        self._rng = np.random.default_rng(seed)

    def reset(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(self.seed if seed is None else seed)

    def act(self, env: Any, obs: dict[str, Any], info: dict[str, Any]) -> int:
        return int(self._rng.choice(legal_actions(obs)))


class HeuristicPolicy(Policy):
    """gakumas_rl 内置启发式：

    - 考试环境：官方 ``ProduceExamAutoEvaluation`` 先验 + 一步前瞻（``ProduceRuntime._choose_exam_action``）
    - 培育环境：``interfaces.service._choose_planning_action``

    考试版需要按环境构造一次内部 planner，这里按 ``id(env)`` 惰性缓存。
    """

    name = "heuristic"

    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed
        self._bound_env_id: int | None = None
        self._impl: Any = None

    def reset(self, seed: int | None = None) -> None:
        self._bound_env_id = None
        self._impl = None

    def _bind(self, env: Any) -> None:
        if isinstance(env, GakumasExamEnv):
            self._impl = heuristic_exam_policy(env, self.seed)
        else:
            self._impl = heuristic_produce_policy
        self._bound_env_id = id(env)

    def act(self, env: Any, obs: dict[str, Any], info: dict[str, Any]) -> int:
        if self._impl is None or self._bound_env_id != id(env):
            self._bind(env)
        return int(self._impl(obs, info, env))
