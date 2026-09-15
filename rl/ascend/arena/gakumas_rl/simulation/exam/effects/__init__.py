"""考试效果器入口。"""

from .lesson_value import resolve_lesson_effect_value
from .registry import EXAM_EFFECT_REGISTRY, STRICT_EFFECTS_ENV, UnknownExamEffectTypeError, apply_exam_effect, strict_effects_enabled

__all__ = [
    'EXAM_EFFECT_REGISTRY',
    'STRICT_EFFECTS_ENV',
    'UnknownExamEffectTypeError',
    'apply_exam_effect',
    'resolve_lesson_effect_value',
    'strict_effects_enabled',
]
