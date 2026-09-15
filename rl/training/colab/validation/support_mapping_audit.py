"""Audit native mappings reachable through every real support definition."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gakumas_training.arena_adapter.environment import arena_version, ensure_arena


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--arena-root')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    arena = ensure_arena(args.arena_root)
    from gakumas_arena.env import get_repository
    from gakumas_arena.produce.golden import GoldenProduceBridge
    repository = get_repository()
    bridge = GoldenProduceBridge(repository)
    report = {'scope': 'Identity resolution for support-origin cards and exam items; '
                       'not a claim of full behavioral coverage for every effect.',
              'arena_version': arena_version(arena),
              'support_count': len(repository.support_cards.rows), 'cards': [], 'items': [], 'failures': []}
    for kind, source, destination in [('card', repository.produce_cards.rows, 'cards'),
                                      ('item', repository.produce_items.rows, 'items')]:
        for row in source:
            if not row.get('originSupportCardId') or (kind == 'item' and not row['isExamEffect']):
                continue
            entry = {'master_id': row['id'], 'support_id': row['originSupportCardId'],
                     'master_name': row['name']}
            if kind == 'card':
                entry['upgrade_count'] = row['upgradeCount']
            try:
                entry['native_id'] = bridge.definition_id(kind, row)
                entry['native_name'] = bridge.by_id[kind][entry['native_id']]['name']
                report[destination].append(entry)
            except Exception as error:
                report['failures'].append({**entry, 'kind': kind, 'error': str(error)})
    report['mapped_card_variants'] = len(report['cards'])
    report['mapped_exam_items'] = len(report['items'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('cards', 'items')}, ensure_ascii=False))
    if report['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
