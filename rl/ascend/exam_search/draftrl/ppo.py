"""Masked on-policy PPO with task-balanced losses and microbatch accumulation."""
import random
import time
from collections import Counter
import torch
from .encoding import collate
from .distribution import distributions
from .advantages import estimate, assert_current_policy
from .practice import profile_weights, validate_auxiliary_records  # mesh-aware weights are in sharded
from . import sharded
from .update_diagnostics import update_coverage, post_update


def aggregate_auxiliary_diagnostics(diagnostics, mesh):
    """Aggregate rank-local evidence counts, without counting shared rows twice."""
    if diagnostics is None:
        return None
    keys = ('roots', 'accepted_roots', 'weighted_roots', 'rejected_roots',
            'exploration_samples', 'distinct_particle_action_pairs')
    totals = sharded.reduce_sum(mesh, {**{key: diagnostics[key] for key in keys},
        'weight_sum': diagnostics['mean_weight'] * diagnostics['accepted_roots']})
    return {**diagnostics, **{key: int(totals[key]) for key in keys},
        'mean_weight': totals['weight_sum']/max(1, totals['accepted_roots']),
        'rejected_reasons': sharded.reduce_nested(mesh, diagnostics['rejected_reasons'])}


def update(model, optimizer, records, config, device, progress=None, mesh=None):
    if not records:
        raise ValueError('empty on-policy rollout')
    n = len(records)
    # Two record layouts (distributed.LearnerGroup.update decides): `shared` means every
    # rank holds the identical full list and blocks are global and strided -- the
    # original scheme, kept for direct callers and the two-process parity tests.
    # Otherwise each rank holds only its own records and every batch-wide quantity
    # is all-reduced through `local_mesh`; totals()/gradients() use `mesh` either way.
    shared = mesh is not None and getattr(mesh, 'shared_records', False)
    local_mesh = None if shared else mesh
    if any(r.get('loss_kind') not in ('ppo', 'search') for r in records):
        raise ValueError('Every joint record must declare its actual action mechanism')
    assert_current_policy(records,config.get('_policy_version'))
    validate_auxiliary_records(records, config)
    signed_settings=config.get('signed_exam_credit')
    if signed_settings:
        from .signed_credit import prepare
        prepare(records,signed_settings)
    auxiliary_diagnostics = None
    if config.get('search', {}).get('execution_mode', 'act') == 'auxiliary':
        from .search_supervision import prepare_auxiliary
        auxiliary_diagnostics = prepare_auxiliary(records, config['search'])
    efficiency=config.get('sample_efficiency',{})
    advantage_mode=efficiency.get('advantage_mode','mc')
    raw_advantages,raw_targets=estimate(records,advantage_mode,efficiency.get('gae_lambda',0.98))
    meaningful = torch.tensor([len(r['encoded'].submissions)>1 and r['loss_kind']=='ppo' for r in records])
    searched = torch.tensor([r['loss_kind']=='search' for r in records])
    auxiliary = torch.tensor(['search_aux_target' in r for r in records])
    labelled = searched | auxiliary
    advantages = torch.tensor(raw_advantages)
    critic_targets = torch.tensor(raw_targets)
    # Per-profile mean/std/RMS, the profile set and the record count are properties of
    # the whole batch, not of this rank's share of it; sharded.profile_weights
    # all-reduces them and is the identity without a mesh.
    policy_weight, value_weight, profiles, n_global = sharded.profile_weights(
        advantages, records, meaningful, local_mesh)
    search_weight = torch.zeros(n)
    learning_diagnostics=[]
    search_total = sharded.search_totals(local_mesh, records, labelled, profiles)
    for profile in profiles:
        indices = [i for i, r in enumerate(records) if r['profile']==profile and labelled[i]]
        total = search_total[profile]
        for i in indices:
            search_weight[i] = records[i].get('loss_weight', 1.)*n_global/(len(profiles)*total)
            if auxiliary[i] or config['search'].get('learning_target'):
                payload = records[i]['search_aux_target'] if auxiliary[i] else records[i]['search']
                detail=payload.get('learning_target')
                expected_mode = 'peer_marginal' if auxiliary[i] else 'prior_advantage'
                if (not detail or detail.get('mode')!=expected_mode
                        or not 0<=detail.get('weight',-1)<=1):
                    raise ValueError('Missing separated search learning evidence')
                search_weight[i] *= detail['weight']
                learning_diagnostics.append(detail)
    logs = []
    duty = config.get('update_duty_cycle', 1.0)
    if duty != 1:
        raise ValueError('Artificial training sleeps are disabled in both resource modes')
    intentional_pause = 0.0
    last_progress = time.monotonic()
    order = list(range(n))
    effective = config.get('effective_minibatch',64)
    stop = False
    maximum_epochs=efficiency.get('ppo_epochs_max',config['epochs'])
    if type(maximum_epochs) is not int or maximum_epochs<1:raise ValueError('invalid PPO epoch limit')
    stop_reason='epoch_limit'
    accepted_indices, attempted_indices = set(), set()
    stopping_block = None
    # Agree the block structure once: every rank walks the same num_blocks blocks over
    # its OWN records (cut into near-equal chunks), so the collectives inside the loop
    # line up even when ranks hold different record counts and every global block
    # contains every rank's share (no ragged tail of tiny blocks).
    if shared:
        num_blocks, n_global = -(-n // effective), n
        bounds = [(i*effective, min((i+1)*effective, n)) for i in range(num_blocks)]
    else:
        bounds, num_blocks, n_global = sharded.block_plan(local_mesh, n, effective)
    for epoch in range(maximum_epochs):
        if shared:
            mesh.shuffle(order)
        else:
            random.shuffle(order)
        epoch_kl = []
        for block_index in range(num_blocks):
            start, end = bounds[block_index]
            block = order[start:end]
            # The divisor is the block's size across ALL ranks: gradients are summed,
            # never averaged again, so this keeps the single-learner objective exactly.
            block_size = len(block) if shared else sharded.block_length(local_mesh, len(block))
            attempted_indices.update(block)
            optimizer.zero_grad(set_to_none=True)
            totals = Counter()
            shard = block[mesh.rank::mesh.size] if shared else block
            for offset in range(0,len(shard),config['minibatch']):
                indices = shard[offset:offset+config['minibatch']]
                rows = [records[i] for i in indices]
                batch = collate([r['encoded'] for r in rows],device)
                logits, values, quantiles = model.learning_forward(batch)
                dist, base = distributions(logits,batch['mask'],[r['exploration'] for r in rows])
                selected = meaningful[indices].to(device)
                actions = torch.tensor([r['action'] for r in rows],device=device)
                targets = critic_targets[indices].to(device)
                is_search = searched[indices].to(device)
                ppo_indices = (~is_search).nonzero(as_tuple=True)[0]
                log_ratio = logits.new_zeros(len(rows))
                if len(ppo_indices):
                    old = logits.new_tensor([r['old_logp'] for r in rows if r['loss_kind']=='ppo'])
                    if not torch.isfinite(old).all():
                        raise ValueError('Invalid true PPO behavior likelihood')
                    # Search-selected actions have no PPO ratio at all.
                    log_ratio = log_ratio.index_copy(0, ppo_indices,
                        dist.log_prob(actions)[ppo_indices]-old)
                ratio = log_ratio.exp()
                adv = advantages[indices].to(device)
                pw, vw = policy_weight[indices].to(device), value_weight[indices].to(device)
                surrogate = torch.minimum(ratio*adv, ratio.clamp(1-config['clip'],1+config['clip'])*adv)
                policy = -(surrogate*pw).sum()/block_size
                sw = search_weight[indices].to(device)
                target = torch.zeros_like(logits)
                for position, row in enumerate(rows):
                    if row['loss_kind'] != 'search' and 'search_aux_target' not in row:
                        continue
                    search = row['search'] if row['loss_kind']=='search' else row['search_aux_target']
                    if (row['encoded'].phase != 0 or not search['target_budget_eligible']
                            or search['root_action_coverage'] != 1.
                            or search['actions'] != row['encoded'].submissions):
                        raise ValueError('Invalid search policy target admission/alignment')
                    probability = logits.new_tensor(search['target_policy'])
                    if (len(probability) != len(row['encoded'].submissions)
                            or not torch.isfinite(probability).all() or (probability < 0).any()
                            or not torch.isclose(probability.sum(), logits.new_tensor(1.))):
                        raise ValueError('Malformed detached search distribution')
                    target[position,:len(probability)] = probability.detach()
                log_policy = logits.log_softmax(-1).masked_fill(~batch['mask'], 0.)
                search_loss = (-(target*log_policy).sum(-1)*sw).sum()/block_size
                value = (torch.nn.functional.smooth_l1_loss(values,targets,reduction='none')*vw).sum()/block_size
                distribution_loss = logits.new_zeros(())
                if quantiles is not None:
                    from .value_distribution import quantile_loss
                    exam_mask = (batch['phase']==0).to(vw.dtype)
                    distribution_loss = (quantile_loss(quantiles,targets)*vw*exam_mask).sum()/block_size
                norm_entropy = base.entropy()/batch['mask'].sum(-1).float().log().clamp_min(1)
                coeff = logits.new_tensor([r['exploration']['entropy_coefficient'] for r in rows])
                bonus = (coeff*norm_entropy*torch.where(is_search,sw,pw)).sum()/block_size
                loss = (policy + config['search']['loss_coefficient']*search_loss
                        + config['value_coefficient']*value
                        + config.get('value_calibration',{}).get('distribution_coefficient',1.)*distribution_loss - bonus)
                if not torch.isfinite(loss):
                    raise FloatingPointError('nonfinite mixed-plan PPO')
                loss.backward()
                kl_values = ((ratio-1)-log_ratio)[selected]
                totals.update(loss=float(loss.detach()), policy_loss=float(policy.detach()),
                    value_loss=float(value.detach()), distribution_loss=float(distribution_loss.detach()), search_loss=float(search_loss.detach()), entropy_bonus=float(bonus.detach()),
                    kl_sum=float(kl_values.detach().sum()), kl_count=len(kl_values),
                    clip_count=int(((ratio-1).abs()>config['clip'])[selected].sum()))
            if mesh is not None:
                totals = mesh.totals(totals)
            kl = totals['kl_sum']/max(1,totals['kl_count'])
            epoch_kl.append((kl,totals['kl_count']))
            # No optimizer step is taken for a block already outside trust region.
            if kl > config['target_kl']*2:
                stopping_block = {'kl': kl, 'threshold': config['target_kl']*2,
                                  'epoch': epoch+1, 'start_record': start, 'records': block_size}
                optimizer.zero_grad(set_to_none=True); stop=True; stop_reason='block_kl'; break
            if mesh is not None:
                mesh.gradients(model)
            from gakumas_training.device import optimizer_options
            grad = torch.nn.utils.clip_grad_norm_(model.parameters(),config['max_grad'],
                error_if_nonfinite=True, **optimizer_options(model))
            optimizer.step()
            accepted_indices.update(block)
            logs.append({k:totals[k] for k in ('loss','policy_loss','search_loss','value_loss','distribution_loss','entropy_bonus')} | {
                'kl':kl,'grad_norm':float(grad),'clip_fraction':totals['clip_count']/max(1,totals['kl_count'])})
            if progress is not None and time.monotonic()-last_progress >= 30:
                progress(epoch=epoch+1, epochs_max=maximum_epochs,
                    records_seen=end, records_total=n,
                    optimizer_steps=len(logs), microbatch=config['minibatch'], kl=kl)
                last_progress = time.monotonic()
        mean_kl = sum(k*c for k,c in epoch_kl)/max(1,sum(c for _,c in epoch_kl))
        if stop or mean_kl>config['target_kl']:
            if not stop:stop=True;stop_reason='epoch_kl'
            break
    if not logs:
        raise RuntimeError('PPO made no update; check frozen behavior likelihood parity')
    completion = None
    if config.get('critic_completion'):
        from .critic_completion import complete_values
        completion = complete_values(model, optimizer, records, critic_targets, value_weight,
            accepted_indices, attempted_indices, order, config, device, progress, mesh=mesh)
    signed_result=None
    if signed_settings:
        from .signed_credit import summarize
        signed_result=summarize(records,accepted_indices)
        if local_mesh is not None and local_mesh.size > 1:
            # Group counts are summed over ranks; the hash and samples are this rank's.
            signed_result['groups']=sharded.reduce_nested(local_mesh, signed_result['groups'])
            signed_result['records_sha256']='per-rank:'+signed_result['records_sha256']
    _ld_keys=('target_entropy','prior_entropy','behavior_entropy','estimated_gain')
    _ld=sharded.reduce_sum(local_mesh, {'roots':len(learning_diagnostics),
        'weighted':sum(d['weight']>0 for d in learning_diagnostics),
        'weight':sum(d['weight'] for d in learning_diagnostics),
        **{key:sum(d[key] for d in learning_diagnostics) for key in _ld_keys}})
    _counts=sharded.reduce_sum(local_mesh, {'search':int(searched.sum()), 'ppo':int((~searched).sum()),
        'auxiliary_labels':int(auxiliary.sum()), 'auxiliary_roots':sum('search_aux' in r for r in records)})
    _task_records=sharded.reduce_nested(local_mesh, dict(Counter(r['profile'] for r in records)))
    # Batch-wide record statistics for metrics.jsonl (phase counts, exploration
    # entropies, practice diagnostics). The runner used to iterate the gathered record
    # set on rank 0; that set no longer exists, so the partial sums are reduced here.
    from .practice import PHASES as _PHASES
    _fields=('behavior_entropy_fraction','base_entropy_fraction','behavior_max_probability','base_max_probability')
    _stats={'phase_decisions':{}, 'exploration':{}, 'practice':{}}
    for r in records:
        _ph=r['encoded'].phase
        _stats['phase_decisions'][str(_ph)]=_stats['phase_decisions'].get(str(_ph),0)+1
        _active=len(r['encoded'].submissions)>1
        # Rollout records carry choose()'s entropy diagnostics; bare test records may not.
        if _active and r['loss_kind']=='ppo' and all(k in r for k in _fields):
            _e=_stats['exploration'].setdefault(_PHASES[_ph],{'count':0,**{k:0. for k in _fields}})
            _e['count']+=1
            for k in _fields:_e[k]+=float(r[k])
        _g=_stats['practice'].setdefault('%s/%s/%s'%(r['profile'],_PHASES[_ph],r.get('exploration_mode','normal')),
            {'decisions':0,'meaningful':0,'value_mae':0.,'bmp_sum':0.,'bmp_count':0})
        _g['decisions']+=1
        _g['value_mae']+=abs(float(r['return'])-float(r['old_value']))
        if _active:
            _g['meaningful']+=1
            if 'behavior_max_probability' in r:
                _g['bmp_sum']+=float(r['behavior_max_probability']); _g['bmp_count']+=1
    _record_stats=sharded.reduce_nested(local_mesh,_stats)
    auxiliary_diagnostics = aggregate_auxiliary_diagnostics(auxiliary_diagnostics, local_mesh)
    return {k:sum(r[k] for r in logs)/len(logs) for k in logs[0]} | {
        'signed_credit':signed_result,
        'auxiliary_search':auxiliary_diagnostics,
        'search_learning': {'roots':int(_ld['roots']),
            'weighted_roots':int(_ld['weighted']),
            'mean_weight':_ld['weight']/max(1,_ld['roots']),
            **{'mean_'+key:_ld[key]/max(1,_ld['roots']) for key in _ld_keys}},
        'intentional_pause_seconds':intentional_pause,'update_duty_cycle':duty,
        'epochs_attempted':epoch+1,'epochs_max':maximum_epochs,'ppo_stop_reason':stop_reason,
        'advantage_mode':advantage_mode,
        'optimizer_steps':len(logs),'effective_minibatch':effective,'microbatch':config['minibatch'],
        'search_records':int(_counts['search']), 'ppo_records':int(_counts['ppo']),
        'auxiliary_search_records':int(_counts['auxiliary_labels']),
        'auxiliary_search_roots':int(_counts['auxiliary_roots']),
        'task_records':{k:int(v) for k,v in _task_records.items()},'kl_early_stop':stop,
        'stopping_block':stopping_block,
        'update_coverage':sharded.reduce_coverage(local_mesh, update_coverage(records,accepted_indices,attempted_indices)),
        'critic_completion':completion,
        'critic_update_coverage':completion['coverage'] if completion else
            sharded.reduce_coverage(local_mesh, update_coverage(records,accepted_indices,attempted_indices)),
        'record_stats':_record_stats,
        'learner_world_size': mesh.size if mesh is not None else 1,
        'post_update_kl':post_update(model,records,config,device) if mesh is None or mesh.rank == 0 else None}
