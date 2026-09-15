"""Resume a committed joint update, preserving abandoned rollout evidence."""
import json
import os
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
import torch
from .checkpoint import digest, load, json_write, source_version


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def prepare(output, setup, config, arena_hash, device):
    output = Path(output)
    manifest = read(output/'manifest.json')
    model, info = load(output/'latest.pt', device)
    from gakumas_arena.engine.search import search_content_version
    if info['training_config'] != config:
        raise ValueError('Recovery configuration differs from committed checkpoint')
    if info['arena_sha256'] != arena_hash or info['search_version'] != search_content_version():
        raise ValueError('Recovery Arena or search version differs')
    if info['rl_source_sha256'] != source_version() or manifest['rl_source_sha256'] != source_version():
        raise ValueError('Recovery source differs; use a separately audited migration')
    if any(digest(setup/name) != value for name, value in info['setup_sha256'].items()):
        raise ValueError('Recovery setup differs')
    if not all(torch.isfinite(value).all() for value in model.state_dict().values()):
        raise ValueError('Nonfinite checkpoint')
    if 'committed_log_offsets' not in info or 'run_progress' not in info:
        raise ValueError('Checkpoint predates transactional recovery metadata')
    for name, offset in info['committed_log_offsets'].items():
        path = output/name
        if Path(name).name != name or not path.exists() or path.stat().st_size < offset:
            raise ValueError('Committed log is missing or shorter than checkpoint: '+name)
    best = info.get('committed_best')
    if best and digest(output/best['path']) != best['sha256']:
        raise ValueError('Committed best snapshot differs')
    best4=info.get('committed_best4')
    if best4 and digest(output/best4['path'])!=best4['sha256']:
        raise ValueError('Committed Best-of-4 snapshot differs')
    history_path = output/'validation-history.jsonl'
    limit = info['committed_log_offsets'].get(history_path.name, 0)
    history = [json.loads(line) for line in history_path.read_bytes()[:limit].splitlines()] if limit else []
    baseline_path = output/'validation-initial.json'
    baseline = read(baseline_path) if baseline_path.exists() else None
    progress = dict(info['run_progress'])
    progress.update(batches=info['batches'], decisions=info['decisions'])
    return model, info, {'baseline': baseline, 'history': history, 'progress': progress}


def restore_random(info):
    from gakumas_training.device import restore_accelerator_rng
    if info['training_config']['device'].startswith('npu') and not info.get('npu_rng'):
        raise ValueError('Missing NPU RNG state in checkpoint')
    restore_accelerator_rng({'cuda': info.get('cuda_rng', []), 'npu': info.get('npu_rng', [])})
    torch.set_rng_state(info['torch_rng'])
    random.setstate(info['python_rng'])


def commit_recovery(output, info, context):
    output = Path(output)
    backup = output/'recovery-evidence'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True)
    for name in ('latest.pt', 'best.pt', 'best4.pt', 'best4-reference.json', 'progress.json', 'manifest.json'):
        if (output/name).exists():
            shutil.copy2(output/name, backup/name)
    offsets = info['committed_log_offsets']
    archived = {}
    for path in list(output.glob('*.jsonl'))+[output/'progress.log']:
        if not path.exists():
            continue
        offset = offsets.get(path.name, 0)
        if path.stat().st_size > offset:
            with path.open('rb') as stream:
                stream.seek(offset)
                tail = stream.read()
            (backup/(path.name+'.uncommitted')).write_bytes(tail)
            with path.open('r+b') as stream:
                stream.truncate(offset)
            archived[path.name] = len(tail)
    if info.get('committed_best'):
        temp = output/'best.pt.recovery-tmp'
        shutil.copy2(output/info['committed_best']['path'], temp)
        os.replace(temp, output/'best.pt')
    if info.get('committed_best4'):
        temp=output/'best4.pt.recovery-tmp'
        shutil.copy2(output/info['committed_best4']['path'],temp)
        os.replace(temp,output/'best4.pt')
    else:
        # An interrupted first Best-of-4 reference is not a committed baseline.
        for name in ('best4.pt','best4-reference.json'):
            path=output/name
            if path.exists():path.rename(backup/(name+'.uncommitted'))
    audit = {'resumed_at': datetime.now(timezone.utc).isoformat(),
        'checkpoint_batch': info['batches'], 'checkpoint_decisions': info['decisions'],
        'next_seed': info['next_episode_index'], 'search_seed_counter': info['search_seed_counter'],
        'optimizer_restored': True, 'rng_restored': True, 'preserve_original_deadline': True,
        'archived_uncommitted_bytes': archived, 'evidence_backup': str(backup),
        'source_sha256': source_version()}
    json_write(output/'recovery.json', audit)
    manifest = read(output/'manifest.json')
    manifest.setdefault('recoveries', []).append(audit)
    json_write(output/'manifest.json', manifest)
    return audit
