"""完整实测编成到既有 LoadoutConfig 的无损转换；缺失值不使用训练默认。"""

from __future__ import annotations

from gakumas_rl.interfaces.service import LoadoutConfig
from gakumas_rl.loadout import ProduceMemoryCardSpec, ProduceMemorySpec

from .contracts import RunLoadout
from .session import MissingFields


def to_loadout_config(loadout: RunLoadout) -> LoadoutConfig:
    """要求配置读取完整，保留逐卡等级、回忆来源、获得时机与自定义。"""
    required = ('idol_card_id', 'producer_level', 'idol_rank', 'dearness_level',
                'potential_level', 'prima_stella_level', 'use_after_item')
    missing = [f'loadout.{name}' for name in required if getattr(loadout, name) is None]
    if not loadout.supports_complete:
        missing.append('loadout.supports_complete')
    if not loadout.memories_complete:
        missing.append('loadout.memories_complete')
    for support in loadout.supports:
        for field in ('support_card_id', 'level'):
            if getattr(support, field) is None:
                missing.append(f'supports.{support.instance_id}.{field}')
    memories = []
    for memory in loadout.memories:
        for field in ('source_idol_card_id', 'ability_ids', 'ability_levels'):
            if getattr(memory, field) is None:
                missing.append(f'memories.{memory.instance_id}.{field}')
        card = memory.card
        if card is None:
            missing.append(f'memories.{memory.instance_id}.card')
        elif card.definition_id is None or card.upgrade_count is None or card.customize_ids is None:
            missing.append(f'memories.{memory.instance_id}.card.definition_and_variant')
        if memory.acquisition_phase is None:
            missing.append(f'memories.{memory.instance_id}.acquisition_phase')
        if memory.ability_ids is not None and memory.ability_levels is not None and len(memory.ability_ids) != len(memory.ability_levels):
            raise ValueError(f'Memory ability ids and levels must align: {memory.instance_id}')
        if not missing:
            memories.append(ProduceMemorySpec(
                memory_id=memory.instance_id, idol_card_id=memory.source_idol_card_id,
                allowed_character_ids=memory.allowed_character_ids or (),
                produce_card=ProduceMemoryCardSpec(card.definition_id, card.upgrade_count, card.customize_ids,
                    f'ProduceMemoryProduceCardPhaseType_{memory.acquisition_phase}'),
                ability_ids=memory.ability_ids, ability_levels=memory.ability_levels,
            ))
    if missing:
        raise MissingFields(*missing)
    return LoadoutConfig(
        **{name: getattr(loadout, name) for name in required},
        auto_support_cards=False,
        support_card_ids=tuple(support.support_card_id for support in loadout.supports),
        support_card_levels=tuple(support.level for support in loadout.supports),
        memories=tuple(memories),
    )
