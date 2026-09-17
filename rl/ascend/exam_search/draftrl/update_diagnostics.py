"""Bounded diagnostics; no optimizer, rollout, or global RNG changes."""
import random
from collections import defaultdict
import torch
from .encoding import collate
from .distribution import distributions
from .practice import PHASES


def update_coverage(records, accepted, attempted):
    groups = defaultdict(lambda: {'records': 0, 'accepted_unique': 0, 'attempted_unique': 0})
    for i, r in enumerate(records):
        phase = PHASES[r['encoded'].phase]
        for key in (f'phase:{phase}', f'profile:{r["profile"]}',
                    f'loss:{r.get("loss_kind", "ppo")}',
                    f'route:{r.get("exploration_mode", "normal")}'):
            g = groups[key]
            g['records'] += 1
            g['accepted_unique'] += i in accepted
            g['attempted_unique'] += i in attempted
    for g in groups.values():
        g['accepted_fraction'] = g['accepted_unique'] / g['records']
    return {'record_count': len(records), 'accepted_unique': len(accepted),
            'attempted_unique': len(attempted), 'accepted_fraction': len(accepted)/len(records),
            'groups': dict(groups),
            'note': 'Unique records used by accepted optimizer steps; diagnostics and rejected gradients are excluded.'}


def stratified_indices(records, limit):
    groups = defaultdict(list)
    rng = random.Random(937135)
    for i, r in enumerate(records):
        if len(r['encoded'].submissions) > 1:
            groups[(r['profile'], r['encoded'].phase)].append(i)
    keys = sorted(groups)
    for key in keys:
        rng.shuffle(groups[key])
    out = []
    while len(out) < limit and any(groups.values()):
        for key in keys:
            if groups[key] and len(out) < limit:
                out.append(groups[key].pop())
    return out


def post_update(model, records, config, device):
    records = [r for r in records if r.get('loss_kind') == 'ppo']
    cfg = config.get('practice', {}).get('update_diagnostics', {})
    if not cfg.get('enabled', False):
        return None
    limit = cfg.get('max_records', 512)
    if type(limit) is not int or not 1 <= limit <= 2048:
        raise ValueError('Invalid bounded post-update diagnostic size')
    selected = stratified_indices(records, limit)
    groups = defaultdict(list)
    # config['minibatch'] is the TRAINING microbatch (4), sized for backward-pass memory.
    # This pass is under no_grad, so slicing 512 records into 128 forwards of 4 buys
    # nothing and costs 128 sequential launches on the coordinator. Use the optimizer
    # block size, falling back to the microbatch if it is not configured.
    _chunk = config.get('effective_minibatch') or config['minibatch']
    with torch.no_grad():
        for start in range(0, len(selected), _chunk):
            rows = [records[i] for i in selected[start:start+_chunk]]
            b = collate([r['encoded'] for r in rows], device)
            logits, _ = model(b)
            dist, _ = distributions(logits, b['mask'], [r['exploration'] for r in rows])
            action = torch.tensor([r['action'] for r in rows], device=device)
            old = torch.tensor([r['old_logp'] for r in rows], device=device)
            ratio_log = dist.log_prob(action) - old
            kl = (ratio_log.exp() - 1 - ratio_log).cpu().tolist()
            for r, value in zip(rows, kl):
                groups[f"{r['profile']}|{PHASES[r['encoded'].phase]}"].append(value)
    return {'records': len(selected), 'method': 'fixed stratified profile/phase sample; approximate action KL after update',
            'groups': {k: {'records': len(v), 'mean_kl': sum(v)/len(v), 'max_action_kl': max(v)} for k,v in groups.items()},
            'mean_kl': sum(map(sum, groups.values()))/len(selected) if selected else None}
