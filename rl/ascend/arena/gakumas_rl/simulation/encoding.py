"""训练与实况共用原始环境编码，并用显式掩码隔离不可观测特征。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

import gymnasium as gym
import numpy as np

ENCODER_VERSION = 'arena-planning-observed/2'

# 只有这里声明了完整依赖的全局特征才允许在局部实况下进入 actor。
GLOBAL_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    'step_ratio': ('step',), 'remaining_step_ratio': ('step',),
    'audition_progress': ('audition_index',), 'remaining_audition_ratio': ('audition_index',),
    'stamina_ratio': ('stamina', 'max_stamina'), 'produce_point_ratio': ('produce_points',),
    'fan_vote_ratio': ('fan_votes',), 'vocal_ratio': ('vocal',), 'dance_ratio': ('dance',),
    'visual_ratio': ('visual',), 'vocal_growth': ('vocal_growth',),
    'dance_growth': ('dance_growth',), 'visual_growth': ('visual_growth',),
    'refresh_used_ratio': ('refresh_used',), 'last_exam_score_ratio': ('last_exam_score',),
    'producer_level_ratio': ('producer_level',), 'idol_rank_ratio': ('idol_rank',),
    'dearness_level_ratio': ('dearness_level',),
    'exam_score_bonus_multiplier': ('exam_score_bonus_multiplier',),
    'deck_size_ratio': ('inventory.deck',), 'drink_inventory_ratio': ('inventory.drinks',),
    'route_first_star': (), 'route_nia': (), 'score_weight_vocal': (),
    'score_weight_dance': (), 'score_weight_visual': (),
    'is_shop_phase': (), 'is_retry_phase': (),
}


def encoder_manifest(env: Any, *, observed: bool = False) -> dict[str, Any]:
    """记录名称、顺序、维度和语义版本，不能仅靠张量形状判断 checkpoint 兼容。"""
    body = {
        'version': ENCODER_VERSION if observed else 'arena-env/2',
        'rules_semantics': 'parameter-buff-multiple-duration/2',
        'taxonomy': asdict(env.taxonomy),
        'global_features': list(env.global_feature_names),
        'action_feature_dim': env.action_feature_dim, 'max_actions': env.max_actions,
        'missing_masks': observed,
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return {**body, 'sha256': digest}


def mask_planning_observation(
    env: Any, raw: dict[str, np.ndarray], known_fields: set[str],
) -> dict[str, np.ndarray]:
    """保留原 env 特征值；无完整依赖的项只输出零占位和 known_mask=0。"""
    global_mask = np.zeros_like(raw['global'], dtype=np.float32)
    for index, name in enumerate(env.global_feature_names):
        dependencies = GLOBAL_DEPENDENCIES.get(name)
        if name.startswith(('loadout_plan_', 'loadout_exam_')):
            dependencies = ('loadout.idol_card_id',)
        if dependencies is not None and set(dependencies) <= known_fields:
            global_mask[index] = 1.0
    action_mask = np.zeros_like(raw['action_features'], dtype=np.float32)
    prefix = env.action_feature_dim - 41
    # 共用 taxonomy 与主数据效果元信息，不另造效果分类或硬编码 52x100。
    for index, candidate in enumerate(env._candidates):
        if candidate.kind == 'padding':
            action_mask[index] = 1.0
            continue
        if not candidate.payload.get('available', False):
            continue
        action_mask[index, :prefix] = 1.0
        # 这些数值只取自当前明确候选和固定剧本，未知资源及模型风险项不进入 actor。
        for slot in (1, 2, 3, 4, 5, 6, 7, 8, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22):
            action_mask[index, prefix + slot] = 1.0
        if {'stamina', 'max_stamina'} <= known_fields:
            for slot in (0, 9, 24):
                action_mask[index, prefix + slot] = 1.0
    return {
        'global': np.where(global_mask > 0, raw['global'], 0).astype(np.float32),
        'action_features': np.where(action_mask > 0, raw['action_features'], 0).astype(np.float32),
        'action_mask': raw['action_mask'].copy(),
        'global_known_mask': global_mask,
        'action_features_known_mask': action_mask,
    }


class PlanningVisibilityWrapper(gym.ObservationWrapper):
    """训练可用同一可观测配置；需要读取缺失掩码的 actor 必须用此配置重新训练。"""

    def __init__(self, env: gym.Env, known_fields: set[str]) -> None:
        """绑定实况可提供的字段集合，增加两个缺失掩码空间。"""
        super().__init__(env)
        self.known_fields = set(known_fields)
        spaces = dict(env.observation_space.spaces)
        spaces['global_known_mask'] = gym.spaces.Box(0, 1, shape=spaces['global'].shape, dtype=np.float32)
        spaces['action_features_known_mask'] = gym.spaces.Box(0, 1, shape=spaces['action_features'].shape, dtype=np.float32)
        self.observation_space = gym.spaces.Dict(spaces)

    def observation(self, observation: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """与实况入口调用完全相同的环境特征掩码函数。"""
        return mask_planning_observation(self.env.unwrapped, observation, self.known_fields)
