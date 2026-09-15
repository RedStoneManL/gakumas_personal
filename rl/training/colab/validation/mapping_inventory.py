"""Read-only candidate/identity audit; no game stepping, model, or training.

Run with Arena's dependency environment and --arena-root. This audit establishes
identity coverage of the configured source pools, not effect equivalence or
official reward probabilities.
"""
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def event_rewards(event):
    effects = list(event.get('effects', []))
    for option in event.get('options', []):
        for field in ('effects', 'success_effects', 'fail_effects'):
            effects.extend(option.get(field, []))
    for effect in effects:
        yield from effect.get('produceRewards', [])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arena-root', type=Path, required=True)
    p.add_argument('--config', type=Path, default=Path(__file__).parents[1] / 'configs/full_produce_mixed.json')
    p.add_argument('--output', type=Path, default=Path(__file__).parent)
    args = p.parse_args(argv)
    arena = args.arena_root.resolve()
    sys.path.insert(0, str(arena))
    from gakumas_arena.env import get_repository, make_produce_env
    from gakumas_arena.produce.golden import GoldenProduceBridge, ProduceEventLibrary, DATA
    from gakumas_arena.produce.loadout_handoff import thaw_loadout
    from gakumas_arena.produce.research import install_hif_research_profile
    from gakumas_arena.produce.card_switches import normalize_initial_deck
    repo = get_repository()
    bridge, events = GoldenProduceBridge(repo), ProduceEventLibrary(repo)
    config = json.loads(args.config.read_text(encoding='utf8'))
    pool = config['task_config']['loadout_pool']
    common = {'created_at_utc': datetime.now(timezone.utc).isoformat(),
              'config_sha256': sha(args.config), 'config_name': args.config.name,
              'scope': 'Current five configured HIF loadouts at PLv76; source-pool identity coverage only',
              'limitations': ['No effect-by-effect semantic equivalence claim',
                  'No official reward probability claim',
                  'Conditional rewards are included as a conservative source closure; not all coexist in one run',
                  'No game stepping or training performed'],
              'source_sha256': {path.relative_to(arena).as_posix(): sha(path) for path in [
                  arena / 'gakumas_arena/produce/golden.py',
                  arena / 'gakumas_arena/produce/sampling.py',
                  arena / 'gakumas_rl/simulation/produce/runtime.py',
                  DATA / 'p_items.json', DATA / 'skill_cards.json', DATA / 'p_drinks.json']},
              'master_table_sha256': {name: hashlib.sha256(json.dumps(repo.load_table(name).rows,
                  ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                  for name in ('IdolCard', 'ProduceItem', 'ProduceCard', 'ProduceDrink',
                               'ProduceEventSupportCard', 'ProduceStepEventDetail', 'ProduceEffect')}}
    item_sources = defaultdict(set)
    cards, drinks = {}, {}
    card_sources, drink_sources = defaultdict(set), defaultdict(set)
    profile_records = []

    def add_card(row, source):
        key = f"{row['id']}@{int(row.get('upgradeCount') or 0)}"
        cards[key] = row
        card_sources[key].add(source)

    def add_drink(row, source):
        drinks[row['id']] = row
        drink_sources[row['id']].add(source)

    for profile in pool:
        name, loadout = profile['name'], profile['loadout']
        idol = repo.load_table('IdolCard').first(loadout['idol_card_id'])
        for field in ('beforeProduceItemId', 'afterProduceItemId'):
            if idol.get(field):
                item_sources[idol[field]].add(f'{name}:idol:{field}')
        explicit_cards, explicit_drinks = set(), set()
        for support, level in zip(loadout['support_card_ids'], loadout['support_card_levels']):
            for eid in events.support_event_ids(support, level):
                for reward in event_rewards(events.event(eid)):
                    kind, rid = reward.get('resourceType'), reward.get('resourceId')
                    if kind == 'ProduceResourceType_ProduceItem':
                        item_sources[rid].add(f'{name}:support:{support}:{eid}')
                    elif kind == 'ProduceResourceType_ProduceCard':
                        explicit_cards.add(rid)
                    elif kind == 'ProduceResourceType_ProduceDrink':
                        explicit_drinks.add(rid)
        records = []
        for scenario in ('hif_selection', 'hif_final'):
            env = make_produce_env(scenario=scenario, loadout=thaw_loadout(loadout), seed=0)
            rt = env.runtime
            install_hif_research_profile(rt, profile.get('research_config', {}))
            rt.reset()
            normalize_initial_deck(rt)
            source = f'{name}:{scenario}'
            selection = rt._selection_card_pool()
            for row in selection:
                add_card(row, source + ':selection_pool')
                for upgrade in (0, 1):
                    variant = rt._lookup_card_upgrade_row(row['id'], upgrade)
                    if variant:
                        add_card(variant, source + ':selection_or_shop_upgrade')
            for row in rt.deck:
                add_card(row, source + ':initial_deck')
                for upgrade in (0, 1):
                    variant = rt._lookup_card_upgrade_row(row['id'], upgrade)
                    if variant:
                        add_card(variant, source + ':initial_deck_upgrade')
            for rid in explicit_cards:
                for upgrade in (0, 1):
                    row = rt._lookup_card_upgrade_row(rid, upgrade)
                    if row:
                        add_card(row, source + ':selected_support_reward')
            shop = rt._shop_drink_pool()
            # Exact membership expression used by HifSamplingKernel.candidates.
            sampled = [row for row in repo.produce_drinks.rows
                       if not row.get('libraryHidden') and row.get('planType') in rt._allowed_plan_types()]
            for row in shop:
                add_drink(row, source + ':consult_shop')
            for row in sampled:
                add_drink(row, source + ':hif_reward_interval_candidates')
            for rid in explicit_drinks:
                add_drink(repo.produce_drinks.first(rid), source + ':selected_support_reward')
            records.append({'scenario': scenario, 'selection_rows': len(selection),
                'initial_deck_rows': len(rt.deck), 'consult_drinks': len(shop),
                'hif_reward_interval_drinks': len(sampled),
                'hif_drinks_above_plv76': [r['id'] for r in sampled if int(r.get('unlockProducerLevel') or 0) > 76],
                'hif_drinks_with_support_origin': [r['id'] for r in sampled if r.get('originSupportCardId')]})
        profile_records.append({'name': name, 'idol_card_id': idol['id'],
            'plan': idol.get('planType'), 'producer_level': loadout['producer_level'], 'pools': records})
    for item_id in ('pitem_01-3-266-0', 'pitem_01-3-267-0', 'pitem_02-3-268-0',
                    'pitem_02-3-269-0', 'pitem_03-3-270-0', 'pitem_03-3-271-0', 'pitem_00-3-265-0'):
        item_sources[item_id].add('hif:baton_or_badge_reward')

    def mapped(kind, row, sources):
        result = {'id': row['id'], 'name': row['name'], 'sources': sorted(sources)}
        if kind == 'card':
            result['upgradeCount'] = int(row.get('upgradeCount') or 0)
        try:
            result.update(mapped=True, native_id=bridge.definition_id(kind, row))
        except ValueError as error:
            result.update(mapped=False, error=str(error))
        return result

    item_rows, excluded = [], []
    for item_id, sources in sorted(item_sources.items()):
        row = repo.produce_items.first(item_id)
        if not row.get('isExamEffect'):
            excluded.append({'id': item_id, 'reason': 'non-exam item; Golden exam mapping not needed'})
        else:
            item_rows.append(mapped('item', row, sources))
    future = mapped('item', repo.produce_items.first('pitem_01-3-305-0'), ['future support s_card-3-0087'])
    future.update(current_config_uses_support=False,
        impact='Changing to s_card-3-0087 can require a new explicit native mapping; not a blocker for current five profiles')
    item_report = {**common, 'schema': 'gakumas-current-pitem-mapping-coverage/1',
        'profiles': profile_records, 'exam_item_count': len(item_rows),
        'mapped_count': sum(row['mapped'] for row in item_rows),
        'items': item_rows, 'excluded_non_exam_items': excluded, 'future_configuration_limitations': [future]}
    card_rows = [mapped('card', row, card_sources[key]) for key, row in sorted(cards.items())]
    drink_rows = [mapped('drink', row, drink_sources[key]) for key, row in sorted(drinks.items())]
    other_report = {**common, 'schema': 'gakumas-current-card-drink-mapping-coverage/1',
        'profiles': profile_records,
        'additional_limitations': [
            'Selection pool is inspected at each scenario initialization with real configured loadout and switches; later owned/excluded/legend constraints can shrink it',
            'HIF-final pool initialization here is a static membership probe, not a claim of a natural selection-to-final carryover',
            'Consult shop applies producer-level and support-origin filters; HIF reward/interval drink membership uses its own broader current implementation',
            'Card upgrade 0/1 closure covers normal upgrades and interval offers; customizations and effect execution are outside this identity audit'],
        'card_variant_count': len(card_rows), 'mapped_card_variants': sum(r['mapped'] for r in card_rows),
        'drink_count': len(drink_rows), 'mapped_drinks': sum(r['mapped'] for r in drink_rows),
        'cards': card_rows, 'drinks': drink_rows}
    args.output.mkdir(parents=True, exist_ok=True)
    for filename, report in [('pitem-mapping-coverage.json', item_report),
                             ('card-drink-mapping-coverage.json', other_report)]:
        (args.output / filename).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'exam_items': len(item_rows), 'mapped_items': sum(r['mapped'] for r in item_rows),
        'card_variants': len(card_rows), 'mapped_cards': sum(r['mapped'] for r in card_rows),
        'drinks': len(drink_rows), 'mapped_drinks': sum(r['mapped'] for r in drink_rows),
        'missing_current': [r for r in (*item_rows, *card_rows, *drink_rows) if not r['mapped']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
