"""Build an explicit, compositional HIF research memory/support inventory.

This defines an experiment, not a claim that its memories exist in an account
or that a server-side memory lottery can produce every combination.
"""
from collections import Counter
from dataclasses import asdict
import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
START = 'ProduceMemoryProduceCardPhaseType_ProduceStart'
MID = 'ProduceMemoryProduceCardPhaseType_EndAuditionMid'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def component(spec, prefix):
    wire = json.loads(canonical(asdict(spec)))
    digest = hashlib.sha256(canonical(wire).encode()).hexdigest()[:24]
    identity = f'research:{prefix}:{digest}'
    wire['memory_id'] = identity
    return {'memory_id': identity, 'spec': wire}


def build_inventory(repository, *, phase_consumes_slot=True, producer_level=76):
    from gakumas_rl.idol_config import _resolve_support_card_level, apply_card_customizations
    from gakumas_rl.loadout import ProduceMemoryCardSpec, ProduceMemorySpec
    from gakumas_arena.produce.golden import GoldenProduceBridge
    from gakumas_arena.produce.customization_bridge import resolve_customizations
    from gakumas_arena.produce.memory_generation import _ability_rows
    bridge = GoldenProduceBridge(repository)
    supports = [{'support_card_id': row['id'], 'level': _resolve_support_card_level(row, 1000)}
                for row in sorted(repository.support_cards.rows, key=lambda r: r['id'])]
    ordinary, special = _ability_rows(repository)
    gold, hif, seen_skills = [], [], set()
    for row in sorted(ordinary, key=lambda r: (r['skill_id'], r['id'], r['level'])):
        key = row['skill_id'], row['level']
        if row['rarity'] != 'SkillRarity_Sr' or key in seen_skills:
            continue
        seen_skills.add(key)
        gold.append(component(ProduceMemorySpec(ability_ids=(row['id'],),
                    ability_levels=(row['level'],)), 'gold'))
    for row in sorted(special, key=lambda r: (r['id'], r['level'])):
        hif.append(component(ProduceMemorySpec(ability_ids=(row['id'],),
                   ability_levels=(row['level'],)), 'hif'))

    cards, card_audit = [], []
    eligible_rarities = {'ProduceCardRarity_R': 2, 'ProduceCardRarity_Sr': 1,
                        'ProduceCardRarity_Ssr': 1}
    for row in sorted(repository.load_table('ProduceCard').rows, key=lambda r: (r['id'], r['upgradeCount'])):
        if (row['upgradeCount'] != 1 or row['rarity'] not in eligible_rarities
                or row.get('originIdolCardId') or row.get('originSupportCardId')
                or row.get('originCharacterId') or row.get('originPrimaStellaIdolCardId')
                or row.get('libraryHidden') or row.get('isConversion')
                or row.get('unlockProducerLevel', 0) > producer_level):
            continue
        # Ordinary active/mental cards; no idol, support, trouble or contest-only cards.
        if row['id'].split('-')[2] not in ('act', 'men'):
            continue
        budget = min(eligible_rarities[row['rarity']], int(row.get('maxCustomizeCount') or 0))
        options = list(row.get('produceCardCustomizeIds') or [])
        sequences = [()]
        for n in range(1, budget + 1):
            sequences.extend(product(options, repeat=n))
        # R/SR offer early and mid acquisition. SSR uses mid acquisition in this
        # first research pool; the Arena wire's permissiveness is not evidence
        # of a real start-acquisition SSR memory.
        phases = (MID,) if row['rarity'] == 'ProduceCardRarity_Ssr' else (START, MID)
        count = 0
        for phase in phases:
            for sequence in sequences:
                if len(sequence) + int(phase_consumes_slot and phase == START) > eligible_rarities[row['rarity']]:
                    continue
                try:
                    applied = apply_card_customizations(repository, row, tuple(sequence))
                except ValueError:
                    continue  # Invalid repeated customization level; not a candidate.
                # Fail on unmapped mechanics; never silently truncate the pool.
                native_id = bridge.definition_id('card', applied)
                _, residual, _ = resolve_customizations(repository, applied,
                    bridge.by_id['card'][native_id], bridge.native_customizations)
                if residual:
                    raise ValueError(f'Unexpected residual growth for research card {row["id"]}: {residual}')
                spec = ProduceMemorySpec(produce_card=ProduceMemoryCardSpec(
                    row['id'], 1, tuple(sequence), phase))
                cards.append(component(spec, 'card'))
                count += 1
        card_audit.append({'card_id': row['id'], 'name': row['name'], 'rarity': row['rarity'],
                           'plan': row['planType'], 'variants': count})
    inventory = {'schema_version': 'gakumas-setup-inventory/1', 'supports': supports,
        'memories': [], 'memory_components': {'cards': cards, 'gold_factors': gold, 'hif_abilities': hif},
        'provenance': {'ruleset': 'hif-research-gold-compositional/1',
            'account_inventory_claimed': False, 'server_generation_feasibility_claimed': False,
            'producer_level': producer_level, 'ordinary_factors_per_memory': 3,
            'ordinary_factor_rarity': 'SkillRarity_Sr', 'ordinary_factors_distinct_within_memory': True,
            'hif_abilities_per_memory': '0 or 1; selected independently of carried card',
            'card_upgrade_count': 1,
            'customization_budget': {'ProduceCardRarity_R': 2, 'ProduceCardRarity_Sr': 1, 'ProduceCardRarity_Ssr': 1},
            'initial_hand_customization_consumes_one_slot': True,
            'produce_start_acquisition_consumes_one_slot': phase_consumes_slot,
            'acquisition_phases': {'R': [START, MID], 'Sr': [START, MID], 'Ssr': [MID]},
            'cross_plan_carried_cards_excluded': True,
            'support_levels': 'maximum legal rarity level; all local definitions',
            'ordinary_factor_deduplication': 'same ProduceSkill ID and exact level',
            'source_tables': ['SupportCard', 'ProduceCard', 'ProduceCardCustomize',
                              'ProduceCardGrowEffect', 'MemoryAbility', 'ProduceSkill'],
            'source_tables_sha256': {table: hashlib.sha256(canonical(repository.load_table(table).rows).encode()).hexdigest()
                                    for table in ('SupportCard', 'ProduceCard', 'ProduceCardCustomize', 'MemoryAbility', 'ProduceSkill')}}}
    audit = {'schema': 'hif-research-inventory-audit/1', 'inventory_sha256': hashlib.sha256(canonical(inventory).encode()).hexdigest(),
        'support_count': len(supports), 'gold_factor_count': len(gold), 'hif_ability_count': len(hif),
        'card_identity_count': len(card_audit), 'card_variant_count': len(cards),
        'card_plans': dict(Counter(row['plan'] for row in card_audit)), 'cards': card_audit,
        'scope': inventory['provenance']}
    return inventory, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arena-root', type=Path, default=ROOT / 'third_party/gakumas_arena')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'configs/research_inventory.json')
    parser.add_argument('--phase-consumes-slot', action='store_true', default=True,
                        help='User-defined research rule: start acquisition costs one slot (always enabled).')
    args = parser.parse_args()
    sys.path.insert(0, str(args.arena_root.resolve()))
    from gakumas_arena.env import get_repository
    inventory, audit = build_inventory(get_repository(), phase_consumes_slot=args.phase_consumes_slot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    report = Path(__file__).parent / 'validation/research-inventory.json'
    report.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({key: value for key, value in audit.items() if key not in ('cards', 'scope')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
