"""Training-only practice routing and correctly weighted current-policy forks."""
import copy
import math
from collections import Counter, defaultdict
import statistics

PHASES = ('exam', 'drink', 'draft', 'guidance', 'memory')


def mode_for(config, local_index, training=True):
    cfg = config.get('practice', {}).get('routing', {})
    if not training or not cfg.get('enabled', False):
        return 'normal'
    cycle = cfg.get('cycle', ['normal', 'normal', 'draft', 'exam', 'normal'])
    if not cycle or any(m not in ('normal', 'draft', 'exam') for m in cycle):
        raise ValueError('Invalid practice routing cycle')
    return cycle[local_index % len(cycle)]


def routed_parameters(examples, modes, scheduled, config):
    if scheduled is None:
        return None
    cfg = config.get('practice', {}).get('routing', {})
    out = []
    for e, mode in zip(examples, modes):
        phase = PHASES[e.phase]
        setting = dict(scheduled[phase])
        if cfg.get('enabled', False) and mode == phase and mode in ('draft', 'exam'):
            for key, value in cfg.get('overrides', {}).get(mode, {}).items():
                if key not in ('temperature', 'uniform_mix'):
                    raise ValueError('Routing may only change temperature and epsilon')
                setting[key] = max(setting[key], float(value))
        size = config.get('practice', {}).get('size_exploration', {})
        remaining = getattr(e, 'size_gate_remaining', None)
        if size.get('enabled') and mode == 'draft' and remaining is not None:
            if remaining < 1 or [a['method'] for a in e.submissions] != ['finish_draft', 'continue_draft']:
                raise ValueError('Invalid public size gate')
            # A pure prior would sample all remaining final sizes uniformly.
            # Mixture stays differentiable and is frozen for PPO likelihoods.
            setting['action_prior'] = [1 / (remaining + 1), remaining / (remaining + 1)]
            setting['uniform_mix'] = size.get('prior_mix', .8)
        out.append(setting)
    return out


def retained_metadata(summary):
    return {k: copy.deepcopy(v) for k, v in summary.items()
            if k not in ('entry', 'submissions', 'choice_steps') and not k.startswith('_')}


def selected_for_fork(config, local_index, every):
    # Each route position is selected once per `every` cycles. Using the raw
    # episode index modulo every aliases with the five-position route cycle.
    cycle = config.get('practice', {}).get('routing', {}).get('cycle', ['normal'])
    width = len(cycle) or 1
    cycle_index, position = divmod(local_index, width)
    return (cycle_index + position) % every == 0


def make_fork_tasks(summaries, config, next_seed):
    from .sample_bank import SampleBank
    cfg = config.get('practice', {}).get('forks', {})
    if not cfg.get('enabled', False):
        return [], next_seed
    if config.get('sample_efficiency', {}).get('advantage_mode', 'mc') != 'mc':
        raise ValueError('Multi-continuation prefixes currently require complete MC')
    replicas, every = cfg.get('replicas', 2), cfg.get('every_n_per_profile', 5)
    if type(replicas) is not int or not 2 <= replicas <= 4 or type(every) is not int or every < 1:
        raise ValueError('Invalid fork replication settings')
    tasks = []
    for s in summaries:
        if s.get('sampling_source') != 'joint':
            raise ValueError('Only current joint prefixes may be replicated')
        local_index = (s['seed'] - config['train_seed_base']) // len(config['_profiles'])
        if not selected_for_fork(config, local_index, every):
            continue
        if s.get('policy_version') != config['_policy_version']:
            raise ValueError('Stale prefix cannot receive a new return')
        for branch in range(1, replicas):
            meta = retained_metadata(s)
            meta.update(prefix_id=f"joint:{s['seed']}", branch_id=branch, fork_replicas=replicas,
                        parent_entry_sha256=s.get('entry_sha256'),
                        parent_environment_seed=s['seed'], environment_seed=next_seed,
                        action_rng_seed=next_seed + 40_000_000)
            tasks.append({'key': SampleBank.key(s['entry']), 'entry': copy.deepcopy(s['entry']),
                          'metadata': meta, 'replay_seed': next_seed})
            next_seed += 1
    return tasks, next_seed


