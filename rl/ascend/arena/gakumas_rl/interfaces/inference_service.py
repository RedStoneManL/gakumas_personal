"""统一的推理服务接口，支持多种RL后端。"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import numpy as np


logger = logging.getLogger(__name__)


@dataclass
class ExamState:
    """考试状态的完整描述。"""

    # 基础属性
    vocal: int
    dance: int
    visual: int
    stamina: int
    max_stamina: int

    # 考试状态
    score: int
    target_score: int  # 目标分数（可变更）
    turn: int
    max_turns: int

    # 资源状态
    block: int  # 元気
    review: int  # 好印象
    aggressive: int  # やる気
    concentration: int  # 強気
    full_power_point: int  # 全力点数
    parameter_buff: int  # 好調
    lesson_buff: int  # 集中

    # 指针状态
    stance: str  # neutral/concentration/full_power/preservation
    stance_level: int

    # 手牌信息
    hand_cards: list[dict[str, Any]]  # 当前手牌列表
    deck_count: int  # 牌库数量
    grave_count: int  # 弃牌堆数量

    # 饮料信息
    drinks: list[dict[str, Any]]  # P饮料列表

    # P道具效果
    status_enchants: list[str]  # 状态附魔ID列表

    # N.I.A专属
    fan_votes: int | None = None  # 粉丝投票数

    # 回忆卡（支援卡）
    support_cards: list[str] | None = None  # 回忆卡ID列表

    # 其他状态
    gimmicks: list[dict[str, Any]] | None = None  # 场地机制


@dataclass
class InferenceRequest:
    """推理请求。"""

    state: ExamState
    legal_actions: list[dict[str, Any]]  # 合法动作列表
    deterministic: bool = True  # 是否使用确定性策略


@dataclass
class InferenceResponse:
    """推理响应。"""

    action_index: int  # 选择的动作索引
    confidence: float  # 置信度
    action_id: str = ""  # 动作稳定标识（优先由客户端传入）
    db_id: str = ""  # 实体类动作对应的主库 ID
    action_kind: str = ""  # 动作类别
    value_estimate: float | None = None  # 价值估计（可选）
    policy_probs: list[float] | None = None  # 策略概率分布（可选）


class RLBackend(ABC):
    """RL后端抽象基类。"""

    @abstractmethod
    def load_model(self, checkpoint_path: Path, *, device: str = 'cpu') -> None:
        """加载模型checkpoint。"""
        pass

    @abstractmethod
    def predict(self, request: InferenceRequest) -> InferenceResponse:
        """执行推理。"""
        pass

    @abstractmethod
    def get_backend_info(self) -> dict[str, Any]:
        """获取后端信息。"""
        pass


class PPOBackend(RLBackend):
    """PPO后端实现（Stable-Baselines3）。"""

    def __init__(self):
        self.model = None
        self.env = None

    def load_model(self, checkpoint_path: Path, *, device: str = 'cpu') -> None:
        """加载PPO模型。"""
        try:
            from sb3_contrib import MaskablePPO
        except ImportError:
            raise RuntimeError("PPO backend requires sb3-contrib MaskablePPO")

        self.model = MaskablePPO.load(str(checkpoint_path), device=device)
        manifest_path = checkpoint_path.with_suffix('.encoder.json')
        self.encoder_manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else None

    def predict(self, request: InferenceRequest) -> InferenceResponse:
        """执行PPO推理。"""
        if self.model is None:
            raise RuntimeError("Model not loaded")

        # 构造观测
        obs = self._state_to_observation(request.state, request.legal_actions)

        # 执行推理
        action, _states = self.model.predict(obs, deterministic=request.deterministic)
        action_index = int(action)

        # 通过稳定字段回传动作身份，避免协议依赖 OCR 名称
        action_id = ""
        db_id = ""
        action_kind = ""
        if action_index < len(request.legal_actions):
            action_payload = request.legal_actions[action_index]
            action_id = str(action_payload.get('action_id') or action_payload.get('id') or "")
            db_id = str(action_payload.get('db_id') or "")
            action_kind = str(action_payload.get('kind') or "")

        # 获取价值估计（如果可用）
        value_estimate = None
        try:
            value_estimate = float(self.model.policy.predict_values(obs)[0])
        except (AttributeError, TypeError, ValueError, IndexError) as exc:
            logger.debug('PPO 价值估计不可用: %s', exc)

        return InferenceResponse(
            action_index=action_index,
            action_id=action_id,
            db_id=db_id,
            action_kind=action_kind,
            confidence=1.0 if request.deterministic else 0.0,
            value_estimate=value_estimate,
        )

    def _state_to_observation(self, state: ExamState, legal_actions: list[dict[str, Any]]) -> dict[str, np.ndarray]:
        """拒绝无法恢复当前训练编码的旧简化 ExamState。"""
        raise ValueError(
            'Legacy ExamState cannot reconstruct the training encoder. '
            'Use LiveSession or predict_encoded with the shared environment encoder and manifest.'
        )

    def predict_encoded(
        self, observation: dict[str, np.ndarray], legal_actions: list[dict[str, Any]],
        manifest: dict[str, Any], *, deterministic: bool = True,
    ) -> InferenceResponse:
        """消费共用 encoder 的张量，严格校验 checkpoint 版本和合法动作掩码。"""
        if self.model is None:
            raise RuntimeError('Model not loaded')
        expected = getattr(self, 'encoder_manifest', None)
        if not expected or expected.get('sha256') != manifest.get('sha256'):
            raise ValueError('Checkpoint encoder manifest missing or incompatible')
        if not self.model.observation_space.contains(observation):
            raise ValueError('Observation does not match checkpoint space')
        if any(not np.isfinite(value).all() for value in observation.values()):
            raise ValueError('Non-finite encoded observation')
        mask = np.asarray(observation['action_mask']) > 0.5
        if not mask.any() or len(legal_actions) > len(mask):
            raise ValueError('Invalid action table')
        for index in np.flatnonzero(mask):
            if index >= len(legal_actions) or not legal_actions[index].get('available', False):
                raise ValueError('Action table does not match mask')
        action, _ = self.model.predict(observation, deterministic=deterministic, action_masks=mask)
        index = int(action)
        if index < 0 or index >= len(legal_actions) or not mask[index]:
            raise ValueError('Policy selected a masked or nonexistent action')
        target = legal_actions[index]
        return InferenceResponse(
            action_index=index, confidence=1.0 if deterministic else 0.0,
            action_id=str(target.get('action_id') or target.get('id') or ''),
            db_id=str(target.get('db_id') or ''), action_kind=str(target.get('kind') or ''),
        )

    def get_backend_info(self) -> dict[str, Any]:
        """获取PPO后端信息。"""
        return {
            'backend': 'ppo',
            'framework': 'stable-baselines3',
            'model_loaded': self.model is not None,
        }


class DQNBackend(RLBackend):
    """DQN后端实现（预留接口）。"""

    def __init__(self):
        self.model = None

    def load_model(self, checkpoint_path: Path, *, device: str = 'cpu') -> None:
        """加载DQN模型。"""
        del checkpoint_path, device
        raise NotImplementedError("DQN backend not yet implemented")

    def predict(self, request: InferenceRequest) -> InferenceResponse:
        """执行DQN推理。"""
        raise NotImplementedError("DQN backend not yet implemented")

    def get_backend_info(self) -> dict[str, Any]:
        """获取DQN后端信息。"""
        return {
            'backend': 'dqn',
            'framework': 'custom',
            'model_loaded': False,
        }


class AlphaZeroBackend(RLBackend):
    """AlphaZero后端实现（预留接口）。"""

    def __init__(self):
        self.model = None
        self.mcts_simulations = 100

    def load_model(self, checkpoint_path: Path, *, device: str = 'cpu') -> None:
        """加载AlphaZero模型。"""
        del checkpoint_path, device
        raise NotImplementedError("AlphaZero backend not yet implemented")

    def predict(self, request: InferenceRequest) -> InferenceResponse:
        """执行AlphaZero推理（带MCTS）。"""
        raise NotImplementedError("AlphaZero backend not yet implemented")

    def get_backend_info(self) -> dict[str, Any]:
        """获取AlphaZero后端信息。"""
        return {
            'backend': 'alphazero',
            'framework': 'custom',
            'mcts_simulations': self.mcts_simulations,
            'model_loaded': False,
        }


class InferenceService:
    """统一的推理服务。"""

    def __init__(
        self,
        backend_type: str = 'ppo',
        *,
        checkpoint_path: str | Path | None = None,
        device: str = 'cpu',
    ):
        """初始化推理服务。

        Args:
            backend_type: 后端类型 (ppo/dqn/alphazero)
        """
        self.backend = self._create_backend(backend_type)
        self.backend_type = backend_type
        self.device = str(device or 'cpu')
        self.checkpoint_path = str(checkpoint_path or "")
        if checkpoint_path:
            self.load_model(checkpoint_path, device=self.device)

    def _create_backend(self, backend_type: str) -> RLBackend:
        """创建后端实例。"""
        backends = {
            'ppo': PPOBackend,
            'dqn': DQNBackend,
            'alphazero': AlphaZeroBackend,
        }

        if backend_type not in backends:
            raise ValueError(f"Unknown backend type: {backend_type}")

        return backends[backend_type]()

    def load_model(self, checkpoint_path: str | Path, *, device: str | None = None) -> None:
        """加载模型。"""
        resolved_device = str(device or self.device or 'cpu')
        resolved_path = Path(checkpoint_path)
        self.backend.load_model(resolved_path, device=resolved_device)
        self.device = resolved_device
        self.checkpoint_path = str(resolved_path)

    def predict(self, request: InferenceRequest) -> InferenceResponse:
        """执行推理。"""
        return self.backend.predict(request)

    def get_info(self) -> dict[str, Any]:
        """获取服务信息。"""
        return {
            'service': 'gakumas_rl_inference',
            'backend_type': self.backend_type,
            'device': self.device,
            'checkpoint_path': self.checkpoint_path,
            'backend_info': self.backend.get_backend_info(),
        }
