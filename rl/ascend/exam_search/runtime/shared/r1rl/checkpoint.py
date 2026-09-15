import hashlib
import json
import os
import random
from pathlib import Path
from datetime import datetime, timezone
import torch
from round2rl.checkpoint import digest, json_write
from .model import JointPolicy, MODEL_SCHEMA
from .encoding import ENCODING


def source_version():
    root = Path(__file__).resolve().parents[1]
    reused = root.parent / 'round2/round2rl'
    files = list(sorted((root / 'r1rl').glob('*.py'))) + [root / 'train.py', root / 'prepare.py']
    files += [reused / n for n in ('encoding.py', 'model.py', 'checkpoint.py')]
    return hashlib.sha256(json.dumps({str(p.relative_to(root.parent)): digest(p) for p in files}, sort_keys=True).encode()).hexdigest()


def transfer(path, arena_hash, device):
    from round2rl.checkpoint import load as old_load
    old, info = old_load(path)
    if info.get('kind') != 'trained' or info['arena_sha256'] != arena_hash:
        raise ValueError('transfer requires trained, mechanically compatible checkpoint')
    model = JointPolicy(**info['model_config'])
    missing, unexpected = model.load_state_dict(old.state_dict(), strict=False)
    expected = {k for k in model.state_dict() if k.startswith(('drink_policy_head.', 'drink_value_head.'))}
    if set(missing) != expected or unexpected:
        raise ValueError('unexpected transfer mismatch')
    return model.to(device), {'path': str(Path(path).resolve()), 'sha256': digest(path),
        'source_arena_sha256': info['arena_sha256'], 'source_rl_sha256': info['rl_source_sha256'],
        'optimizer_reset': True, 'new_heads': sorted(expected)}


def save(path, model, optimizer, **metadata):
    value = {'model_schema': MODEL_SCHEMA, 'encoding': ENCODING, 'model_config': model.config,
        'model_state': model.state_dict(), 'optimizer_state': optimizer.state_dict(),
        'torch_rng': torch.get_rng_state(), 'python_rng': random.getstate(),
        'cuda_rng': torch.cuda.get_rng_state_all(), 'created_at': datetime.now(timezone.utc).isoformat(),
        'rl_source_sha256': source_version(), **metadata}
    temp = Path(path).with_suffix('.pt.tmp')
    torch.save(value, temp)
    os.replace(temp, path)


def load(path, device):
    value = torch.load(path, map_location='cpu', weights_only=True)
    if value.get('model_schema') != MODEL_SCHEMA or value.get('encoding') != ENCODING:
        raise ValueError('joint checkpoint schema mismatch')
    with torch.random.fork_rng(devices=[]):
        model = JointPolicy(**value['model_config'])
        model.load_state_dict(value['model_state'], strict=True)
    return model.to(device), value
