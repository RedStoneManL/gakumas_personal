#!/usr/bin/env python3
"""Create a portable source snapshot for the independent, executable trainer.

Only reviewed source/data directories are included. The Ascend target also
includes one explicitly frozen checkpoint and the portable observation dashboard.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import os
import sys
import tempfile
import zipfile

import build_bundle as base


TRAINING_RULES = base.DEFAULT_RULES[:10] + (
    base.IncludeRule('rl/training/pyproject.toml', 'training/pyproject.toml'),
    base.IncludeRule('rl/training/README.md', 'training/README.md'),
    base.IncludeRule('rl/training/MODEL_CONTRACT.md', 'training/MODEL_CONTRACT.md'),
    base.IncludeRule('rl/training/ACCEPTANCE.md', 'training/ACCEPTANCE.md'),
    base.IncludeRule('rl/training/gakumas_training', 'training/gakumas_training', ('.py', '.json')),
    *(base.IncludeRule('rl/training/colab/' + name, 'colab/' + name) for name in (
        'bootstrap.py', 'preflight.py', 'persistence.py', 'run_training.py', 'process_utils.py', 'performance.py',
        'migrate_run.py', 'runtime_control.py', 'notebook_session.py', 'HIF_Training.ipynb')),
    base.IncludeRule('rl/training/colab/configs', 'configs', ('.json',)),
    base.IncludeRule('rl/training/colab/README.md', 'README.md'),
    base.IncludeRule('rl/training/colab/LOADOUTS_AND_COURSES.md', 'LOADOUTS_AND_COURSES.md'),
    base.IncludeRule('rl/training/colab/RESEARCH_POOL.md', 'RESEARCH_POOL.md'),
    *(base.IncludeRule('rl/training/colab/validation/' + name, 'validation/' + name) for name in (
        'pitem-mapping-coverage.json', 'card-drink-mapping-coverage.json',
        'research-inventory.json', 'support-mapping-audit.json', 'policy-topology-optimization.json')),
)


def validator(workspace):
    path = workspace / 'rl/training/colab/bootstrap.py'
    spec = importlib.util.spec_from_file_location('training_bundle_bootstrap', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.validate_zip_archive


def build(workspace: Path, output: Path, *, target='colab'):
    rules = TRAINING_RULES
    if target == 'ascend':
        rules = tuple(r for r in rules if r.destination != 'README.md' and not r.destination.startswith('arena/')) + (
            base.IncludeRule('rl/ascend/arena', 'arena', base.TEXT_SOURCE_SUFFIXES + ('.toml', '')),
            base.IncludeRule('rl/ascend/README.md', 'README.md'),
            base.IncludeRule('rl/ascend/scripts', 'ascend', ('.py', '.sh', '.txt')),
            base.IncludeRule('rl/ascend/configs', 'ascend/configs', ('.json',)),
            base.IncludeRule('rl/ascend/source-import.json', 'ascend/source-import.json'),
            base.IncludeRule('rl/ascend/full-arena-import.json', 'ascend/full-arena-import.json'),
            base.IncludeRule('rl/ascend/dashboard-import.json', 'ascend/dashboard-import.json'),
            base.IncludeRule('rl/ascend/checkpoints/provenance.json', 'checkpoints/provenance.json'),
            base.IncludeRule('rl/ascend/checkpoints/latest.pt', 'checkpoints/latest.pt'),
            base.IncludeRule('rl/ascend/dashboard', 'dashboard', ('.py', '.js', '.html', '.css', '.json', '.md', '.zip')),
            base.IncludeRule('rl/ascend/exam_search', 'exam-search', base.TEXT_SOURCE_SUFFIXES + ('',)),
            base.IncludeRule('rl/ascend/ACCEPTANCE.md', 'ACCEPTANCE.md'),
            base.IncludeRule('rl/ascend/PORTING.md', 'PORTING.md'),
            base.IncludeRule('rl/ascend/validation', 'validation', ('.json',)),
            base.IncludeRule('rl/ascend/tests', 'ascend/tests', ('.py',)),
            base.IncludeRule('rl/training/tests', 'training/tests', ('.py',)),
        )
    elif target != 'colab':
        raise ValueError('Unknown bundle target')
    sources = base.collect_sources(workspace, rules)
    if sum(source.size for source in sources.values()) > base.MAX_UNCOMPRESSED_BYTES:
        raise base.BundleError('Bundle exceeds uncompressed size limit')
    required = {'colab/HIF_Training.ipynb', 'colab/run_training.py',
                'colab/persistence.py', 'colab/preflight.py', 'colab/process_utils.py', 'colab/performance.py', 'configs/full_produce.json',
                'configs/full_produce_mixed.json', 'configs/exam_score.json',
                'configs/full_produce_setup_mixed.json', 'configs/full_produce_select.json',
                'configs/research_inventory.json'}
    if missing := required - set(sources):
        raise base.BundleError(f'Missing training entry points: {sorted(missing)}')
    output = output.resolve()
    if output in {s.path.resolve() for s in sources.values()}:
        raise base.BundleError('Output would overwrite an input')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=output.name + '.', suffix='.tmp', dir=output.parent)
    os.close(fd)
    temporary = Path(temporary)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            records = [base._copy_source(archive, name, source) for name, source in sources.items()]
            manifest = {
                'schema': 'hif-colab-training/1',
                'training_enabled': True,
                'target': target,
                'tasks': ['full_produce', 'exam_score'] + (['joint_search'] if target == 'ascend' else []),
                'default_config': 'configs/full_produce_setup_mixed.json',
                'default_total_hours': 24,
                'default_session_hours': 8,
                'checkpoint_included': target == 'ascend',
                'checkpoint_usage': 'Search weights and Adam for a new run; not full-produce initialization' if target == 'ascend' else None,
                'files': [{key: row[key] for key in ('path', 'size', 'sha256')} for row in records],
            }
            archive.writestr(base._zip_info('manifest.json'), base.canonical_json(manifest))
        with zipfile.ZipFile(temporary) as archive:
            validator(workspace)(archive)
        # A changing source tree is never silently presented as one snapshot.
        current = base.collect_sources(workspace, rules)
        if list(current) != list(sources):
            raise base.BundleError('Source inventory changed during packaging')
        for source in sources.values():
            base._read_stable(source)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    result = {'zip': str(output), 'size_bytes': output.stat().st_size,
              'sha256': base._sha256_file(output), 'files': len(records),
              'unpacked_bytes': sum(row['size'] for row in records),
              'schema': manifest['schema']}
    output.with_suffix('.sha256').write_text(result['sha256'] + '  ' + output.name + '\n', encoding='utf-8')
    output.with_suffix('.json').write_bytes(base.canonical_json(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--target', choices=('colab', 'ascend'), default='colab')
    args = parser.parse_args()
    workspace = args.workspace.resolve(strict=True)
    if args.verify:
        with zipfile.ZipFile(args.verify) as archive:
            validator(workspace)(archive)
        result = {'verified': str(args.verify), 'sha256': base._sha256_file(args.verify)}
    else:
        output = args.output or workspace / f'rl/training/artifacts/{args.target}/gakumas-{args.target}-training.zip'
        result = build(workspace, output, target=args.target)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
