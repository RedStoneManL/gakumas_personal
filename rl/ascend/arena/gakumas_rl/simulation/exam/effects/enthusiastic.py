"""热意（ExamGimmickEnthusiastic）效果器。

主数据里 `ProduceExamEffectType_ExamGimmickEnthusiastic` 只作为热意资源的「标签类型」出现
（ProduceDescriptionLabel / 卡面描述），当前 dump 里没有以它为 effectType 的效果行；
热意的实际来源是温存解除奖励（ExamSetting.preservationReleaseEnthusiastic*）。
这里仍注册一个效果器：若将来出现直接「熱意+n」的效果行，按 effectValue1 走热意增量管线
（套用 熱意追加 / 熱意増加 修饰）。
"""

from __future__ import annotations

from typing import Any

from ..ids import ExamEffect
from .context import ExamEffectContext


def apply_enthusiastic_effect(context: ExamEffectContext, effect: dict[str, Any], source: str) -> None:
    """按 effectValue1 增加热意。"""

    delta = context.gain_enthusiastic(context.raw_value(effect))
    context.dispatch_status_change(delta, [ExamEffect.GIMMICK_ENTHUSIASTIC], origin=source)
