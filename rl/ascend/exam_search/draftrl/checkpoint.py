import hashlib
import json
import os
import random
import shutil
from pathlib import Path
from datetime import datetime, timezone
import torch
from round2rl.checkpoint import digest, json_write, atomic_replace
from .model import DraftPolicy, MODEL_SCHEMA
from .encoding import ENCODING
from gakumas_training.device import accelerator_rng


def source_version():
    from .source_identity import source_version as fingerprint
    return fingerprint()


def transfer(path, arena_hash, device):
    info = torch.load(path, map_location='cpu', weights_only=True)
    if info.get('model_schema') not in (MODEL_SCHEMA, 'hif-memory-draft-drink-exam-policy/1') or info.get('encoding') not in (ENCODING,'arena-generalist-build-exam/2','arena-generalist-build-exam/1','arena-fixed-entry-drink-supply/1','arena-mixed-plan-sequential-choice/3','arena-mixed-plan-sequential-choice/2','arena-mixed-plan-sequential-choice/1','arena-memory-scenario-deck-guidance-drink-exam/1'):
        raise ValueError('incompatible shared five-phase architecture')
    if info['model_schema'] == MODEL_SCHEMA:
        model = DraftPolicy(**info['model_config'])
        model.load_state_dict(info['model_state'], strict=True)
    else:
        from .migration import migrate
        model = migrate(info, device)
        for name, value in model.state_dict().items():
            old_name = model.legacy_parameter_name(name)
            if old_name is not None and not torch.equal(value.cpu(), info['model_state'][old_name].cpu()):
                raise ValueError('Function-preserving split migration changed an inherited tensor')
    return model.to(device), {'path':str(Path(path).resolve()),'sha256':digest(path),
        'source_arena_sha256':info['arena_sha256'],'current_arena_sha256':arena_hash,
        'source_decisions':info['decisions'],'source_batches':info['batches'],
        'optimizer_reset':False,'optimizer_migration_pending':True,'restore_continuation':False,'all_old_weights_preserved':True,
        'source_encoding':info['encoding'], 'current_encoding':ENCODING,
        'change':'Joint public-history MCTS. Split build/exam into four-block towers with initially identical outputs; inherited Adam moments copied explicitly, new identity blocks fresh. New Arena/catalogue version and new on-policy collection; no old rollout labels reused.'}


def save(path, model, optimizer, **metadata):
    value = {'model_schema': MODEL_SCHEMA, 'encoding': ENCODING, 'model_config': model.config,
        'model_state': model.state_dict(), 'optimizer_state': optimizer.state_dict(),
        'torch_rng': torch.get_rng_state(), 'python_rng': random.getstate(),
        'cuda_rng': accelerator_rng()['cuda'], 'npu_rng': accelerator_rng()['npu'],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'rl_source_sha256': source_version(), **metadata}
    temp = Path(path).with_suffix('.pt.tmp')
    torch.save(value, temp)
    atomic_replace(temp, path)


def load(path, device):
    value = torch.load(path, map_location='cpu', weights_only=True)
    if value.get('model_schema') != MODEL_SCHEMA or value.get('encoding') != ENCODING:
        raise ValueError('joint checkpoint schema mismatch')
    with torch.random.fork_rng(devices=[]):
        model = DraftPolicy(**value['model_config'])
        model.load_state_dict(value['model_state'], strict=True)
    return model.to(device), value


def save_committed(path, model, optimizer, **metadata):
    """Atomically seal weights, immutable best, and the current log boundary."""
    path = Path(path)
    output = path.parent
    best = None
    best4 = None
    if path.name == 'latest.pt' and (output/'best.pt').exists():
        fingerprint = digest(output/'best.pt')
        archive = output/'committed-best'/f'{fingerprint}.pt'
        archive.parent.mkdir(exist_ok=True)
        if not archive.exists():
            try:
                os.link(output/'best.pt', archive)
            except OSError:
                shutil.copy2(output/'best.pt', archive)
        best = {'path': str(archive.relative_to(output)), 'sha256': fingerprint}
    if path.name == 'latest.pt' and (output/'best4.pt').exists():
        fingerprint=digest(output/'best4.pt')
        archive=output/'committed-best4'/f'{fingerprint}.pt'
        archive.parent.mkdir(exist_ok=True)
        if not archive.exists():
            try:os.link(output/'best4.pt',archive)
            except OSError:shutil.copy2(output/'best4.pt',archive)
        best4={'path':str(archive.relative_to(output)),'sha256':fingerprint}
    save(path, model, optimizer, committed_best=best, committed_best4=best4,
         committed_log_offsets={p.name: p.stat().st_size for p in
             [*output.glob('*.jsonl'), output/'progress.log'] if p.exists()}, **metadata)
