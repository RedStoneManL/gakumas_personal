"""Whole-produce starting cards, directly from ProduceInitialDeck master rows.

The standalone examination builder fills a practice deck with sampled cards;
those cards are not acquisitions and must never appear in a produce run.
"""
from copy import deepcopy


def reserved_memory_card_ids(runtime):
    """Unique memory cards cannot occur in produce offers, including before grant.

    Official help memory-memory-produce explicitly reserves all equipped unique
    memory cards for the whole produce run, rather than only while owned.
    """
    from gakumas_rl.idol_config import resolve_produce_card_row
    loadout = runtime.idol_loadout
    if loadout is None:
        return set()
    result = set()
    for memory in loadout.memories:
        spec = memory.produce_card
        if spec is None:
            continue
        row = resolve_produce_card_row(runtime.repository, spec.card_id, loadout, spec.upgrade_count)
        if row is not None and row.get('noDeckDuplication'):
            result.add(row['id'])
    return result


def build_hif_initial_deck(runtime):
    from gakumas_rl.idol_config import _load_memory_deck_rows, resolve_produce_card_row

    repo, loadout = runtime.repository, runtime.idol_loadout
    if loadout is None:
        raise ValueError('HIF produce starting deck requires an idol loadout')
    matches = [row for row in repo.load_table('ProduceInitialDeck').rows
               if row.get('produceId') == runtime.scenario.produce_id
               and row.get('examEffectType') == loadout.stat_profile.exam_effect_type]
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous HIF ProduceInitialDeck master mapping')
    master = repo.exam_initial_decks.first(matches[0]['examInitialDeckId'])
    if master is None:
        raise ValueError('Missing HIF initial deck master row')
    ids = list(master.get('produceCardIds') or [])
    levels = list(master.get('produceCardUpgradeCounts') or [0] * len(ids))
    if len(ids) != len(levels):
        raise ValueError('HIF initial deck card/upgrade count mismatch')
    deck = []
    for card_id, level in zip(ids, levels):
        row = resolve_produce_card_row(repo, card_id, loadout, int(level))
        if row is None:
            raise ValueError(f'Missing HIF initial card: {card_id}@{level}')
        # Repeated basic cards are distinct physical copies, not deduplicated.
        deck.append(deepcopy(row))
    unique_id = loadout.stat_profile.unique_produce_card_id
    if unique_id:
        row = resolve_produce_card_row(repo, unique_id, loadout, 0)
        if row is None:
            raise ValueError(f'Missing idol starting card: {unique_id}')
        if not any(card['id'] == row['id'] for card in deck):
            deck.append(deepcopy(row))
    for row in _load_memory_deck_rows(repo, loadout):
        # Official memory help: equipping the same unique card more than once
        # still grants one card. Keep configured order for equal-time grants.
        if row.get('noDeckDuplication') and any(card['id'] == row['id'] for card in deck):
            continue
        deck.append(deepcopy(row))
    seen = set()
    for card in deck:
        if card.get('noDeckDuplication') and card['id'] in seen:
            raise ValueError(f'Duplicate unique starting card: {card["id"]}')
        seen.add(card['id'])
    return deck
