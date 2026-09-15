"""考试训练和实况共享原环境张量，按可观测依赖设置缺失掩码。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

import gymnasium as gym
import numpy as np

from .passive_catalog import PASSIVE_FEATURE_NAMES, PASSIVE_IDS

EXAM_ENCODER_VERSION = 'arena-exam-observed/2'
# 对应 GakumasExamEnv._global_observation 的原有顺序，不重新定义数值公式。
BASE_NAMES = (
    'turn_ratio', 'remaining_turn_ratio', 'score_ratio', 'score_gap', 'stamina_ratio',
    'hand_count', 'hand_overflow', 'deck_count', 'discard_count', 'hold_count', 'lost_count',
    'drink_count', 'block', 'review', 'aggressive', 'concentration', 'full_power_point',
    'parameter_buff', 'lesson_buff', 'preservation', 'over_preservation', 'enthusiastic',
    'sleepy', 'panic', 'stamina_consumption_down', 'plays_used', 'play_limit',
    'stance_neutral', 'stance_concentration', 'stance_full_power', 'stance_preservation',
    'weight_vocal', 'weight_dance', 'weight_visual', 'extra_turns', 'active_effect_count',
    'active_enchant_count', 'score_bonus_multiplier', 'vocal', 'dance', 'visual',
    'fan_votes', 'fan_requirement', 'future_gimmicks', 'next_gimmick', 'is_exam', 'is_lesson',
    'color_vocal', 'color_dance', 'color_visual',
)
DEPENDENCIES = {
    0: {'turn', 'max_turns'}, 1: {'turn', 'max_turns'},
    2: {'score', 'target_score'}, 3: {'score', 'target_score'},
    4: {'stamina', 'max_stamina'}, 5: {'inventory.hand'}, 6: {'inventory.hand'},
    7: {'inventory.deck'}, 8: {'inventory.discard'}, 9: {'inventory.hold'},
    10: {'inventory.lost'}, 11: {'inventory.drinks'},
    **{i: {BASE_NAMES[i]} for i in range(12, 25)},
    25: {'plays_used'}, 26: {'plays_used', 'plays_remaining'},
    **{i: {'stance'} for i in range(27, 31)},
    # exam_effects 仅是额外持续效果；不能把它的长度当全部状态数。
    34: {'extra_turns'}, 36: {'exam_enchants'},
    37: {'score_bonus_multiplier'}, 45: set(), 46: set(),
    **{i: {'current_turn_color'} for i in range(47, 50)},
}


def exam_encoder_manifest(env: Any) -> dict[str, Any]:
    """同时标记有序特征、场景/角色词表、动作语义与维度。"""
    names = list(BASE_NAMES) + [f'stage:{v}' for v in (*env.stage_type_ids, 'unknown')]
    names += [f'plan:{v}' for v in range(4)]
    names += [f'character:{v}' for v in env.loadout_character_ids]
    names += [f'rarity:{v}' for v in env.loadout_rarities]
    names += [f'focus:{v}' for v in env.scenario.focus_effect_types]
    names += ['producer_level', 'idol_rank', 'dearness_level', 'use_after_item']
    if env.include_deck_features:
        raise ValueError('Observed encoder requires include_deck_features=False')
    if len(names) != env.global_dim:
        raise ValueError('Exam encoder layout changed; update observed dependencies')
    body = {'version': EXAM_ENCODER_VERSION, 'rules': 'arena-rules/2',
            'taxonomy': asdict(env.taxonomy), 'global_features': names,
            'max_actions': env.max_actions, 'action_feature_dim': env.action_feature_dim,
            'max_hand_cards': env.max_hand_cards, 'max_drinks': env.max_drinks,
            'decision_kinds': ['exam', 'search', 'discard'],
            'wire_action_types': ['card', 'drink', 'end_turn', 'card_select'],
            'exam_context': ['parameter_buff_multiple_per_turn', 'plays_remaining'], 'missing_masks': True,
            'passive_ids': list(PASSIVE_IDS), 'passive_features': list(PASSIVE_FEATURE_NAMES),
            'counter_semantics': 'arena-exam-counters/1'}
    if getattr(env, 'structural_passives', False):
        from .structural_encoding import structural_manifest
        body['version'] = 'arena-exam-observed/3'
        body.pop('passive_ids')
        body.pop('passive_features')
        body['passive_structure'] = structural_manifest()
    return {**body, 'sha256': hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()}


def encode_exam_observation(env: Any, known_fields: set[str], *, raw: dict | None = None,
                            decision_kind: str = 'exam') -> dict[str, np.ndarray]:
    """同一入口供实况与训练 wrapper 调用；隐藏状态变化不得影响未知特征。"""
    exam_encoder_manifest(env)
    raw = env._build_observation() if raw is None else raw
    gm = np.zeros_like(raw['global'])
    for index, dependencies in DEPENDENCIES.items():
        if dependencies <= known_fields:
            gm[index] = 1
    start = 50
    if 'exam_stage_type' in known_fields:
        gm[start:start + env.stage_context_dim] = 1
    start += env.stage_context_dim
    if 'loadout.idol_card_id' in known_fields:
        gm[start:start + env.loadout_context_dim - 4] = 1
    am = np.zeros_like(raw['action_features'])
    prefix = env.action_feature_dim - 14
    for index, candidate in enumerate(env._candidates):
        if not candidate.payload.get('available'):
            continue
        am[index, :prefix + 9] = 1
        # 静态卡面和实际变体已明确；动态资源未提供时仍须掩码。
        for slot, deps in ((9, {'score', 'target_score'}), (10, {'review'}),
                           (11, {'block'}), (12, {'aggressive'})):
            if deps <= known_fields:
                am[index, prefix + slot] = 1
        am[index, prefix + 13] = 1  # 仅本次可见候选顺序
    kind = np.zeros(3, dtype=np.float32)
    kind[['exam', 'search', 'discard'].index(decision_kind)] = 1
    features = np.where(am, raw['action_features'], 0).astype(np.float32)
    if decision_kind != 'exam':
        # 选目标不代表出牌；旧 card 动作 one-hot 清空，由独立 kind 区分。
        features[:, :len(env.taxonomy.action_types)] = 0
    context_values = np.array([env.runtime.resources['parameter_buff_multiple_per_turn'],
                               max(env.runtime.play_limit - env.runtime.turn_counters['play_count'], 0)], dtype=np.float32)
    context_mask = np.array([float('parameter_buff_multiple_per_turn' in known_fields),
                            float({'plays_used', 'plays_remaining'} <= known_fields)], dtype=np.float32)
    # 补足旧 global 未包含的绝好调持续时间，训练/实况同入口、同归一化。
    context = np.where(context_mask, context_values / (context_values + 10.0), 0).astype(np.float32)
    passive = np.zeros((len(PASSIVE_IDS), len(PASSIVE_FEATURE_NAMES)), dtype=np.float32)
    passive_mask = np.zeros_like(passive)
    structural = getattr(env, 'structural_passives', False)
    if 'exam_enchants' in known_fields and not structural:
        passive_mask[:] = 1
        seen = set()
        for enchant in env.runtime.active_enchants:
            if enchant.enchant_id not in PASSIVE_IDS or enchant.enchant_id in seen:
                raise ValueError('Observed encoder cannot represent unsupported or duplicate passive')
            seen.add(enchant.enchant_id)
            def bound(value):
                return max(value or 0, 0) / (max(value or 0, 0) + 10.0)
            passive[PASSIVE_IDS.index(enchant.enchant_id)] = (
                1, bound(enchant.remaining_turns), float(enchant.remaining_turns is None),
                bound(enchant.remaining_count), float(enchant.remaining_count is None),
                bound(enchant.applied_turn), bound(enchant.last_fired_turn), float(enchant.last_fired_turn < 0))
    passive_result = {'passive_features': passive, 'passive_features_known_mask': passive_mask}
    if structural:
        from .structural_encoding import encode_passive_structure
        passive_result = encode_passive_structure(env.runtime, known='exam_enchants' in known_fields)
    return {'global': np.where(gm, raw['global'], 0).astype(np.float32),
            'action_features': features, 'action_mask': raw['action_mask'].copy(),
            'global_known_mask': gm, 'action_features_known_mask': am, 'decision_kind': kind,
            'exam_context': context, 'exam_context_known_mask': context_mask,
            **passive_result}


class ExamVisibilityWrapper(gym.ObservationWrapper):
    """训练使用相同考试编码；既有 checkpoint 不具有该空间和 manifest。"""

    def __init__(self, env: gym.Env, known_fields: set[str], *, structural_passives: bool = False) -> None:
        """声明可观测字段，不改变底层仿真。"""
        super().__init__(env)
        self.known_fields = set(known_fields)
        env.unwrapped.structural_passives = structural_passives
        spaces = dict(env.observation_space.spaces)
        for key in ('global', 'action_features'):
            spaces[f'{key}_known_mask'] = gym.spaces.Box(0, 1, shape=spaces[key].shape, dtype=np.float32)
        spaces['decision_kind'] = gym.spaces.Box(0, 1, shape=(3,), dtype=np.float32)
        spaces['exam_context'] = gym.spaces.Box(0, 1, shape=(2,), dtype=np.float32)
        spaces['exam_context_known_mask'] = gym.spaces.Box(0, 1, shape=(2,), dtype=np.float32)
        for key in ('passive_features', 'passive_features_known_mask'):
            spaces[key] = gym.spaces.Box(0, 1, shape=(len(PASSIVE_IDS), len(PASSIVE_FEATURE_NAMES)), dtype=np.float32)
        if structural_passives:
            from .structural_encoding import passive_shapes
            for key, shape in passive_shapes().items():
                spaces[key] = gym.spaces.Box(-1, 1, shape=shape, dtype=np.float32)
                spaces[key + '_known_mask'] = gym.spaces.Box(0, 1, shape=shape, dtype=np.float32)
        self.observation_space = gym.spaces.Dict(spaces)

    def observation(self, observation: dict) -> dict:
        """直接调用公共入口。"""
        return encode_exam_observation(self.env.unwrapped, self.known_fields, raw=observation)
