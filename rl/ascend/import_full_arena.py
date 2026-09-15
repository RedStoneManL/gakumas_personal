"""Freeze the current full Arena and master data into this reviewable port."""
import hashlib
import json
from pathlib import Path
import shutil
import sys


def main():
    here = Path(__file__).resolve().parent
    workspace = here.parents[1]
    sys.path.insert(0, str(workspace/'rl/hif-colab'))
    import build_bundle as base
    destination = here/'arena'
    if destination.exists():
        raise FileExistsError('Refusing to overwrite the frozen Arena')
    rules = base.DEFAULT_RULES[:10]
    inventory = base.collect_sources(workspace, rules)
    records = []
    for name, source in inventory.items():
        target = here/name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('wb') as stream:
            digest = base._read_stable(source, stream)
        records.append({'path': name, 'source': source.source, 'size': source.size,
                        'sha256': digest})
    for source in inventory.values():
        base._read_stable(source)
    (here/'full-arena-import.json').write_text(json.dumps({'source': 'third_party/gakumas_arena',
        'files': records}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'files': len(records), 'bytes': sum(r['size'] for r in records)}))


if __name__ == '__main__':
    main()
