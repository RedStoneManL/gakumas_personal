"""体力效果器。"""

from __future__ import annotations

from ..ids import ExamEffect, ExamPhase
from ..scoring import ceil_int
from .context import ExamEffectContext


STAMINA_EFFECT_TYPES = {
    ExamEffect.STAMINA_DAMAGE,
    ExamEffect.STAMINA_REDUCE,
    ExamEffect.STAMINA_REDUCE_FIX,
    ExamEffect.STAMINA_RECOVER,
    ExamEffect.STAMINA_RECOVER_FIX,
    ExamEffect.STAMINA_RECOVER_MULTIPLE,
}


def apply_stamina_effect(context: ExamEffectContext, effect: dict[str, Any], source: str) -> None:
    """处理体力扣减与回复。"""

    effect_type = str(effect.get('effectType') or '')
    if effect_type == ExamEffect.STAMINA_REDUCE_FIX:
        # 「体力消費n」：费用型，穿透元気直接扣体力（§4.4 / §9；录像：ときめきのいっぱい 体力消費2 在元気 19 时体力 26→24）。
        context.spend_stamina(0.0, force_value=context.direct_value(effect), phase_type=ExamPhase.STAMINA_REDUCE, status_change_origin=source)
        return
    if effect_type == ExamEffect.STAMINA_REDUCE:
        # 「最大体力の n% 分体力消費」：同样穿透元気，消耗量向上取整。
        amount = ceil_int(context.max_stamina * context.ratio_value(effect))
        context.spend_stamina(0.0, force_value=float(amount), phase_type=ExamPhase.STAMINA_REDUCE, status_change_origin=source)
        return
    if effect_type == ExamEffect.STAMINA_DAMAGE:
        # 「体力減少n」（Pアイテム/トラブル）：是否先扣元気为 §15-12 未決；默认按 gakumas-core 走 normal 费用（元気优先）。
        force = context.scoring_rules.stamina_damage_penetrates_genki
        context.spend_stamina(
            0.0 if force else context.direct_value(effect),
            force_value=context.direct_value(effect) if force else 0.0,
            phase_type=ExamPhase.STAMINA_REDUCE,
            status_change_origin=source,
        )
        return
    if context.has_timed_effect(ExamEffect.STAMINA_RECOVER_RESTRICTION):
        return
    if effect_type in {ExamEffect.STAMINA_RECOVER, ExamEffect.STAMINA_RECOVER_FIX}:
        context.stamina = min(context.max_stamina, context.stamina + context.direct_value(effect))
    elif effect_type == ExamEffect.STAMINA_RECOVER_MULTIPLE:
        context.stamina = min(context.max_stamina, context.stamina + context.max_stamina * context.ratio_value(effect))
