"""未精确分类效果的兜底效果器。"""

from __future__ import annotations

import logging
from typing import Any

from .context import ExamEffectContext

logger = logging.getLogger(__name__)

UNKNOWN_EFFECT_TYPES_SEEN: set[str] = set()
"""运行期间被兜底吸收过的 effectType 集合，便于测试/巡检发现主数据新增的类型。"""


def apply_fallback_timed_effect(context: ExamEffectContext, effect: dict[str, Any], source: str) -> None:
    """未知效果先按持续效果挂载，并对每种类型只告警一次；严格模式（GAKUMAS_STRICT_EFFECTS=1）下不会走到这里。"""

    effect_type = str(effect.get('effectType') or '')
    if effect_type not in UNKNOWN_EFFECT_TYPES_SEEN:
        UNKNOWN_EFFECT_TYPES_SEEN.add(effect_type)
        logger.warning('考试效果类型 %r 没有对应效果器，已按持续效果兜底挂载（effect id=%r, source=%r）', effect_type, effect.get('id'), source)
    context.register_timed_effect(effect, source)
