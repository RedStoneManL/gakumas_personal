"""标量资源效果器。"""

from __future__ import annotations

from ..constants import SCALAR_RESOURCE_TYPES, STATUS_CHANGE_TRIGGER_ORIGINS
from ..ids import ExamEffect, ExamPhase, GrowEffect
from .context import ExamEffectContext


def apply_scalar_resource(context: ExamEffectContext, effect: dict[str, Any], source: str) -> None:
    """处理好印象、集中以外的即时标量资源增长。"""

    effect_type = str(effect.get('effectType') or '')
    resource_key = SCALAR_RESOURCE_TYPES[effect_type]
    delta = context.direct_value(effect)
    if source == 'card' and effect_type == ExamEffect.CARD_PLAY_AGGRESSIVE:
        delta = context.adjust_direct_gain(delta, add_grow_type=GrowEffect.AGGRESSIVE_ADD)
    elif source == 'card' and effect_type == ExamEffect.REVIEW:
        delta = context.adjust_direct_gain(delta, add_grow_type=GrowEffect.REVIEW_ADD)
    elif source == 'card' and effect_type == ExamEffect.LESSON_BUFF:
        delta = context.adjust_direct_gain(delta, add_grow_type=GrowEffect.LESSON_BUFF_ADD)
    elif source == 'card' and effect_type == ExamEffect.FULL_POWER_POINT:
        delta = context.adjust_direct_gain(
            delta,
            add_grow_type=GrowEffect.FULL_POWER_POINT_ADD,
            reduce_grow_type=GrowEffect.FULL_POWER_POINT_REDUCE,
        )
    context.add_resource(resource_key, delta)
    if resource_key == 'full_power_point':
        context.total_counters['full_power_point_gained'] += context.positive_count(delta)
    context.dispatch_status_change(delta, [effect_type], origin=source)
    if resource_key == 'aggressive' and delta > 0 and context.status_change_origin(source) in STATUS_CHANGE_TRIGGER_ORIGINS:
        # 「直接効果でやる気が n 回増加時」（ProduceExamPhaseType_ExamAggressiveUpInterval）：
        # 只统计卡牌/饮料这类直接效果带来的やる気增加次数。
        context.total_counters['aggressive_up_count'] += 1
        context.dispatch_interval_phase(
            ExamPhase.AGGRESSIVE_UP_INTERVAL,
            context.total_counters['aggressive_up_count'],
            effect_types=[effect_type],
        )
