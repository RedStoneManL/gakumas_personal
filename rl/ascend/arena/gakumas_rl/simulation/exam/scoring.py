"""考试/课程结算的取整与倍率规则（整数运算）。

规则来源：`docs/rules/lesson_exam_engine.md` §4.3 / §5 / §6 / §15，以及 `docs/rules/scoring_fidelity.md`。

要点：
- 分数/パラメータ 的每一步都是「先算后向上取整」，元気向下取整，体力消耗向上取整。
- 好調/絶好調 倍率必须用整数千分比运算：`0.1 × 1.4` 这类浮点误差会改变取整结果
  （gakumas-core `lesson-mutation.ts` 注释，本家 v1.2.0 实测向量见规则文档 §5.2）。
- 所有倍率常数仍以 `ExamSetting` 的 permil 字段为准，这里只提供组合与取整。
- 规则文档 §15 里标注「未決/待验证」的项以 `ScoringRules` 开关暴露，默认值为社区共识。
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

# 浮点比较用的极小量：`ceil(13.5)` 这类本来就是整数边界的值不受影响，只吸收 1e-12 级别的累计误差。
EPSILON = 1e-9
PERMIL = 1000


@dataclass(frozen=True)
class ScoringRules:
    """结算规则开关。默认值 = 社区共识（gakumas-core / gakumas-engine / seesaawiki 三方一致的选择）。"""

    # §15-2：回合结束的好印象结算是否吃 集中/熱意 加算。两套模拟器都吃，本家未验证。
    review_payout_uses_concentration: bool = True
    # §15-3：消費体力減少 与 消費体力増加 共存时的合成倍率。
    # False → ×1（两套模拟器）；True → 使用 `ExamSetting.examStaminaConsumptionAddDownPermil`（1250）。
    stamina_down_and_add_use_setting_permil: bool = False
    # §5.5：元気增量的最终取整方向。'floor'（seesaawiki 転記，采用）或 'ceil'（gakumas-core）。
    genki_rounding: str = 'floor'
    # §3.5：本回合新获得（或回合开始阶段付与）的持续状态在下一回合开始时不递减。
    fresh_modifier_no_decay: bool = True
    # §5.4：「好印象追加発動+n」重复结算时，每次结算单独取整（True）还是先乘次数再取整（False）。
    review_activation_rounds_each: bool = True
    # §15-12：Pアイテム/トラブル 的「体力減少n」是否穿透元気。False = 先扣元気（gakumas-core，[推定]）。
    stamina_damage_penetrates_genki: bool = False


DEFAULT_SCORING_RULES = ScoringRules()


def ceil_int(value: float) -> int:
    """正向数值向上取整（带浮点容差），非正值归零。"""

    numeric = float(value)
    if numeric <= EPSILON:
        return 0
    return int(math.ceil(numeric - EPSILON))


def floor_int(value: float) -> int:
    """正向数值向下取整（带浮点容差），非正值归零。"""

    numeric = float(value)
    if numeric <= EPSILON:
        return 0
    return int(math.floor(numeric + EPSILON))


def round_genki(value: float, rules: ScoringRules = DEFAULT_SCORING_RULES) -> int:
    """按规则开关对元気增量取整。"""

    return ceil_int(value) if rules.genki_rounding == 'ceil' else floor_int(value)


def ceil_div(numerator: int, denominator: int) -> int:
    """非负整数的向上整除。"""

    if denominator <= 0:
        raise ValueError('denominator must be positive')
    if numerator <= 0:
        return 0
    return -((-numerator) // denominator)


def apply_permil_ceil(value: int, permil: int) -> int:
    """`ceil(value × permil / 1000)`，全程整数运算。"""

    return ceil_div(int(value) * int(permil), PERMIL)


def scale_by_permils(value: int, permils: Iterable[int]) -> int:
    """`ceil(value × Π(permil_i / 1000))`：所有倍率合并成一个分数后只取整一次。

    gakumas-engine `resolvers.resolveScore` 的 S2 步骤就是把 好調倍率×指針倍率×増減倍率 一起乘完再 ceil。
    """

    numerator = int(value)
    denominator = 1
    for permil in permils:
        numerator *= int(permil)
        denominator *= PERMIL
    return ceil_div(numerator, denominator)


def permil_from_ratio(ratio: float) -> int:
    """把 0-1 浮点比例（来自 `_ratio_value`）还原成整数千分比。"""

    return int(round(float(ratio) * PERMIL))


def good_condition_permil(
    parameter_buff_turns: int,
    excellent_condition: bool,
    exam_setting: dict[str, Any],
) -> int:
    """好調/絶好調 的整数千分比倍率。

    好調 >0 时 `examParameterBuffPermil`（1500）；同时有 絶好調 时每 1 回合好調再 +`examParameterBuffMultiplePerTurnPermil`（100）。
    絶好調 单独存在无效。绝好调的层数不参与计算（它是回合数型状态，不是叠加倍率）。
    """

    turns = int(parameter_buff_turns)
    if turns <= 0:
        return PERMIL
    permil = int(exam_setting.get('examParameterBuffPermil') or 1500)
    if excellent_condition:
        permil += turns * int(exam_setting.get('examParameterBuffMultiplePerTurnPermil') or 0)
    return permil


def stance_lesson_permil(
    stance: str,
    stance_level: int,
    exam_setting: dict[str, Any],
    additive_permil: int = 0,
) -> int:
    """指針的打分倍率（千分比），含 強気強化/全力強化 的加算。"""

    if stance == 'concentration':
        key = f'examConcentrationLessonValueMultiplePermil{max(int(stance_level), 1)}'
        base = int(exam_setting.get(key) or exam_setting.get('examConcentrationLessonValueMultiplePermil') or PERMIL)
    elif stance == 'preservation':
        if int(stance_level) >= 3:
            base = int(exam_setting.get('examOverPreservationLessonValueMultiplePermil') or 0)
        else:
            key = f'examPreservationLessonValueMultiplePermil{max(int(stance_level), 1)}'
            base = int(exam_setting.get(key) or PERMIL)
    elif stance == 'full_power':
        base = int(exam_setting.get('examFullPowerLessonValueMultiplePermil') or PERMIL)
    else:
        return PERMIL
    return max(base + int(additive_permil), 0)


def stance_stamina_permil(stance: str, stance_level: int, exam_setting: dict[str, Any]) -> int:
    """指針的体力消耗倍率（千分比）。"""

    if stance == 'concentration':
        key = f'examConcentrationStaminaMultiplePermil{max(int(stance_level), 1)}'
        return int(exam_setting.get(key) or PERMIL)
    if stance == 'preservation':
        if int(stance_level) >= 3:
            return int(exam_setting.get('examOverPreservationStaminaMultiplePermil') or 0)
        key = f'examPreservationStaminaMultiplePermil{max(int(stance_level), 1)}'
        return int(exam_setting.get(key) or PERMIL)
    return PERMIL


def stamina_consumption_permil(
    has_down: bool,
    has_add: bool,
    exam_setting: dict[str, Any],
    rules: ScoringRules = DEFAULT_SCORING_RULES,
) -> int:
    """消費体力減少 / 消費体力増加 的合成倍率（千分比）。

    減少 ×`examStaminaConsumptionDownPermil`（500），増加 ×(1 + `examStaminaConsumptionAddPermil`)（2000）。
    两者同时存在：默认 ×1（§15-3 社区共识），开关打开时用 `examStaminaConsumptionAddDownPermil`。
    多个同类状态只按「存在/不存在」判定：它们是回合数型状态，叠加只会延长回合数而不会再乘一次。
    """

    if has_down and has_add:
        if rules.stamina_down_and_add_use_setting_permil:
            return int(exam_setting.get('examStaminaConsumptionAddDownPermil') or PERMIL)
        return PERMIL
    if has_down:
        return int(exam_setting.get('examStaminaConsumptionDownPermil') or 500)
    if has_add:
        return PERMIL + int(exam_setting.get('examStaminaConsumptionAddPermil') or PERMIL)
    return PERMIL


def score_bonus_permil(multiplier: float) -> int:
    """把考试スコアボーナス倍率（例 17.94 = 1794%）转成整数千分比，避免 `50 × 17.94` 的浮点尾数影响 ceil。"""

    return max(int(round(float(multiplier) * PERMIL)), 0)
