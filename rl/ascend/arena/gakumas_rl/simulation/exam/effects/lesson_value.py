"""打分效果的数值解析。"""

from __future__ import annotations

from ..ids import ExamEffect, GrowEffect
from .context import ExamEffectContext


def resolve_lesson_effect_value(context: ExamEffectContext, effect: dict[str, Any], from_card: bool = False) -> float:
    """按资源、检索数量和 stance 结算课程分数效果。"""

    effect_type = str(effect.get('effectType') or '')
    base_value = context.direct_value(effect)
    ratio_value = context.ratio_value(effect)
    if from_card and effect_type == ExamEffect.LESSON_DEPEND_REVIEW:
        ratio_value += context.current_card_ratio_bonus(GrowEffect.LESSON_DEPEND_REVIEW_ADD)
    elif from_card and effect_type == ExamEffect.LESSON_DEPEND_AGGRESSIVE:
        ratio_value += context.current_card_ratio_bonus(GrowEffect.LESSON_DEPEND_AGGRESSIVE_ADD)
    elif from_card and effect_type == ExamEffect.LESSON_DEPEND_BLOCK:
        ratio_value += context.current_card_ratio_bonus(GrowEffect.LESSON_DEPEND_BLOCK_ADD)
    search_count = context.search_count(str(effect.get('produceCardSearchId') or ''))
    if effect_type == ExamEffect.LESSON_FIX:
        value = base_value
    elif effect_type == ExamEffect.LESSON_DEPEND_REVIEW:
        value = context.ceil_positive(context.resources['review'] * ratio_value)
    elif effect_type == ExamEffect.LESSON_DEPEND_AGGRESSIVE:
        value = context.ceil_positive(context.resources['aggressive'] * ratio_value)
    elif effect_type == ExamEffect.LESSON_DEPEND_BLOCK:
        value = context.ceil_positive(context.resources['block'] * ratio_value)
    elif effect_type == ExamEffect.LESSON_DEPEND_PARAMETER_BUFF:
        value = context.ceil_positive(context.resources['parameter_buff'] * ratio_value)
    elif effect_type == ExamEffect.LESSON_DEPEND_STAMINA:
        # 「体力の n% 分パラメータ上昇」：参照当前体力（非最大体力），effectValue1 为千分比（8000 = 800%）。
        value = context.ceil_positive(context.stamina * ratio_value)
    elif effect_type == ExamEffect.MULTIPLE_ENTHUSIASTIC_LESSON:
        # 「パラメータ+n（熱意効果を m 倍適用）」：与 ExamMultipleLessonBuffLesson 同构，
        # effectValue2 千分比为额外倍率，主管线会再加一次热意，合计 (1 + effectValue2/1000) 倍。
        extra_ratio = float(effect.get('effectValue2') or 0) / 1000.0
        value = context.compose_referenced_gain(
            base=max(base_value, 1.0),
            referenced=context.resources['enthusiastic'] * extra_ratio,
        )
    elif effect_type == ExamEffect.LESSON_DEPEND_PLAY_CARD_COUNT_SUM:
        # 「パラメータ+v1（レッスン中に使用したスキルカード1枚につき、パラメータ上昇量+v2）」：v1 + 使用枚数 × v2
        # （effectValue2 是固定值不是千分比；录像：ときめきのいっぱい 3 + 3×16 + 集中22 → ×1.5 = 110）。
        value = base_value + context.total_counters['play_count'] * float(effect.get('effectValue2') or 0)
    elif effect_type == ExamEffect.LESSON_DEPEND_STAMINA_CONSUMPTION_SUM:
        value = context.ceil_positive(context.total_counters['stamina_spent'] * ratio_value)
    elif effect_type == ExamEffect.LESSON_DEPEND_BLOCK_CONSUMPTION_SUM:
        value = context.ceil_positive(context.total_counters['block_consumed'] * ratio_value)
    elif effect_type == ExamEffect.LESSON_DEPEND_BLOCK_AND_SEARCH_COUNT:
        extra_ratio = float(effect.get('effectValue2') or 0) / 1000.0
        value = context.compose_referenced_gain(
            base=search_count * max(base_value, 1.0),
            referenced=context.resources['block'] * extra_ratio,
        )
    elif effect_type == ExamEffect.LESSON_PER_SEARCH_COUNT:
        value = context.compose_referenced_gain(
            base=max(base_value, 1.0),
            referenced=search_count * (float(effect.get('effectValue2') or 0) / 1000.0),
        )
    elif effect_type == ExamEffect.LESSON_FULL_POWER_POINT:
        value = context.ceil_positive(context.resources['full_power_point'] * max(base_value, 1.0))
    elif effect_type in {ExamEffect.LESSON_ADD_MULTIPLE_LESSON_BUFF, ExamEffect.MULTIPLE_LESSON_BUFF_LESSON}:
        extra_ratio = float(effect.get('effectValue2') or effect.get('effectValue1') or 0) / 1000.0
        value = context.compose_referenced_gain(
            base=max(base_value, 1.0),
            referenced=context.focus_score_contribution() * extra_ratio,
        )
    elif effect_type == ExamEffect.LESSON_ADD_MULTIPLE_PARAMETER_BUFF:
        extra_ratio = float(effect.get('effectValue2') or 0) / 1000.0
        value = context.compose_referenced_gain(
            base=max(base_value, 1.0),
            referenced=context.resources['parameter_buff'] * extra_ratio,
        )
    else:
        value = base_value
    if from_card:
        value = context.adjust_direct_gain(
            value,
            add_grow_type=GrowEffect.LESSON_ADD,
            reduce_grow_type=GrowEffect.LESSON_REDUCE,
        )
    # 強気強化 / 全力強化 的加算已并入主管线的指针倍率（runtime._stance_lesson_multiple_additive_permil），
    # 这里不再后乘，避免双算（见 docs/rules/hif_exam_effects.md §1.5 的接入点提示）。
    modified = context.apply_score_value_modifiers(value)
    return max(modified, 0.0)
