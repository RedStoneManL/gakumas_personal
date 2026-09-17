"""Rank-local records under batch-global statistics.

Until now every learner rank received the complete record set -- two all_gathers during
collection and one broadcast before the update -- so that the PPO loop could shuffle a
global order and stride it across ranks. Serialising ~1 GB of Encoded objects three
times cost about 30 minutes of a 115-minute batch. Now each rank keeps only the records
it produced, and the two things that were implicitly batch-global are made explicit:

  * the per-profile statistics behind profile_weights() and the search-weight
    normalisation (weight sums, weighted mean and variance, marginal RMS, record count,
    the profile set) are all-reduced before any advantage is rescaled;
  * the optimizer block structure is agreed up front so every rank makes exactly the
    same number of collective calls per epoch, and each block's loss is divided by the
    GLOBAL block length -- the contract stated in gakumas_training.collectives.

With mesh=None (a single learner) every function here degenerates to the code path
that existed before, so the single-rank behaviour is unchanged.
"""
import math
import torch

MARGINAL_KINDS = ('best_of_k_leave_one_out_max', 'best_of_k_state_contribution')


# --- primitive reductions ----------------------------------------------------

def reduce_sum(mesh, values):
    """All-reduce (sum) a flat dict of numbers. Identity without a mesh."""
    if mesh is None or mesh.size == 1:
        return dict(values)
    return mesh.sum_values({k: float(v) for k, v in values.items()})


def reduce_max(mesh, values):
    """All-reduce (max) a flat dict of numbers, via one small gather."""
    if mesh is None or mesh.size == 1:
        return dict(values)
    rows = mesh.gather_lists([dict(values)])
    keys = set().union(*rows)
    return {k: max(r[k] for r in rows if k in r) for k in keys}


def gather_union(mesh, items):
    """Sorted union of a small hashable collection across ranks."""
    local = sorted(set(items))
    if mesh is None or mesh.size == 1:
        return local
    return sorted(set(mesh.gather_lists(local)))


def flatten(nested, prefix=''):
    """{'a': {'x': 1}, 'b': 2} -> {'a|x': 1, 'b': 2}; only numeric leaves are kept."""
    out = {}
    for key, value in nested.items():
        name = f'{prefix}{key}'
        if isinstance(value, dict):
            out.update(flatten(value, name + '|'))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            out[name] = value
    return out


def unflatten(flat):
    out = {}
    for name, value in flat.items():
        parts = name.split('|')
        node = out
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


def reduce_nested(mesh, nested):
    """All-reduce every numeric leaf of a nested dict; keys are unioned across ranks."""
    if mesh is None or mesh.size == 1:
        return nested
    flat = flatten(nested)
    keys = gather_union(mesh, flat)
    summed = reduce_sum(mesh, {k: flat.get(k, 0.) for k in keys})
    return unflatten(summed)


# --- optimizer block structure -------------------------------------------------

def even_bounds(n_local, num_blocks):
    """Cut range(n_local) into num_blocks contiguous chunks whose sizes differ by <= 1."""
    bounds, start = [], 0
    for i in range(num_blocks):
        size = n_local // num_blocks + (1 if i < n_local % num_blocks else 0)
        bounds.append((start, start + size)); start += size
    return bounds


def block_plan(mesh, n_local, effective):
    """How this rank walks its own records while staying in lockstep with the others.

    Returns (bounds, num_blocks, n_global): bounds[i] = (start, end) into this rank's
    own shuffled order for global block i. A global block of `effective` records
    strided across `size` ranks gave each rank at most ceil(effective/size) of them, so
    num_blocks is the largest ceil(n_local/per_rank) over ranks and every rank cuts its
    records into that many near-equal chunks (each <= per_rank). Every global block
    therefore contains every rank's share and block_length ~ n_global/num_blocks; there
    is no ragged tail of tiny blocks when the ranks hold unequal record counts. A rank
    with fewer records than num_blocks walks some empty chunks and still joins every
    collective. A single rank (mesh None or size 1) keeps the original layout exactly:
    range(0, n, effective) with one short tail block, so the single-learner reference
    the two-process parity tests compare against is unchanged.
    """
    size = 1 if mesh is None else mesh.size
    if size == 1:
        num_blocks = math.ceil(n_local / effective) if n_local else 0
        return ([(i * effective, min((i + 1) * effective, n_local)) for i in range(num_blocks)],
                num_blocks, n_local)
    per_rank = max(1, math.ceil(effective / size))
    totals = reduce_sum(mesh, {'n': n_local})
    local_blocks = math.ceil(n_local / per_rank) if n_local else 0
    num_blocks = int(reduce_max(mesh, {'blocks': local_blocks})['blocks'])
    return even_bounds(n_local, num_blocks), num_blocks, int(round(totals['n']))


def block_length(mesh, local_len):
    """Global length of the current block: the divisor every microbatch loss uses."""
    return int(round(reduce_sum(mesh, {'len': local_len})['len']))


# --- batch-global advantage normalisation -----------------------------------------

