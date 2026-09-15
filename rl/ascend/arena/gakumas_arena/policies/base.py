"""策略接口：``Policy.act(env, obs, info) -> action``。

与 ``gakumas_arena.sim`` 里 ``policy(obs, info, env) -> int`` 的可调用约定兼容：``Policy`` 实例
本身可调用，因此可以直接传给 ``run_exam(..., policy=SearchPolicy())``。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Policy(ABC):
    """所有策略的基类。子类实现 ``act``；``reset`` 在每个 episode 开始前调用以保证可复现。"""

    #: 策略名，用于 ``RolloutResult.policy`` 与评估表格
    name: str = "policy"
    #: 实况缺失掩码输入只开放给明确支持局部观测的特征策略；不暴露模拟器隐藏状态。
    supports_partial_observations: bool = False

    @abstractmethod
    def act(self, env: Any, obs: dict[str, Any], info: dict[str, Any]) -> int:
        """给定环境、观测与 info，返回一个动作槽下标（必须在 ``obs['action_mask']`` 内合法）。"""

    def reset(self, seed: int | None = None) -> None:
        """新 episode 前重置内部随机状态；默认无状态。"""

    # 与 facade 的 ``policy(obs, info, env)`` 约定兼容
    def __call__(self, obs: dict[str, Any], info: dict[str, Any], env: Any) -> int:
        return int(self.act(env, obs, info))

    @property
    def __name__(self) -> str:  # facade 用 ``getattr(policy, '__name__')`` 记录策略名
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"