def apply_fork_returns(records, original, fork_records, results, expected_tasks=None, *, objective='mean'):
    """Prefix once; each exam branch gets weight 1/M and its own return."""
    from .best_of import group_credit, apply_exam_credit
    if objective not in ('mean','best_of_k'):
        raise ValueError('Unknown repeated-construction objective')
    by_prefix = defaultdict(list)
    for s in results:
        by_prefix[s['prefix_id']].append(s)
    lookup = {f"joint:{s['seed']}": s for s in original}
    if expected_tasks is not None:
        expected = [(t['metadata']['prefix_id'], t['metadata']['branch_id']) for t in expected_tasks]
        actual = [(s['prefix_id'], s['branch_id']) for s in results]
        if len(set(actual)) != len(actual) or Counter(actual) != Counter(expected):
            raise ValueError('Missing, duplicate, or unexpected continuation result')
    # Validate all groups before mutating any return or extending the buffer.
    for prefix, branches in by_prefix.items():
        parent = lookup[prefix]
        replicas = branches[0]['fork_replicas']
        if len(branches) != replicas - 1 or {b['branch_id'] for b in branches} != set(range(1, replicas)):
            raise ValueError('Incomplete or duplicate fork outcomes')
        for branch in branches:
            if branch['policy_version'] != parent['policy_version'] or branch['fork_replicas'] != replicas:
                raise ValueError('Policy or replication plan changed during repeated exams')
            for key in ('entry_sha256', 'score_scale', 'resolved_turn_types', 'exploration_mode'):
                if key in parent and branch.get(key) != parent[key]:
                    raise ValueError(f'Continuation changed public condition: {key}')
        if not all(math.isfinite(s['normalized_score']) for s in [parent, *branches]):
            raise ValueError('Nonfinite continuation return')
        if len({s['seed'] for s in [parent,*branches]}) != replicas:
            raise ValueError('Repeated exams must use distinct environment seeds')
        if len({s.get('action_rng_seed') for s in [parent,*branches]}) != replicas:
            raise ValueError('Repeated exams must use distinct action RNG seeds')
    diagnostics = []
    for prefix, branches in by_prefix.items():
        branches.sort(key=lambda b:b['branch_id'])
        parent = lookup[prefix]
        replicas = branches[0]['fork_replicas']
        if len(branches) != replicas - 1 or len({b['branch_id'] for b in branches}) != replicas - 1:
            raise ValueError('Incomplete or duplicate fork outcomes')
        if any(b['policy_version'] != parent['policy_version'] for b in branches):
            raise ValueError('Policy changed during repeated exams')
        values = [parent['normalized_score']] + [b['normalized_score'] for b in branches]
        mean = statistics.mean(values)
        maximum, credits = group_credit(values)
        target = maximum if objective == 'best_of_k' else mean
        for r in records:
            if r['episode_id'] == prefix:
                r.update(prefix_id=prefix, branch_id=0, fork_replicas=replicas)
                if r['encoded'].phase == 0:
                    r['loss_weight'] = 1 / replicas
                else:
                    r.update(return_kind='current_prefix_'+objective, loss_weight=1.0)
                    r['return'] = target
        for r in fork_records:
            if r['prefix_id'] == prefix:
                if r['encoded'].phase != 0:
                    raise ValueError('Continuation unexpectedly contains construction')
                r['loss_weight'] = 1 / replicas
        if objective == 'best_of_k':
            apply_exam_credit([r for r in records if r['episode_id']==prefix and r['encoded'].phase==0],
                              values[0],credits[0],replicas,prefix,0,max(values[1:]))
            for branch in branches:
                index=branch['branch_id']
                apply_exam_credit([r for r in fork_records if r['prefix_id']==prefix and r['branch_id']==index],
                                  values[index],credits[index],replicas,prefix,index,
                                  max(values[:index]+values[index+1:]))
        sample_std = statistics.stdev(values)
        diagnostics.append({'prefix_id': prefix, 'profile': parent['profile'],
                            'policy_version': parent['policy_version'],
                            'entry_sha256': parent.get('entry_sha256'),
                            'exploration_mode': parent.get('exploration_mode', 'normal'),
                            'environment_seeds': [parent['seed']] + [b.get('seed') for b in branches],
                            'action_rng_seeds': [parent.get('action_rng_seed')] + [b.get('action_rng_seed') for b in branches],
                            'score_scale': parent.get('score_scale'),
                            'raw_scores': [parent.get('score')] + [b.get('score') for b in branches],
                            'sample_std': sample_std, 'mean_standard_error': sample_std / math.sqrt(replicas),
                            'replicas': replicas, 'mean': mean, 'maximum':maximum,
                            'objective':objective, 'construction_target':target,
                            'exam_marginal_gains':credits if objective=='best_of_k' else None,
                            'std': statistics.pstdev(values), 'returns': values})
    records.extend(fork_records)
    return diagnostics


