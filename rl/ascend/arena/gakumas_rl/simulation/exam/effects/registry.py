"""考试效果器注册表。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import os
from typing import Any

from ..ids import ExamEffect
from .context import ExamEffectContext

EffectHandler = Callable[[ExamEffectContext, dict[str, Any], str], None]

STRICT_EFFECTS_ENV = 'GAKUMAS_STRICT_EFFECTS'
"""环境变量：设为 1/true/yes/on 时，遇到没有精确/前缀效果器的 effectType 直接抛错而不是走兜底。"""


class UnknownExamEffectTypeError(KeyError):
    """严格模式下遇到未注册 effectType 时抛出。"""


def strict_effects_enabled() -> bool:
    """读取 GAKUMAS_STRICT_EFFECTS 环境变量。"""

    return str(os.environ.get(STRICT_EFFECTS_ENV) or '').strip().lower() in {'1', 'true', 'yes', 'on'}


class EffectHandlerRegistry:
    """把主数据 effectType 映射到对应效果器。"""

    def __init__(self) -> None:
        self._exact_handlers: dict[str, EffectHandler] = {}
        self._prefix_handlers: list[tuple[str, EffectHandler]] = []
        self._fallback_handler: EffectHandler | None = None

    def register(self, effect_types: Iterable[str], handler: EffectHandler) -> None:
        """注册一组精确 effectType。"""

        for effect_type in effect_types:
            self._exact_handlers[str(effect_type)] = handler

    def register_one(self, effect_type: str, handler: EffectHandler) -> None:
        """注册单个精确 effectType。"""

        self._exact_handlers[str(effect_type)] = handler

    def register_prefix(self, prefix: str, handler: EffectHandler) -> None:
        """注册按前缀命中的效果器。"""

        self._prefix_handlers.append((str(prefix), handler))

    def register_fallback(self, handler: EffectHandler) -> None:
        """注册兜底效果器，用于暂未精确分类的持续效果。"""

        self._fallback_handler = handler

    def resolve(self, effect_type: str) -> EffectHandler | None:
        """返回精确或前缀命中的效果器；没有命中返回 None（不含兜底）。"""

        handler = self._exact_handlers.get(str(effect_type))
        if handler is not None:
            return handler
        for prefix, prefix_handler in self._prefix_handlers:
            if str(effect_type).startswith(prefix):
                return prefix_handler
        return None

    def is_registered(self, effect_type: str) -> bool:
        """判断 effectType 是否有精确/前缀效果器（兜底不算）。"""

        return self.resolve(effect_type) is not None

    def registered_effect_types(self) -> set[str]:
        """返回所有精确注册的 effectType（不含前缀命中）。"""

        return set(self._exact_handlers)

    def dispatch(self, runtime: Any, effect: dict[str, Any], source: str) -> None:
        """根据 effectType 调用匹配的效果器。"""

        context = ExamEffectContext(runtime)
        effect_type = str(effect.get('effectType') or '')
        handler = self.resolve(effect_type)
        if handler is not None:
            handler(context, effect, source)
            return
        if strict_effects_enabled():
            raise UnknownExamEffectTypeError(
                f'未注册的考试效果类型 {effect_type!r}（effect id={effect.get("id")!r}, source={source!r}）；'
                f'请在 gakumas_rl/simulation/exam/effects/ 里实现效果器，或取消 {STRICT_EFFECTS_ENV}。'
            )
        if self._fallback_handler is not None:
            self._fallback_handler(context, effect, source)


def _build_registry() -> EffectHandlerRegistry:
    """集中装配内置效果器，避免运行时硬编码长分支。"""

    from . import (
        aggressive,
        block,
        card_operation,
        delayed_effect,
        duration_resource,
        encore,
        enthusiastic,
        fallback,
        gimmick,
        grow_effect,
        item_fire_limit,
        lesson_buff,
        lesson_score,
        parameter_buff,
        review,
        scalar_resource,
        simple,
        stamina,
        status_enchant,
        timed,
    )

    registry = EffectHandlerRegistry()
    registry.register(timed.TIMED_EFFECT_TYPES, timed.apply_timed_effect)
    registry.register_one(ExamEffect.STATUS_ENCHANT, status_enchant.apply_status_enchant)
    registry.register_one(ExamEffect.STATUS_ENCHANT_ENCORE, encore.apply_status_enchant_encore)
    registry.register_one(ExamEffect.EFFECT_TIMER, delayed_effect.apply_delayed_effect)
    registry.register_one(ExamEffect.ADD_GROW_EFFECT, grow_effect.apply_grow_effect)
    registry.register(card_operation.CARD_OPERATION_EFFECT_TYPES, card_operation.apply_card_operation)
    registry.register(card_operation.FORCE_PLAY_EFFECT_TYPES, card_operation.apply_force_play)
    registry.register(duration_resource.DURATION_RESOURCE_TYPES, duration_resource.apply_duration_resource)
    registry.register(scalar_resource.SCALAR_RESOURCE_TYPES, scalar_resource.apply_scalar_resource)
    registry.register(simple.SIMPLE_EFFECT_TYPES, simple.apply_simple_effect)
    registry.register(stamina.STAMINA_EFFECT_TYPES, stamina.apply_stamina_effect)
    registry.register(block.BLOCK_EFFECT_TYPES, block.apply_block_effect)
    registry.register(aggressive.AGGRESSIVE_EFFECT_TYPES, aggressive.apply_aggressive_effect)
    registry.register(review.REVIEW_EFFECT_TYPES, review.apply_review_effect)
    registry.register(parameter_buff.PARAMETER_BUFF_EFFECT_TYPES, parameter_buff.apply_parameter_buff_effect)
    registry.register(lesson_buff.LESSON_BUFF_EFFECT_TYPES, lesson_buff.apply_lesson_buff_effect)
    registry.register_one(ExamEffect.ITEM_FIRE_LIMIT_ADD, item_fire_limit.apply_item_fire_limit_add)
    registry.register(gimmick.GIMMICK_EFFECT_TYPES, gimmick.apply_gimmick_effect)
    registry.register_one(ExamEffect.GIMMICK_ENTHUSIASTIC, enthusiastic.apply_enthusiastic_effect)
    registry.register(simple.EXTRA_SIMPLE_EFFECT_TYPES, simple.apply_extra_simple_effect)
    registry.register_prefix(ExamEffect.LESSON_PREFIX, lesson_score.apply_lesson_score_effect)
    registry.register_one(ExamEffect.MULTIPLE_LESSON_BUFF_LESSON, lesson_score.apply_lesson_score_effect)
    registry.register_one(ExamEffect.MULTIPLE_ENTHUSIASTIC_LESSON, lesson_score.apply_lesson_score_effect)
    registry.register_fallback(fallback.apply_fallback_timed_effect)
    return registry


EXAM_EFFECT_REGISTRY = _build_registry()


def apply_exam_effect(runtime: Any, effect: dict[str, Any], source: str) -> None:
    """应用一条考试效果。"""

    EXAM_EFFECT_REGISTRY.dispatch(runtime, effect, source)
