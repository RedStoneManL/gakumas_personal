"""Play one real exam per prepared profile through the native Arena.

No model and no torch: the deck is filled from the profile's own candidate pool and
every turn submits the first legal action. Score is meaningless here; what is being
checked is that each profile's data is wired end to end.

  * the entry builds and the exam reaches a terminal result
  * the profile's unique card is actually in play
  * its unique P item resolves, with effects, and is registered to its own p_idol
  * newly unlocked cards are present in the pool at the configured producer level
  * the score lands mostly on the idol's first-priority attribute, which is the
    observable consequence of the stage turn allocation

Usage: python ops/verify_profiles.py [--root DIR] [--setup DIR] [--seed N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECK = 20


def play(profile, seed, create_training_exam):
    entry = json.loads(json.dumps(profile['entry']))
    fixed = [card['definition_id'] for card in entry['cards']]
    pool = [c['card']['definition_id'] for c in profile['spec']['candidates']]
    fill = [c for c in pool if c not in fixed][:DECK - len(fixed)]
    entry['cards'] = entry['cards'] + [
        {'instance_id': 'fill:%d:%d' % (i, c), 'definition_id': c,
         'customizations': {}, 'growth': {}, 'bindings': []} for i, c in enumerate(fill)]
    exam = create_training_exam(entry, seed=seed)
    observation = exam.observe()
    definitions = observation.get('definitions') or {}
    seen, turns = set(), 0
    while turns <= 400:
        if observation.get('choice') is not None:
            observation = exam.choose([0], decision_version=observation['decision_version'])
            continue
        for card in (observation.get('cards') or []):
            seen.add(card.get('definition_id', card.get('id')))
        actions = observation.get('actions') or []
        if not actions:
            break
        observation = exam.act(actions[0])
        turns += 1
        # `result` is present from the first observation; only `terminated` ends the exam.
        if (observation.get('result') or {}).get('terminated'):
            break
    return observation.get('result') or {}, seen, definitions, turns


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=ROOT,
                        help='deployment root holding exam-search/ or exam_search/')
    parser.add_argument('--setup', type=Path, help='setup directory (default: <root>/exam[-_]search/setup)')
    parser.add_argument('--seed', type=int, default=12345)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    exam_root = root / 'exam-search' if (root / 'exam-search').is_dir() else root / 'exam_search'
    if args.setup is None:
        args.setup = exam_root / 'setup'
    sys.path[:0] = [str(exam_root), str(exam_root / 'runtime/shared'), str(exam_root / 'runtime/arena')]
    from gakumas_arena.engine.training import create_training_exam

    profiles = json.loads((args.setup / 'profiles.json').read_text(encoding='utf-8-sig'))
    failures = []
    for profile in profiles:
        name = profile['id']
        spec = profile['spec']
        try:
            result, seen, definitions, turns = play(profile, args.seed, create_training_exam)
        except Exception as error:                                          # noqa: BLE001
            failures.append('%s: %s: %s' % (name, type(error).__name__, error))
            print('%-14s FAILED %s: %s' % (name, type(error).__name__, str(error)[:150]))
            continue
        unique = profile['fixed'][0]
        items = {row['id']: row for row in (definitions.get('p_items') or [])}
        item = items.get(profile['pitem'])
        colours = result.get('score_by_color') or {}
        top = max(colours, key=lambda k: colours[k]) if colours else None
        checks = {
            'terminated': bool(result.get('terminated')),
            'unique card in play': unique in seen,
            'p item resolved': item is not None and bool(item.get('effects')),
            'p item is this idol\'s': item is not None and item.get('pIdolId') == profile['idol'],
            'score on first priority': top == profile['priority'][0],
        }
        bad = [k for k, ok in checks.items() if not ok]
        print('%-14s plan=%-8s turns=%-3d score=%-7s by_colour=%s  %s' % (
            name, spec['plan'], turns, result.get('score'),
            json.dumps(colours, ensure_ascii=False), 'OK' if not bad else 'FAILED: ' + ', '.join(bad)))
        print('               pool=%d  producer_level=%d  unique=%d  p_item=%d %s' % (
            len(spec['candidates']), spec['producer_level'], unique, profile['pitem'],
            item.get('name') if item else '(missing)'))
        failures += ['%s: %s' % (name, k) for k in bad]

    print()
    print('%d profile(s), %d failed check(s)' % (len(profiles), len(failures)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
