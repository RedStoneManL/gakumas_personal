"""卡牌操作效果器。"""

from __future__ import annotations

from typing import Any

from ..ids import ExamEffect
from .context import ExamEffectContext


CARD_OPERATION_EFFECT_TYPES = {
    ExamEffect.CARD_CREATE_ID,
    ExamEffect.CARD_CREATE_SEARCH,
    ExamEffect.CARD_DUPLICATE,
    ExamEffect.CARD_MOVE,
    ExamEffect.CARD_UPGRADE,
}

FORCE_PLAY_EFFECT_TYPES = {
    ExamEffect.FORCE_PLAY_CARD_SEARCH,
    ExamEffect.FORCE_PLAY_CARD_SEARCH_WITH_COST,
}


def apply_card_operation(context: ExamEffectContext, effect: dict[str, Any], source: str) -> None:
    """执行造卡、复制、移动、升级等卡牌操作。"""

    context.apply_card_operation(effect)


def apply_force_play(context: ExamEffectContext, effect: dict[str, Any], source: str) -> None:
    """强制使用检索到的卡。

    - `ExamForcePlayCardSearch`：「…をコストを消費せず使用」，不支付费用；
    - `ExamForcePlayCardSearchWithCost`：「…を選択し、コストを消費して使用」，支付费用，因此只从
      当前费用可支付的候选里挑选；
    - 两者都不占用本回合的スキルカード使用数。

    再演（绑定型附魔）发动时 `context.resolving_enchant_card` 即被绑定的卡，用它解析
    `p_card_search-target_is_self-*` 这类 `isSelf` / `Target` 检索。
    """

    effect_type = str(effect.get('effectType') or '')
    pay_cost = effect_type == ExamEffect.FORCE_PLAY_CARD_SEARCH_WITH_COST
    bound_card = context.resolving_enchant_card
    acting_card = bound_card if bound_card is not None else context.current_card
    selection = context.search_cards(
        str(effect.get('produceCardSearchId') or ''),
        acting_card=acting_card,
        target_card=bound_card,
    )
    candidates = list(selection.selected)
    if pay_cost:
        candidates = [card for card in candidates if context.card_cost_affordable(card)]
    if not candidates:
        return
    pick_limit = context.effect_pick_limit(effect)
    if pick_limit is not None and pick_limit < len(candidates):
        if str(effect.get('pickRangeType') or '') == 'ProducePickRangeType_Random':
            candidates = context.random_choice(candidates, pick_limit)
        else:
            candidates = context.rank_card_selection_pool(candidates)[:pick_limit]
    for card in candidates:
        context.force_play_card(card, pay_cost=pay_cost, source=source)
        if context.terminated:
            break
