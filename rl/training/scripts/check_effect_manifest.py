"""Validate every pinned effect row against the encoder manifest, without simulation."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from gakumas_training.arena_adapter.environment import ensure_arena, arena_version
from gakumas_training.arena_adapter.mechanisms import mechanical
from gakumas_training.encoding.graph import _canonical, _compile_definition


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arena-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = ensure_arena(args.arena_root)
    from gakumas_arena.env import get_repository
    repo = get_repository()
    report = {'schema': 'training-effect-manifest-check/1', 'tables': {}, 'errors': [],
              'scope': 'row schemas and semantic operation labels; no execution-equivalence claim'}
    for table, type_key in [('ProduceEffect', 'produceEffectType'), ('ProduceExamEffect', 'effectType')]:
        rows = repo.load_table(table).rows
        types = set()
        for row in rows:
            types.add(row.get(type_key))
            try:
                _compile_definition(_canonical({'table': table, 'id': row['id'], 'data': mechanical(row)}))
            except Exception as error:
                report['errors'].append({'table': table, 'id': row['id'], 'error': str(error)})
        report['tables'][table] = {'rows': len(rows), 'types': len(types)}
    report['passed'] = not report['errors']
    report['arena_version'] = arena_version(root)
    manifest = Path(__file__).resolve().parents[1] / 'gakumas_training/encoding/semantic_manifest.json'
    report['semantic_manifest_sha256'] = sha256(manifest.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
