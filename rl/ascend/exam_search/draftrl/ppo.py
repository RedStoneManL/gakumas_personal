"""Masked on-policy PPO with task-balanced losses and microbatch accumulation."""
import random
import time
from collections import Counter
import torch
from .encoding import collate
from .distribution import distributions
from .advantages import estimate, assert_current_policy
from .practice import profile_weights
from .update_diagnostics import update_coverage, post_update


def update(model, optimizer, records, config, device, progress=None, mesh=None):
    if not records:
        raise ValueError('empty on-policy rollout')
    n = len(records)
    if any(r.get('loss_kind') not in ('ppo', 'search') for r in records):
        raise ValueError('Every joint record must declare its actual action mechanism')
    assert_current_policy(records,config.get('_policy_version'))
    signed_settings=config.get('signed_exam_credit')
    if signed_settings:
        from .signed_credit import prepare
        prepare(records,signed_settings)
    efficiency=config.get('sample_efficiency',{})
    advantage_mode=efficiency.get('advantage_mode','mc')
    raw_advantages,raw_targets=estimate(records,advantage_mode,efficiency.get('gae_lambda',0.98))
    meaningful = torch.tensor([len(r['encoded'].submissions)>1 and r['loss_kind']=='ppo' for r in records])
    searched = torch.tensor([r['loss_kind']=='search' for r in records])
    advantages = torch.tensor(raw_advantages)
    critic_targets = torch.tensor(raw_targets)
    profiles = sorted({r['profile'] for r in records})
    policy_weight, value_weight = profile_weights(advantages, records, meaningful)
    search_weight = torch.zeros(n)
    learning_diagnostics=[]
    for profile in profiles:
        indices = [i for i, r in enumerate(records) if r['profile']==profile and searched[i]]
        total = sum(records[i].get('loss_weight', 1.) for i in indices)
        for i in indices:
            search_weight[i] = records[i].get('loss_weight', 1.)*n/(len(profiles)*total)
            if config['search'].get('learning_target'):
                detail=records[i]['search'].get('learning_target')
                if (not detail or detail.get('mode')!='prior_advantage'
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
    for epoch in range(maximum_epochs):
        if mesh is None:
            random.shuffle(order)
        else:
            mesh.shuffle(order)
        epoch_kl = []
        for start in range(0,n,effective):
            block = order[start:start+effective]
            attempted_indices.update(block)
            optimizer.zero_grad(set_to_none=True)
            totals = Counter()
            shard = block if mesh is None else block[mesh.rank::mesh.size]
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
                policy = -(surrogate*pw).sum()/len(block)
                sw = search_weight[indices].to(device)
                target = torch.zeros_like(logits)
                for position, row in enumerate(rows):
                    if row['loss_kind'] != 'search':
                        continue
                    search = row['search']
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
                search_loss = (-(target*log_policy).sum(-1)*sw).sum()/len(block)
                value = (torch.nn.functional.smooth_l1_loss(values,targets,reduction='none')*vw).sum()/len(block)
                distribution_loss = logits.new_zeros(())
                if quantiles is not None:
                    from .value_distribution import quantile_loss
                    exam_mask = (batch['phase']==0).to(vw.dtype)
                    distribution_loss = (quantile_loss(quantiles,targets)*vw*exam_mask).sum()/len(block)
                norm_entropy = base.entropy()/batch['mask'].sum(-1).float().log().clamp_min(1)
                coeff = logits.new_tensor([r['exploration']['entropy_coefficient'] for r in rows])
                bonus = (coeff*norm_entropy*torch.where(is_search,sw,pw)).sum()/len(block)
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
                                  'epoch': epoch+1, 'start_record': start, 'records': len(block)}
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
                    records_seen=min(start+effective,n), records_total=n,
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
    return {k:sum(r[k] for r in logs)/len(logs) for k in logs[0]} | {
        'signed_credit':signed_result,
        'search_learning': {'roots':len(learning_diagnostics),
            'weighted_roots':sum(d['weight']>0 for d in learning_diagnostics),
            'mean_weight':sum(d['weight'] for d in learning_diagnostics)/max(1,len(learning_diagnostics)),
            **{'mean_'+key:sum(d[key] for d in learning_diagnostics)/max(1,len(learning_diagnostics))
               for key in ('target_entropy','prior_entropy','behavior_entropy','estimated_gain')}},
        'intentional_pause_seconds':intentional_pause,'update_duty_cycle':duty,
        'epochs_attempted':epoch+1,'epochs_max':maximum_epochs,'ppo_stop_reason':stop_reason,
        'advantage_mode':advantage_mode,
        'optimizer_steps':len(logs),'effective_minibatch':effective,'microbatch':config['minibatch'],
        'search_records':int(searched.sum()), 'ppo_records':int((~searched).sum()),
        'task_records':dict(Counter(r['profile'] for r in records)),'kl_early_stop':stop,
        'stopping_block':stopping_block,
        'update_coverage':update_coverage(records,accepted_indices,attempted_indices),
        'critic_completion':completion,
        'critic_update_coverage':completion['coverage'] if completion else
            update_coverage(records,accepted_indices,attempted_indices),
        'critic_completion':completion,
        'critic_update_coverage':completion['coverage'] if completion else
            update_coverage(records,accepted_indices,attempted_indices),
        'learner_world_size': mesh.size if mesh is not None else 1,
        'post_update_kl':post_update(model,records,config,device) if mesh is None or mesh.rank == 0 else None}
