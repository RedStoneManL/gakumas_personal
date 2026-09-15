"""再演（ExamStatusEnchantEncore）效果器。

主数据语义（Label_ExamStatusEnchantEncore）：
「再演是，在训练中，仅限第一次使用自身时发动的效果。在之后的本次训练中，当满足指定条件时，
每回合 1 次为限，自身会再次使用（不消耗技能卡花费值）。」

实现：把 `produceExamStatusEnchantId` 指向的附魔挂成绑定到当前出牌卡的 `TriggeredEnchant`，
`effectCount` = 最多发动次数、`effectTurn=-1` = 直到课程结束、`effectValue1=1` = ターン内 1 回まで。
附魔发动时其效果为 `ExamForcePlayCardSearch`（检索 `isSelf`/`Target`），由 card_operation 效果器
通过 `context.resolving_enchant_card` 找回绑定卡并免费再使用。
"""

from __future__ import annotations

from typing import Any

from .context import ExamEffectContext


def apply_status_enchant_encore(context: ExamEffectContext, effect: dict[str, Any], source: str) -> None:
    """把再演附魔绑定到当前出牌卡；同一张卡只在第一次使用时挂载。"""

    enchant_row = context.exam_status_enchant_row(str(effect.get('produceExamStatusEnchantId') or ''))
    if not enchant_row:
        return
    card = context.current_card
    if card is None:
        # 再演只能由技能卡自身触发；没有出牌上下文时无法绑定，直接忽略。
        return
    enchant_id = str(enchant_row.get('id') or '')
    if context.has_bound_enchant(enchant_id, card.uid):
        # 再使用自身时会再次走到本效果：只保留首次挂载，不刷新次数。
        return
    remaining_turns = int(effect.get('effectTurn') or 0)
    if remaining_turns < 0:
        remaining_turns = None
    elif remaining_turns == 0:
        remaining_turns = 1
    remaining_count = int(effect.get('effectCount') or 0)
    if remaining_count <= 0:
        remaining_count = None
    # effectValue1 = 每回合最多发动次数；主数据里恒为 1（ターン内1回まで）。
    once_per_turn = int(effect.get('effectValue1') or 1) <= 1
    context.register_bound_enchant(
        enchant_row,
        bound_card=card,
        remaining_turns=remaining_turns,
        remaining_count=remaining_count,
        once_per_turn=once_per_turn,
        source=source,
    )