def fork_coverage(original, diagnostics):
    selected = {d['prefix_id']: d for d in diagnostics}
    groups = defaultdict(list)
    for s in original:
        groups[f"{s['profile']}|{s.get('exploration_mode', 'normal')}"].append(s)
    result = {}
    for key, rows in sorted(groups.items()):
        samples = [selected[f"joint:{s['seed']}"] for s in rows if f"joint:{s['seed']}" in selected]
        result[key] = {'joint_prefixes': len(rows), 'repeated_prefixes': len(samples),
                       'coverage': len(samples) / len(rows),
                       'replica_counts': dict(Counter(str(s['replicas']) for s in samples))}
    return {'joint_prefixes': len(original), 'repeated_prefixes': len(diagnostics),
            'coverage': len(diagnostics) / len(original) if original else 0,
            'groups': result,
            'mean_standard_error': statistics.mean(d['mean_standard_error'] for d in diagnostics) if diagnostics else None,
            'note': 'Standard error is estimated from a small number of trials, not a calibrated confidence interval.'}


def profile_weights(advantages, records, meaningful):
    import torch
    n = len(records)
    weights = torch.tensor([r.get('loss_weight', 1.0) for r in records])
    if not torch.isfinite(weights).all() or not (weights > 0).all():
        raise ValueError('Invalid sample weights')
    policy = torch.zeros(n); value = torch.zeros(n)
    profiles = sorted({r['profile'] for r in records})
    for p in profiles:
        member = torch.tensor([r['profile'] == p for r in records])
        active = member & meaningful
        if active.any():
            sample, w = advantages[active], weights[active]
            if torch.all(w == 1):
                mean, std = sample.mean(), sample.std(unbiased=False)
            else:
                mean = (sample * w).sum() / w.sum()
                std = (((sample - mean).square() * w).sum() / w.sum()).sqrt()
            marginal = torch.tensor([r.get('policy_advantage_kind') in
                ('best_of_k_leave_one_out_max','best_of_k_state_contribution') for r in records])
            # Do not turn zero marginal contribution into a fabricated negative
            # reward by centering it with unrelated construction advantages.
            advantages[member & ~marginal] = (advantages[member & ~marginal] - mean) / std.clamp_min(1e-5)
            if (member & marginal & meaningful).any():
                indices=member & marginal & meaningful
                rms=(advantages[indices].square()*weights[indices]).sum()/weights[indices].sum()
                floor=max(r.get('contribution_rms_floor',1e-5) for r in records if r['profile']==p)
                advantages[member & marginal] /= rms.sqrt().clamp_min(floor)
            policy[active] = weights[active] * n / (len(profiles) * weights[active].sum())
        value[member] = weights[member] * n / (len(profiles) * weights[member].sum())
    return policy, value


def practice_diagnostics(records):
    groups = defaultdict(list)
    for r in records:
        groups[(r['profile'], PHASES[r['encoded'].phase], r.get('exploration_mode', 'normal'))].append(r)
    result = {}
    for key, rows in groups.items():
        active = [r for r in rows if len(r['encoded'].submissions) > 1]
        result['|'.join(key)] = {'decisions': len(rows), 'meaningful': len(active),
            'value_mae': statistics.mean(abs(r['return'] - r['old_value']) for r in rows),
            'behavior_max_probability': statistics.mean(r['behavior_max_probability'] for r in active) if active else None}
    return result
