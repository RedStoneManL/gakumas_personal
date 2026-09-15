"""显式卡牌补选边界：枚举全部合法目标，不排序代选、不抽样。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import CARD_ZONE_MAP, MOVE_POSITION_MAP


class UnsupportedSelection(ValueError):
    """当前边界未覆盖此主数据选择语义。"""


@dataclass(frozen=True)
class CardSelectionBoundary:
    """已暂停页面的一次明确选择，当前只覆盖固定选一张。"""
    effect_id: str
    required_zones: tuple[str, ...]
    destination: str
    cards: tuple[Any, ...]


def card_selection_boundary(runtime: Any, effect_id: str) -> CardSelectionBoundary:
    """复用引擎检索区域与过滤器，但不截断为默认第一个目标。"""
    effect = runtime.repository.exam_effect_map.get(effect_id)
    if (effect is None or effect.get('effectType') != 'ProduceExamEffectType_ExamCardMove'
            or effect.get('pickRangeType') != 'ProducePickRangeType_Select'
            or effect.get('pickCountType') != 'ProducePickCountType_Unknown'
            or effect.get('pickCountReferenceProduceCardSearchId')
            or effect.get('pickCountMin') != 1 or effect.get('pickCountMax') != 1):
        raise UnsupportedSelection(effect_id)
    search = runtime.card_searches.first(str(effect.get('produceCardSearchId') or ''))
    if search is None or search.get('isSelf') or search.get('orderType') == 'ProduceCardOrderType_Random':
        raise UnsupportedSelection(effect_id)
    zone = CARD_ZONE_MAP.get(search.get('cardPositionType'))
    zones = {'deck': ('deck',), 'deck_grave': ('deck', 'discard'), 'hand': ('hand',),
             'hold': ('hold',), 'lost': ('lost',), 'not_lost': ('deck', 'hand', 'discard', 'hold')}.get(zone)
    destination = MOVE_POSITION_MAP.get(effect.get('movePositionType'))
    if zones is None or destination not in {'hand', 'hold', 'grave'}:
        raise UnsupportedSelection(effect_id)
    pool = runtime._pool_for_search(search, acting_card=None, target_card=None)
    cards = tuple(card for card in pool if runtime._matches_card_search(card, search))
    return CardSelectionBoundary(effect_id, zones, destination, cards)


def resolve_card_selection(runtime: Any, effect_id: str, selected_uid: int) -> None:
    """离线独立边界：移动指定卡并沿用既有移动相位；不是宏动作续跑器。"""
    if runtime.observation_only:
        raise RuntimeError('Observed selection requires an actual result snapshot')
    boundary = card_selection_boundary(runtime, effect_id)
    target = next((card for card in boundary.cards if card.uid == selected_uid), None)
    if target is None:
        raise ValueError('selected card is outside the eligible pool')
    runtime._move_runtime_card(target, boundary.destination)
