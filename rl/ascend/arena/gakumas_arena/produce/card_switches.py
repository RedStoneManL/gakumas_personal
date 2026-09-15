"""Account card-switch snapshot; never an in-exam transformation button."""
from copy import deepcopy
from dataclasses import replace


def install_card_switches(runtime, settings=None):
    settings = deepcopy(settings if settings is not None else {})
    if not isinstance(settings, dict) or any(type(v) is not bool for v in settings.values()):
        raise ValueError('card_switches must map beforeProduceCardId to a boolean')
    pairs = runtime.repository.load_table('ProduceCardConversion').rows
    known = {r['beforeProduceCardId'] for r in pairs}
    if set(settings)-known:
        raise ValueError(f'Unknown card switch: {sorted(set(settings)-known)}')
    # Reuse the existing loadout conversion engine. Profile construction precedes
    # reset(), so the producer level lives in the loadout rather than state yet.
    from gakumas_rl.idol_config import _resolve_selected_produce_card_conversions
    effective = {spec.before_card_id: True for spec in runtime.idol_loadout.produce_card_conversions}
    effective.update(settings)
    settings = effective
    specs = _resolve_selected_produce_card_conversions(runtime.repository,
        int(runtime.idol_loadout.producer_level), tuple(pair['afterProduceCardId']
            for pair in pairs if settings.get(pair['beforeProduceCardId'], False)))
    runtime.idol_loadout = replace(runtime.idol_loadout, produce_card_conversions=specs)
    if isinstance(getattr(runtime, 'hif_loadout_config', None), dict):
        runtime.hif_loadout_config['produce_card_conversion_after_ids'] = [spec.after_card_id for spec in specs]
    selected, family = {}, {}
    for pair in pairs:
        before, after = pair['beforeProduceCardId'], pair['afterProduceCardId']
        active = after if settings.get(before, False) else before
        selected[before] = selected[after] = active
        family[before] = family[after] = before
    runtime.hif_card_switch_settings = settings
    runtime.hif_card_switch_map = selected
    runtime.hif_card_switch_family = family


def active_card_id(runtime, card_id):
    return getattr(runtime, 'hif_card_switch_map', {}).get(card_id, card_id)


def switched_card_row(runtime, row):
    new_id = active_card_id(runtime, row['id'])
    if new_id == row['id']:
        return deepcopy(row)
    converted = runtime._lookup_card_upgrade_row(new_id, int(row.get('upgradeCount') or 0))
    if converted is None:
        raise ValueError(f'Missing switched card variant: {new_id}@{row.get("upgradeCount",0)}')
    converted = deepcopy(converted)
    # Preserve identity/provenance, not the other card's effect definition.
    for key in ('instance_id','sourceMemoryId','sourceMemoryIdolCardId','source_instance_id'):
        if key in row:
            converted[key] = deepcopy(row[key])
    return converted


def switch_pool(runtime, rows):
    result = {}
    excluded = set(runtime.state.get('excluded_card_ids', []))
    for row in rows:
        row = switched_card_row(runtime, row)
        if (row['id'] not in excluded and int(row.get('unlockProducerLevel') or 0) <= int(runtime.state['producer_level'])):
            result[(row['id'],int(row.get('upgradeCount') or 0))] = row
    return list(result.values())


def normalize_initial_deck(runtime):
    """Freeze configured switch identities before the first public decision."""
    runtime.deck = [switched_card_row(runtime, card) for card in runtime.deck]
    runtime.initial_deck_card_ids = {active_card_id(runtime, cid) for cid in runtime.initial_deck_card_ids}
    runtime._selection_card_pool_cache_key = None
