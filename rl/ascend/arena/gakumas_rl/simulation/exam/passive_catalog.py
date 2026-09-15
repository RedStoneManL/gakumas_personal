"""已有证据指向的最小实况触发集合；ID/规则来自固定主数据，不来自 OCR 猜测。"""

from __future__ import annotations

from dataclasses import dataclass

MEMORY_PREFIX = ('memory_ability-p_memory_skill-common-hatsuboshi_idol_festival-'
                 'p_trigger-start_audition-for_hif_memory-exam_status_enchant-'
                 'exam_turn_timer-exam_status_enchant-01-')


@dataclass(frozen=True)
class PassiveDefinition:
    """白名单同时固定触发和结果效果，主数据变化时不能静默扩充语义。"""
    enchant_id: str
    source_kind: str
    source_definition_id: str
    trigger_id: str
    effect_ids: tuple[str, ...]
    count: int | None


def _memory(card: str, number: str, effects: tuple[str, ...]) -> PassiveDefinition:
    return PassiveDefinition(f'enchant-p_ef-hif_memory-{card}-enc01', 'memory',
        f'{MEMORY_PREFIX}{number}-001', f'e_trigger-exam_card_play_after-p_card_search-target-{card}-for_hif_memory-0_1',
        effects, 1)


_DRAW_ACTION = ('e_effect-exam_playable_value_add-01', 'e_effect-exam_card_draw-0001')
_REMOVE_SLEEPY = ('e_effect-exam_card_move-p_card_search-deck_grave-p_card-00-acc-0_002-lost-random-1_1',)
PASSIVE_DEFINITIONS = tuple(sorted((
    _memory('p_card-01-men-2_041', '069', _DRAW_ACTION),
    _memory('p_card-01-act-2_059', '072', _DRAW_ACTION),
    _memory('p_card-01-act-2_001', '003', _REMOVE_SLEEPY),
    _memory('p_card-01-men-2_104', '034', _REMOVE_SLEEPY),
    PassiveDefinition('enchant-p_card-01-men-2_038-enc01', 'card', 'p_card-01-men-2_038',
        'e_trigger-exam_card_play-p_card_search-active_skill-playing-0_1', ('e_effect-exam_lesson_buff-0001',), None),
    PassiveDefinition('enchant-p_item_effect_01-3-342-0-enc01', 'item', 'pitem_01-3-342-0',
        'e_trigger-exam_card_play-lesson_buff_up-13',
        ('e_effect-exam_playable_value_add-01', 'e_effect-exam_lesson_buff-0004'), 1),
), key=lambda item: item.enchant_id))
PASSIVE_IDS = tuple(item.enchant_id for item in PASSIVE_DEFINITIONS)
PASSIVE_BY_ID = {item.enchant_id: item for item in PASSIVE_DEFINITIONS}
PASSIVE_FEATURE_NAMES = ('present', 'remaining_turns', 'unlimited_turns', 'remaining_count',
                         'unlimited_count', 'applied_turn_marker', 'last_fired_turn', 'never_fired')
