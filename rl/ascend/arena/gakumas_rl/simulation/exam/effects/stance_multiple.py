"""指针强化（強気強化 / 全力強化）效果的数值解析。

主数据 `ExamConcentrationLessonMultipleAdditive`（強気強化 +n%）与 `ExamFullPowerLessonMultipleAdditive`（全力強化 +n%）
是持续效果，语义为「对应指针的打分倍率加算 n%」：强气 1 段 ×2.0 → ×(2.0 + n)，全力 ×3.0 → ×(3.0 + n)。

打分主管线 `ExamRuntime._apply_score_value_modifiers` 由其它模块维护，这里只提供一个「修正系数」：
`(基础倍率 + 加算) / 基础倍率`，由 `lesson_value.resolve_lesson_effect_value` 在主管线之后乘上去，
数学上等价于把指针倍率替换成 `基础倍率 + 加算`。
"""

from __future__ import annotations

from ..ids import ExamEffect
from .context import ExamEffectContext


STANCE_LESSON_MULTIPLE_ADDITIVE_TYPES = {
    'concentration': ExamEffect.CONCENTRATION_LESSON_MULTIPLE_ADDITIVE,
    'full_power': ExamEffect.FULL_POWER_LESSON_MULTIPLE_ADDITIVE,
}


def stance_base_lesson_multiple(context: ExamEffectContext) -> float:
    """读取当前指针在 ExamSetting 里的基础打分倍率（与运行时主管线使用相同的键）。"""

    setting = context.exam_setting
    stance = context.stance
    if stance == 'concentration':
        key = f'examConcentrationLessonValueMultiplePermil{max(context.stance_level, 1)}'
        return float(setting.get(key) or setting.get('examConcentrationLessonValueMultiplePermil') or 1000) / 1000.0
    if stance == 'full_power':
        return float(setting.get('examFullPowerLessonValueMultiplePermil') or 1000) / 1000.0
    return 1.0


def stance_lesson_multiple_additive(context: ExamEffectContext) -> float:
    """汇总当前指针对应的「指针强化」持续效果加算比例（千分比 → 比例）。"""

    effect_type = STANCE_LESSON_MULTIPLE_ADDITIVE_TYPES.get(context.stance)
    if not effect_type:
        return 0.0
    total = 0.0
    for timed in context.active_effects:
        if str(timed.effect.get('effectType') or '') == effect_type:
            total += context.ratio_value(timed.effect)
    return total


def stance_lesson_multiple_bonus_factor(context: ExamEffectContext) -> float:
    """返回把指针基础倍率替换成「基础 + 加算」所需的乘法修正系数。"""

    additive = stance_lesson_multiple_additive(context)
    if additive <= 0.0:
        return 1.0
    base = stance_base_lesson_multiple(context)
    if base <= 0.0:
        return 1.0
    return (base + additive) / base