def profile_weights(advantages, records, meaningful, mesh=None):
    """practice.profile_weights with every batch-wide statistic all-reduced.

    Same arithmetic as the original: per profile, non-marginal advantages are
    standardised by the (weighted) mean and population std of that profile's meaningful
    records; marginal (Best-of-K) advantages are divided by their weighted RMS with a
    floor; policy weights are w*n/(P*sum_w_active), value weights w*n/(P*sum_w_member).
    The original branched on all-weights-equal-one to call .mean()/.std(); the weighted
    form gives the same value in that case, so one form serves both.
    """
    if mesh is None or mesh.size == 1:
        # Single learner: the reference implementation, bit for bit.
        from .practice import profile_weights as reference
        policy, value = reference(advantages, records, meaningful)
        return policy, value, sorted({r['profile'] for r in records}), len(records)
    n_local = len(records)
    weights = torch.tensor([r.get('loss_weight', 1.0) for r in records])
    if n_local and (not torch.isfinite(weights).all() or not (weights > 0).all()):
        raise ValueError('Invalid sample weights')
    marginal = torch.tensor([r.get('policy_advantage_kind') in MARGINAL_KINDS for r in records],
                            dtype=torch.bool)
    profiles = gather_union(mesh, [r['profile'] for r in records])
    n = int(round(reduce_sum(mesh, {'n': n_local})['n']))
    members = {p: torch.tensor([r['profile'] == p for r in records], dtype=torch.bool) for p in profiles}

    # pass 1: sums that do not depend on the mean
    part, floors = {}, {}
    for p in profiles:
        member = members[p]
        active = member & meaningful
        marg = member & marginal & meaningful
        part[f'{p}|w_active'] = float(weights[active].sum())
        part[f'{p}|wa_active'] = float((advantages[active] * weights[active]).sum())
        part[f'{p}|w_marg'] = float(weights[marg].sum())
        part[f'{p}|wa2_marg'] = float((advantages[marg].square() * weights[marg]).sum())
        part[f'{p}|w_member'] = float(weights[member].sum())
        floors[p] = max((r.get('contribution_rms_floor', 1e-5) for r in records if r['profile'] == p),
                        default=0.)
    tot = reduce_sum(mesh, part)
    floor = reduce_max(mesh, floors)
    means = {p: tot[f'{p}|wa_active'] / tot[f'{p}|w_active'] if tot[f'{p}|w_active'] > 0 else 0.
             for p in profiles}

    # pass 2: weighted variance about the global mean
    part2 = {}
    for p in profiles:
        active = members[p] & meaningful
        part2[f'{p}|wvar'] = float(((advantages[active] - means[p]).square() * weights[active]).sum())
    tot2 = reduce_sum(mesh, part2)

    policy = torch.zeros(n_local)
    value = torch.zeros(n_local)
    for p in profiles:
        member = members[p]
        active = member & meaningful
        if tot[f'{p}|w_active'] > 0:
            std = math.sqrt(tot2[f'{p}|wvar'] / tot[f'{p}|w_active'])
            plain = member & ~marginal
            advantages[plain] = (advantages[plain] - means[p]) / max(std, 1e-5)
            if tot[f'{p}|w_marg'] > 0:
                rms = tot[f'{p}|wa2_marg'] / tot[f'{p}|w_marg']
                advantages[member & marginal] /= max(math.sqrt(rms), max(floor.get(p, 0.), 1e-5))
            policy[active] = weights[active] * n / (len(profiles) * tot[f'{p}|w_active'])
        if tot[f'{p}|w_member'] > 0:
            value[member] = weights[member] * n / (len(profiles) * tot[f'{p}|w_member'])
    return policy, value, profiles, n


def search_totals(mesh, records, searched, profiles):
    """Per-profile global sum of loss_weight over search-labelled records."""
    part = {p: 0. for p in profiles}
    for i, r in enumerate(records):
        if searched[i]:
            part[r['profile']] += float(r.get('loss_weight', 1.))
    return reduce_sum(mesh, part)


# --- task sharding for replay stages -------------------------------------------------

def stamp_shards(tasks, size, key, rank_of=None):
    """Assign every task a rank so that tasks sharing `key(task)` land together.

    Fork replays must sit on the rank that produced their parent joint episode, so
    apply_fork_returns can credit the (joint, replicas) group locally: pass
    rank_of=lambda t: t['metadata']['origin_rank']. Bank replays only need each
    replica group whole, so they round-robin by group. Both mappings are deterministic
    in task order, so every rank that receives the same task list derives the same
    assignment.
    """
    seen = {}
    for task in tasks:
        k = key(task)
        if k not in seen:
            seen[k] = int(rank_of(task)) % size if rank_of is not None else len(seen) % size
        task['metadata']['shard_rank'] = seen[k]
    return tasks


def reduce_coverage(mesh, coverage):
    """update_coverage() output summed across ranks, fractions recomputed."""
    if mesh is None or mesh.size == 1:
        return coverage
    numeric = {k: v for k, v in coverage.items() if k in ('record_count', 'accepted_unique', 'attempted_unique')}
    groups = {k: {f: v[f] for f in ('records', 'accepted_unique', 'attempted_unique')}
              for k, v in coverage.get('groups', {}).items()}
    total = reduce_nested(mesh, {'top': numeric, 'groups': groups})
    top, groups = total['top'], total.get('groups', {})
    for g in groups.values():
        g['accepted_fraction'] = g['accepted_unique'] / g['records'] if g['records'] else 0.
    return {**coverage, **top, 'groups': groups,
            'accepted_fraction': top['accepted_unique'] / top['record_count'] if top['record_count'] else 0.}


def mine(tasks, rank):
    return [t for t in tasks if t['metadata'].get('shard_rank', 0) == rank]
