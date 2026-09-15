"""打分效果器。"""

from __future__ import annotations

from typing import Any

from ..ids import ExamEffect, GrowEffect
from ..scoring import floor_int
from .context import ExamEffectContext


def lesson_hit_count(context: ExamEffectContext, effect: dict[str, Any], source: str) -> int:
    """「パラメータ+n（m回）」的发动次数：`effectCount`（缺省 1）+ 卡牌成長「上昇回数増加/減少」。"""

    times = max(int(effect.get('effectCount') or 0), 1)
    if source == 'card':
        # 计数型：成長 LessonCountAdd/Reduce 是整数次数
        times += int(round(context.current_card_grow_total(GrowEffect.LESSON_COUNT_ADD)))
        times -= int(round(context.current_card_grow_total(GrowEffect.LESSON_COUNT_REDUCE)))
    return max(times, 1)


def apply_lesson_score_effect(context: ExamEffectContext, effect: dict[str, Any], source: str) -> None:
    """把打分类效果转成得分并同步回合颜色统计。

    每一「回」都是一次独立的 パラメータ上昇：单独走分数管线并各自取整（gakumas-core `times` 循环 / engine 逐次结算），
    中途达到 PERFECT/强制结束时停止。
    """

    effect_type = str(effect.get('effectType') or '')
    for _ in range(lesson_hit_count(context, effect, source)):
        lesson_value = context.resolve_lesson_effect_value(effect, from_card=source == 'card')
        if effect_type == ExamEffect.LESSON_DEPEND_BLOCK:
            # 「元気の n% 分パラメータ上昇させ、元気を半分/0にする」：分数按减少前的元気计算，
            # 之后减少 floor(元気 × effectValue2/1000)（gakumas-core performLeveragingVitality）。
            reduction_ratio = float(effect.get('effectValue2') or 0) / 1000.0
            if reduction_ratio > 0:
                context.resources['block'] = max(
                    context.resources['block'] - floor_int(context.resources['block'] * reduction_ratio), 0.0
                )
        lesson_delta = context.score_gain(lesson_value)
        context.score += lesson_delta
        if context.current_turn_color in context.score_per_color:
            context.score_per_color[context.current_turn_color] += lesson_delta
        context.turn_counters['lesson_plays'] += 1
        context.total_counters['lesson_plays'] += 1
        context.update_clear_state_after_score_change()
        if context.terminated:
            break
