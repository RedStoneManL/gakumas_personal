"""录像复现钩子：让 `ExamRuntime` 按实机录像的确定性条件运行（仅用于对拍测试）。

录像复现需要固定的：山札顺序（含捨札洗回后的顺序）、每回合属性、每属性的スコアボーナス、
応援/トラブル 与 メモリー アビリティ 的具体内容。这些在正常对局里都是随机/主数据驱动的，
这里用一个可选对象把它们注入运行时，不影响默认行为。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


TurnStartHook = Callable[[Any], None]


@dataclass
class ReplayHooks:
    """`ExamRuntime(replay_hooks=...)` 的钩子集合。所有字段都可省略。"""

    # 初始山札顺序：按 `initial_deck_rows` 的下标（=运行时卡构建顺序）。未列出的卡按原顺序排在后面。
    initial_deck_order: Sequence[int] | None = None
    # 捨札洗回山札时的顺序（同样按构建下标）；每次洗回消费一项，用完后退回随机洗牌。
    reshuffle_orders: Sequence[Sequence[int]] = ()
    # 每回合的属性（'vocal' / 'dance' / 'visual'）；超出长度时沿用最后一项。
    turn_colors: Sequence[str] = ()
    # 各属性的スコアボーナス百分比（例 {'dance': 1794} = 1794%）。
    score_bonus_percent: dict[str, float] = field(default_factory=dict)
    # 忽略主数据里的考场 gimmick（応援/トラブル），改用 `turn_start_hooks`。
    disable_stage_gimmicks: bool = False
    # 回合开始阶段（gimmick 时机、抽牌之前）按回合号执行的钩子：turn → [callable(runtime)]。
    turn_start_hooks: dict[int, list[TurnStartHook]] = field(default_factory=dict)
    # 第 1 回合抽牌后执行的钩子（メモリー アビリティ）。
    memory_hooks: list[TurnStartHook] = field(default_factory=list)
    # 禁用支援卡的随机レッスンサポート（录像里的サポート发动由测试逐回合手动施加）。
    disable_support_card_random_upgrade: bool = True

    def __post_init__(self) -> None:
        self._reshuffle_queue: deque[Sequence[int]] = deque(self.reshuffle_orders)

    def next_reshuffle_order(self) -> Sequence[int] | None:
        """取出下一次洗回山札时应使用的顺序；没有预设时返回 None。"""

        if not self._reshuffle_queue:
            return None
        return self._reshuffle_queue.popleft()

    def turn_color(self, turn: int) -> str | None:
        """返回指定回合的固定属性；未配置时返回 None。"""

        if not self.turn_colors:
            return None
        index = min(max(int(turn) - 1, 0), len(self.turn_colors) - 1)
        return str(self.turn_colors[index])


def reorder_by_build_index(cards: Sequence[Any], order: Sequence[int] | None, index_of: Callable[[Any], int]) -> list[Any]:
    """按构建下标顺序重排卡列表：`order` 里列出的卡先按给定顺序排列，其余保持原相对顺序附在后面。"""

    if not order:
        return list(cards)
    by_index = {index_of(card): card for card in cards}
    ordered: list[Any] = []
    used: set[int] = set()
    for build_index in order:
        card = by_index.get(int(build_index))
        if card is None or int(build_index) in used:
            continue
        ordered.append(card)
        used.add(int(build_index))
    ordered.extend(card for card in cards if index_of(card) not in used)
    return ordered
