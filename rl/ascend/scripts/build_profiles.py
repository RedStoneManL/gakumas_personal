"""Rebuild exam-search/setup/profiles.json from master data.

The original generator lives in the upstream Windows workspace and was never part of
this bundle, so the prepared profiles could only be edited by hand. Every field that
depends on the card pool is in fact derived, and the derivation is recovered here and
pinned by ``--selftest``: regenerating the five shipped profiles at their own producer
level and ban list must reproduce the committed file exactly, field for field.

Derivations (each verified against all five shipped profiles):

  candidate pool   catalog cards with sourceType != 'pIdol', plan in {own, free},
                   unlockPlv <= producer_level, upgraded (or the single rarity 'T'
                   sleep card), minus the ban list. Idol-unique cards never draft;
                   a profile's own fixed cards enter through spec.fixed_cards.
  candidate row    supply = 1 for game-unique cards, else null; family = name without
                   the '+'; required_level = unlockPlv; source_type = sourceType.
  guidance rules   one row per fixed + candidate card. max_guidance is the upgraded
                   card's maxCustomizeCount in ProduceCard.yaml (NOT the number of
                   customization tracks: 52 cards differ). tracks expands
                   availableCustomizations through the catalog's customization
                   definitions. pIdol-source cards carry no tracks.
  switch relations every ProduceCardConversion pair touching the pool; a member out of
                   pool gets candidate_key null.
  mutual exclusions the subset whose two members are both in the pool.
  stage / scoring  from the idol's attribute priority, which is itself the descending
                   parameter order of that idol card's ProduceExamBattleConfig:
                   turnCounts 4/3/2, firstTurns .85/.15/0, criteria .45/.30/.25,
                   scoring.values (indexed vocal, dance, visual) 4397/2997/2223.
  stamina          hp = the idol card's produceStamina + 13, as in all five shipped
                   profiles.

Everything else in a spec is scene policy (size rules, memory, scenarios, coverage,
support pool, guidance prices) and is carried over from a shipped profile of the same
plan; the plan fixes the pool, so those fields are identical within a plan.

Usage:
  python scripts/build_profiles.py --selftest
  python scripts/build_profiles.py --level 80 --open-restrictions --add sena-campus \
      --output exam_search/setup/profiles.json
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / 'exam_search' / 'setup'
RAW = ROOT / 'arena' / 'data' / 'raw' / 'gakumasu-diff'

PLAN_BY_TYPE = {'ProducePlanType_Plan1': 'sense', 'ProducePlanType_Plan2': 'logic',
                'ProducePlanType_Plan3': 'anomaly'}
# Rank-ordered by the idol's attribute priority (first = strongest).
TURN_COUNTS = (4, 3, 2)
FIRST_TURNS = (0.85, 0.15, 0)
CRITERIA = (0.45, 0.3, 0.25)
SCORE_VALUES = (4397, 2997, 2223)
ATTRIBUTES = ('vocal', 'dance', 'visual')
STAMINA_BONUS = 13
# Prima Stella cards are deck-slot exemptions registered to idol cards that none of
# these profiles has unlocked; they stay out of every pool regardless of level.
PRIMA_STELLA_IDS = [829, 830, 831, 834, 835, 836, 837, 838, 853, 854]

# 十王星南 / JUO SENA, character jsna. Campus mode!! is i_card-jsna-3-002:
# ProducePlanType_Plan1 (sense), ExamParameterBuff (good_condition), produceStamina 31,
# produce card p_card-01-ido-3_108 (catalog 478/479), P item pitem_01-3-079 (204/205),
# exam battle config vivo-03 -> visual 354 > vocal 292 > dance 239.
NEW_PROFILES = {
    'sena-campus': {
        'id': 'sena-campus',
        'name': '星南 · Campus mode!!',
        'master_id': 'i_card-jsna-3-002',
        'idol': 70,
        'plan': 'sense',
        'strategy': 'good_condition',
        'recommended_effect': 'goodConditionTurns',
        'fixed': [479],
        'pitem': 205,
        'hp': 44,
        'priority': ['visual', 'vocal', 'dance'],
        'prima_stella_unlocked': False,
        'removed_prima_stella_ids': [],
        'score_scale': 150000,
        # Drink pools follow the plan, not the idol: this is the sense pool, identical
        # to hiro-hif's. Inherited from the template too, but stated so it is reviewable.
        'drink_pool': [1, 2, 3, 4, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22],
        'template': 'hiro-hif',
    },
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def normalize(name):
    """The catalog folds full-width punctuation; fold both sides before matching."""
    return unicodedata.normalize('NFKC', name).strip()


def master_cards():
    """(normalized name, upgradeCount, plan) -> master id, upgrade and maxCustomizeCount,
    plus master_id -> raw name for the conversion relations."""
    text = (RAW / 'ProduceCard.yaml').read_text(encoding='utf-8')
    table, names = {}, {}
    for match in re.finditer(r'^- id: (\S+)\n(.*?)(?=^- id: |\Z)', text, re.S | re.M):
        body = match.group(2)
        upgrade = int(search(body, r'upgradeCount: (\d+)', '0'))
        name = search(body, r'^  name: (.+)$', '', flags=re.M).strip()
        plan = PLAN_BY_TYPE.get(search(body, r'planType: (\S+)', ''), 'free')
        table[(normalize(name), upgrade, plan)] = {
            'master_id': match.group(1), 'upgrade': upgrade,
            'max_customize': int(search(body, r'maxCustomizeCount: (\d+)', '0'))}
        names.setdefault(match.group(1), name)
    return table, names


def search(text, pattern, default, flags=0):
    found = re.search(pattern, text, flags)
    return found.group(1) if found else default


def conversions():
    """Every (before, after) master pair from ProduceCardConversion.yaml, in file order."""
    text = (RAW / 'ProduceCardConversion.yaml').read_text(encoding='utf-8')
    return [(m.group(1), m.group(2)) for m in re.finditer(
        r'^- beforeProduceCardId: (\S+)\n  afterProduceCardId: (\S+)', text, re.M)]


class Builder:
    def __init__(self, shipped):
        catalog = read_json(SETUP / 'catalog.json')
        self.cards = {row['id']: row for row in catalog['cards']}
        self.customizations = {str(row['id']): row for row in catalog['customizations']}
        self.master, self.master_names = master_cards()
        self.conversions = conversions()
        # The shipped profiles already pin master id, upgrade count and customize cap for
        # every card they draft; ten catalog names cannot be matched back to the master
        # rows at all (the upstream generator carried hand-written aliases for them), so
        # the shipped rows are authoritative and the name match only fills in new cards.
        self.pinned = {}
        for profile in shipped:
            for card_id, rule in profile['spec']['guidance']['card_rules'].items():
                self.pinned.setdefault(int(card_id), {
                    'master_id': rule['master_id'], 'upgrade': rule['master_upgrade_count'],
                    'max_customize': rule['max_guidance']})
        self.by_master = {}
        for row in catalog['cards']:
            entry = self.link(row['id'])
            if entry:
                self.by_master.setdefault((entry['master_id'], entry['upgrade']), row['id'])

    def link(self, card_id):
        if card_id in self.pinned:
            return self.pinned[card_id]
        row = self.cards[card_id]
        return self.master.get((normalize(row['name']), 1 if row.get('upgraded') else 0, row.get('plan')))

    def pool(self, plan, level, banned):
        banned = set(banned)
        out = []
        for row in self.cards.values():
            if row.get('sourceType') == 'pIdol' or row['id'] in banned:
                continue
            if row.get('plan') not in (plan, 'free'):
                continue
            if (row.get('unlockPlv') or 1) > level:
                continue
            if not row.get('upgraded') and row.get('rarity') != 'T':
                continue
            out.append(row['id'])
        return sorted(out)

    def candidate(self, card_id):
        row = self.cards[card_id]
        key = 'draft:card:%d' % card_id
        return {'key': key,
                'card': {'instance_id': key, 'definition_id': card_id,
                         'customizations': {}, 'growth': {}, 'bindings': []},
                'name': row['name'], 'rarity': row['rarity'],
                'family': row['name'].rstrip('+'), 'unique': bool(row.get('unique')),
                'supply': 1 if row.get('unique') else None,
                'required_level': row.get('unlockPlv') or 1,
                'source_type': row.get('sourceType')}

    def card_rule(self, card_id):
        row = self.cards[card_id]
        entry = self.link(card_id)
        if entry is None:
            raise KeyError('no master entry for catalog card %d (%s)' % (card_id, row['name']))
        available = [] if row.get('sourceType') == 'pIdol' else (row.get('availableCustomizations') or [])
        tracks = {}
        for name in available:
            definition = self.customizations[name]
            tracks[name] = {'max': definition['max'],
                            'prices': [int(v) for v in str(definition['price']).split(',')],
                            'definition': definition}
        return {'max_guidance': entry['max_customize'], 'tracks': tracks,
                'master_id': entry['master_id'], 'master_upgrade_count': entry['upgrade'],
                'required_level': row.get('unlockPlv') or 1, 'rarity': row['rarity']}

    def relations(self, pool):
        """switch_relations (any member in pool) and mutual_exclusions (both in pool)."""
        in_pool = set(pool)
        switch, mutual = [], []
        for before, after in self.conversions:
            members, keys = [], []
            touched = False
            for master in (before, after):
                card_id = None
                for upgrade in (0, 1):
                    found = self.by_master.get((master, upgrade))
                    if found is not None and found in in_pool:
                        card_id = found
                        break
                key = 'draft:card:%d' % card_id if card_id is not None else None
                if key:
                    touched = True
                    keys.append(key)
                members.append({'master_id': master, 'name': self.master_name(master),
                                'candidate_key': key})
            if not touched:
                continue
            relation = {'id': '%s|%s' % (before, after), 'candidate_keys': keys, 'members': members}
            switch.append(relation)
            if len(keys) == 2:
                mutual.append(relation)
        return mutual, switch

    def master_name(self, master_id):
        return self.master_names.get(master_id, master_id)


def build(builder, identity, template, level, banned):
    pool = builder.pool(identity['plan'], level, banned)
    fixed = list(identity['fixed'])
    spec = copy.deepcopy(template['spec'])
    entry = copy.deepcopy(template['entry'])
    priority = identity['priority']
    rank = {name: index for index, name in enumerate(priority)}

    fixed_cards = [{'instance_id': '%s:fixed:%d' % (identity['id'], card),
                    'definition_id': card, 'customizations': {}, 'growth': {},
                    'bindings': []} for card in fixed]
    mutual, switch = builder.relations(pool)
    # Every card that would otherwise draft but does not, with why. A ban wins over the
    # level note; Prima Stella ids never reach here because they are idol-unique cards,
    # which the pool rule drops on sourceType alone.
    in_pool = set(pool)
    banned_set = set(banned)
    removed = [{'id': card['id'], 'name': card['name'],
                'required_level': card.get('unlockPlv') or 1,
                'reason': 'user exclusion' if card['id'] in banned_set else 'P level > %d' % level}
               for card in sorted(builder.cards.values(), key=lambda row: row['id'])
               if card.get('sourceType') != 'pIdol'
               and card.get('plan') in (identity['plan'], 'free')
               and (card.get('upgraded') or card.get('rarity') == 'T')
               and card['id'] not in in_pool]

    spec.update(
        fixed_cards=fixed_cards,
        candidates=[builder.candidate(card) for card in pool],
        mutual_exclusions=mutual, switch_relations=switch,
        exclusions={'card_ids': list(banned), 'removed': removed},
        banned_card_ids=list(banned), producer_level=level,
        # Free slots follow this profile's own fixed cards, not the template's: a one-card
        # idol inheriting hiro-hif's two-card bounds would be allowed to finish at 17.
        min_free_slots=spec['min_cards'] - len(fixed_cards),
        max_free_slots=spec['max_cards'] - len(fixed_cards),
        candidate_scope=re.sub(r'PLv <= \d+', 'PLv <= %d' % level, spec['candidate_scope']),
        profile_id=identity['id'], plan=identity['plan'],
        strategy=identity['strategy'], recommended_effect=identity['recommended_effect'])
    spec['guidance'] = dict(spec['guidance'],
                            card_rules={str(card): builder.card_rule(card) for card in fixed + pool})

    entry.update(preset='%s-generalist-support-no-prima' % identity['id'],
                 cards=fixed_cards,
                 resources={'stamina': identity['hp'], 'max_stamina': identity['hp'], 'drinks': []},
                 p_items=[identity['pitem']] + entry['p_items'][1:])
    context = dict(entry['context'], idol_id=identity['idol'], plan=identity['plan'])
    context['scoring'] = dict(context['scoring'],
                              values=[SCORE_VALUES[rank[a]] for a in ATTRIBUTES])
    context['stage'] = dict(context['stage'],
                            turnCounts={a: TURN_COUNTS[rank[a]] for a in priority},
                            firstTurns={a: FIRST_TURNS[rank[a]] for a in priority},
                            criteria={a: CRITERIA[rank[a]] for a in priority})
    entry['context'] = context

    profile = {key: value for key, value in identity.items() if key != 'template'}
    profile['entry'] = entry
    profile['spec'] = spec
    missing = (set(template) - set(profile)) | (set(profile) - set(template))
    if missing:
        raise KeyError('profile %s field set differs from the template: %s'
                       % (identity['id'], sorted(missing)))
    return profile


def identity_of(profile):
    return {key: copy.deepcopy(value) for key, value in profile.items()
            if key not in ('entry', 'spec')}


def order_like(sample, profile):
    """Emit keys in the shipped order so a diff of the file stays readable."""
    keys = [k for k in sample if k in profile] + [k for k in profile if k not in sample]
    return {k: profile[k] for k in keys}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--selftest', action='store_true',
                        help='regenerate the shipped profiles unchanged and compare')
    parser.add_argument('--level', type=int, help='producer level for every profile')
    parser.add_argument('--open-restrictions', action='store_true',
                        help='drop hand-picked card bans; keep only Prima Stella exemptions')
    parser.add_argument('--add', action='append', default=[], choices=sorted(NEW_PROFILES),
                        help='append a new profile')
    parser.add_argument('--output', type=Path, help='write the result here')
    args = parser.parse_args(argv)

    shipped = read_json(SETUP / 'profiles.json')
    by_id = {profile['id']: profile for profile in shipped}
    builder = Builder(shipped)

    if args.selftest:
        failures = []
        for profile in shipped:
            spec = profile['spec']
            rebuilt = build(builder, identity_of(profile), profile,
                            spec['producer_level'], spec['banned_card_ids'])
            for section in ('entry', 'spec'):
                for key in sorted(set(profile[section]) | set(rebuilt[section])):
                    if profile[section].get(key) != rebuilt[section].get(key):
                        failures.append('%s.%s.%s' % (profile['id'], section, key))
        print('selftest: %d profile(s), %d mismatching field(s)' % (len(shipped), len(failures)))
        for name in failures:
            print('   MISMATCH', name)
        return 1 if failures else 0

    if args.level is None:
        parser.error('--level is required unless --selftest')
    banned = list(PRIMA_STELLA_IDS) if args.open_restrictions else None
    result = []
    for profile in shipped:
        bans = banned if banned is not None else profile['spec']['banned_card_ids']
        result.append(order_like(profile, build(builder, identity_of(profile), profile, args.level, bans)))
    for name in args.add:
        identity = dict(NEW_PROFILES[name])
        template = by_id[identity['template']]
        # Anything not spelled out for a new profile is a scene-level field the plan
        # already fixes (drink pool, score scale); inherit it rather than leave a hole.
        for key, value in identity_of(template).items():
            identity.setdefault(key, copy.deepcopy(value))
        bans = banned if banned is not None else template['spec']['banned_card_ids']
        result.append(order_like(template, build(builder, identity, template, args.level, bans)))

    print('built %d profiles at producer level %d' % (len(result), args.level))
    for profile in result:
        spec = profile['spec']
        print('  %-14s plan=%-8s candidates=%-4d mutual=%-2d switch=%-2d banned=%d' % (
            profile['id'], spec['plan'], len(spec['candidates']),
            len(spec['mutual_exclusions']), len(spec['switch_relations']), len(spec['banned_card_ids'])))
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('wrote', args.output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
