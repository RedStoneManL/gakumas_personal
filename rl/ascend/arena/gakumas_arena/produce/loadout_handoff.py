"""Freeze every accepted loadout input before the selection/final handoff."""
from copy import deepcopy
from dataclasses import asdict, replace
import json

from gakumas_rl.interfaces.service import LoadoutConfig
from gakumas_rl.loadout import ProduceMemoryCardSpec, ProduceMemorySpec


def _memory_from_wire(value):
    if isinstance(value, (str, ProduceMemorySpec)):
        return value
    if not isinstance(value, dict):
        raise TypeError('Frozen loadout memory must be an ID or a memory record')
    value = deepcopy(value)
    card = value.get('produce_card')
    if isinstance(card, dict):
        card['customize_ids'] = tuple(card.get('customize_ids', ()))
        value['produce_card'] = ProduceMemoryCardSpec(**card)
    for key in ('ability_ids', 'ability_levels', 'exam_battle_produce_card_ids',
                'exam_battle_produce_item_ids', 'allowed_character_ids'):
        if key in value:
            value[key] = tuple(value[key])
    return ProduceMemorySpec(**value)


def thaw_loadout(config):
    """Accept historical dictionaries and new JSON-safe normalized snapshots."""
    if isinstance(config, LoadoutConfig):
        return deepcopy(config)
    config = deepcopy(config)
    config['memories'] = tuple(_memory_from_wire(m) for m in config.get('memories', ()))
    for key in ('produce_card_conversion_after_ids', 'support_card_ids', 'support_card_levels',
                'challenge_item_ids'):
        if key in config:
            config[key] = tuple(config[key])
    return LoadoutConfig(**config)


def freeze_loadout(scenario, original, resolved):
    """Preserve config controls and the actual resolved kit; never a preset alias.

    Store before research installation, which may update the frozen conversion
    list through the existing card-switch hook. Rebuilding for the final scenario
    then correctly installs final-only Prima Stella skills.
    """
    from ..env import make_loadout_config
    config = asdict(make_loadout_config(loadout=original, scenario=scenario))
    if resolved is not None:
        config.update(idol_card_id=resolved.idol_card_id, producer_level=resolved.producer_level,
            idol_rank=resolved.idol_rank, dearness_level=resolved.dearness_level,
            use_after_item=resolved.use_after_item, potential_level=resolved.potential_level,
            prima_stella_level=resolved.prima_stella_level, assist_mode=resolved.assist_mode,
            exam_score_bonus_multiplier=resolved.exam_score_bonus_multiplier,
            auto_support_cards=False, support_card_level=None,
            support_card_ids=[c.support_card_id for c in resolved.support_cards],
            support_card_levels=[c.support_card_level for c in resolved.support_cards],
            challenge_item_ids=list(resolved.extra_produce_item_ids),
            produce_card_conversion_after_ids=[c.after_card_id for c in resolved.produce_card_conversions],
            memories=[asdict(m) for m in resolved.memories])
    return json.loads(json.dumps(config, ensure_ascii=False, allow_nan=False))


def handoff_loadout(scenario, supplied, memory):
    """A handoff owns its kit. Legacy records at least own idol identity.

    Preserve the existing full-snapshot precedence over a supplied loadout. If a
    legacy record has no full snapshot, allow matching explicit account settings
    but reject a different idol rather than merging incompatible kits.
    """
    if memory is None:
        return supplied
    from ..env import get_repository, make_loadout_config
    from .golden import ProduceBridgeError
    if not memory.idol_card_id:
        raise ProduceBridgeError('Selection memory requires idol_card_id to restore its kit')
    frozen = memory.metadata.get('loadout_config')
    if frozen is not None:
        config = thaw_loadout(frozen)
        if not config.idol_card_id:
            config = replace(config, idol_card_id=memory.idol_card_id)
        if config.idol_card_id != memory.idol_card_id:
            raise ProduceBridgeError('Selection memory idol and frozen loadout identity differ')
        return config
    if supplied is not None:
        config = asdict(make_loadout_config(loadout=supplied, scenario=scenario))
        if config['idol_card_id'] != memory.idol_card_id:
            raise ProduceBridgeError('Explicit loadout conflicts with legacy selection memory idol')
    else:
        config = asdict(LoadoutConfig(idol_card_id=memory.idol_card_id, auto_support_cards=False))
    config['dearness_level'] = memory.dearness_level
    supports = memory.support_card_states
    if supports:
        config.update(auto_support_cards=False, support_card_level=None,
            support_card_ids=[c['support_card_id'] for c in supports],
            support_card_levels=[c['support_card_level'] for c in supports])
    idol = get_repository().load_table('IdolCard').first(memory.idol_card_id)
    if idol is None:
        raise ProduceBridgeError(f'Unknown selection memory idol: {memory.idol_card_id}')
    carried = {item for item, _ in memory.produce_item_fire_counts}
    before, after = idol.get('beforeProduceItemId'), idol.get('afterProduceItemId')
    if after and after != before and after in carried:
        config['use_after_item'] = True
    elif before in carried:
        config['use_after_item'] = False
    return thaw_loadout(config)
