"""Critic-only calibration on fresh frozen-actor games, never historical PPO."""
import copy
import hashlib
import json
import math
import random
import statistics
import time
from collections import defaultdict
from pathlib import Path


def state_digest(model, predicate):
    h=hashlib.sha256()
    for name,value in model.state_dict().items():
        if predicate(name):h.update(name.encode());h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def value_parameter(name):
    return name.startswith(('critic.towers.exam.', 'value_head.', 'exam_quantile_head.',
                            'critic_relational.encoder.towers.exam.',
                            'critic_relational.value_heads.exam.', 'critic_relational.quantile_head.'))


def thin_records(records, max_states=8):
    grouped=defaultdict(list)
    for r in records:grouped[r['episode_id']].append(r)
    selected=[]
    for episode,rows in grouped.items():
        indices=sorted({round(i*(len(rows)-1)/max(1,max_states-1)) for i in range(min(max_states,len(rows)))})
        if len(rows)<max_states:indices=list(range(len(rows)))
        for i in indices:
            r=rows[i]
            selected.append({'encoded':r['encoded'],'return':r['return'], 'profile':r['profile'],
                             'episode_id':episode,'opening':i==0,'loss_kind':'value_only'})
    return selected


def make_tasks(source, config, directory):
    """Use committed TRAINING loadouts; existing validation/test decks stay untouched."""
    from .duplicate_limits import validate,limit,overrides
    info=config['_calibration_source_info']
    length=info['committed_log_offsets']['train-episodes.jsonl']
    with (Path(source)/'train-episodes.jsonl').open('rb') as f:lines=f.read(length).splitlines()
    by_profile=defaultdict(dict)
    for line in reversed(lines):
        row=json.loads(line)
        if 'entry' not in row:continue
        pid=row['profile']; key=row['entry_sha256']
        if key in by_profile[pid] or len(by_profile[pid])>=6:continue
        try:validate(row['entry']['cards'],config['_card_families'],limit(config),overrides(config))
        except ValueError:continue
        by_profile[pid][key]=row
    entries=[]
    for pid in sorted(p['id'] for p in config['_profiles']):
        rows=list(by_profile[pid].values())
        if len(rows)<6:raise ValueError('Need six distinct committed training loadouts per idol')
        for i,row in enumerate(rows):
            entries.append({'id':f'bank-{pid}-{i}','entry':row['entry'],'metadata':row,
                            'split':'fit' if i<4 else 'unseen'})
    research=Path(config['value_calibration']['research_manifest'])
    research_data=json.loads(research.read_text(encoding='utf-8'))
    research_ids=set()
    for task in research_data['tasks']:
        did=task['metadata']['research_deck_id']
        if did in research_ids:continue
        research_ids.add(did)
        validate(task['entry']['cards'],config['_card_families'],limit(config),overrides(config))
        entries.append({'id':did,'entry':task['entry'],'metadata':task['metadata'],'split':'fit'})
    tasks={'fit':[],'development':[],'unseen':[]}
    cfg=config['value_calibration']
    for i,item in enumerate(entries):
        splits=['fit','development'] if item['split']=='fit' else ['unseen']
        for split in splits:
            count=cfg['train_replicas'] if split=='fit' else cfg['eval_replicas']
            for j in range(count):
                meta={k:copy.deepcopy(item['metadata'][k]) for k in ('profile','plan','course_id','score_scale',
                        'drink_capacity','memory_mode','memory_capacity','condition_cell')}
                meta.update(exploration_mode='normal',search_enabled=False,calibration_entry=item['id'],calibration_split=split)
                seed=3_600_000_000+i*1000+{'fit':0,'development':200,'unseen':400}[split]+j
                tasks[split].append({'entry':copy.deepcopy(item['entry']),'key':item['id'],'metadata':meta,'replay_seed':seed})
    all_seeds=[t['replay_seed'] for group in tasks.values() for t in group]
    if len(set(all_seeds))!=len(all_seeds):raise ValueError('Calibration seeds overlap')
    manifest={'schema':'critic-calibration-data/1','policy_version':config['_policy_version'],
              'source_checkpoint_code':info['rl_source_sha256'],'source_committed_log_bytes':length,
              'research_manifest_sha256':hashlib.sha256(research.read_bytes()).hexdigest(),
              'tasks':tasks,'training_updated':False,'selection':'Recent distinct committed training entries, no score ranking; 20 fit + 10 unseen, plus 6 explicitly adapted research recipes.'}
    (directory/'data-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return tasks


def evaluate(model, records, rows, device, batch_size=24):
    import torch
    from .encoding import collate
    from .value_distribution import quantile_loss,mixture_best_of
    losses=defaultdict(list);means=defaultdict(list);openings={}
    with torch.inference_mode():
        for start in range(0,len(records),batch_size):
            chunk=records[start:start+batch_size]
            mean,atoms=model.value_outputs(collate([r['encoded'] for r in chunk],device))
            targets=torch.tensor([r['return'] for r in chunk],device=device)
            error=quantile_loss(atoms,targets).tolist()
            me=(mean-targets).abs().tolist();distributions=atoms.sort(-1).values.tolist()
            for r,l,m,d in zip(chunk,error,me,distributions):
                losses[r['profile']].append(l);means[r['profile']].append(m)
                if r['opening']:openings[r['episode_id']]=d
    groups=defaultdict(list)
    for row in rows:groups[row['calibration_entry']].append(row)
    summaries=[]
    for key,group in sorted(groups.items()):
        group.sort(key=lambda r:r['seed'])
        predictions=[openings[f'calibration:{r["seed"]}'] for r in group]
        # Average over possible opening hands first, then take Best4 ONCE.
        predicted=mixture_best_of(predictions,4)
        measured=statistics.mean(max(r['normalized_score'] for r in group[i:i+4]) for i in range(0,len(group),4))
        summaries.append({'entry':key,'profile':group[0]['profile'],'predicted_best4':predicted,
                          'measured_best4':measured,'absolute_error':abs(predicted-measured),
                          'score_scale':group[0]['score_scale'],'scores':[r['score'] for r in group]})
    per_profile={p:{'quantile_loss':statistics.mean(losses[p]),'mean_mae':statistics.mean(means[p]),
                   'best4_mae':statistics.mean(r['absolute_error'] for r in summaries if r['profile']==p)} for p in losses}
    return {'profiles':per_profile,'macro_quantile_loss':statistics.mean(p['quantile_loss'] for p in per_profile.values()),
            'macro_best4_mae':statistics.mean(p['best4_mae'] for p in per_profile.values()),'entries':summaries}


def calibrate(pool,model,optimizer,config,device,source,output,choose,publish):
    import torch
    from gakumas_training.device import preserve_rng
    from .bank_rollout import rollout_bank
    from .encoding import collate
    from .value_distribution import quantile_loss
    from .checkpoint import json_write
    cfg=config['value_calibration'];output=Path(output).resolve();directory=output/'value-calibration'
    if directory.exists() and any(directory.iterdir()):
        from datetime import datetime,timezone
        archive=output/('value-calibration-attempt-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        if directory.resolve().parent!=output or archive.resolve().parent!=output:
            raise ValueError('Calibration recovery path escaped this output')
        directory.rename(archive)
    directory.mkdir(exist_ok=True)
    before=state_digest(model,lambda n:not value_parameter(n))
    frozen_actor=state_digest(model,lambda n:n.startswith(('actor.', 'actor_relational.')) or 'policy_head' in n)
    original_flags={n:p.requires_grad for n,p in model.named_parameters()}
    rates=[g['lr'] for g in optimizer.param_groups]
    rng_state=random.getstate()
    start=time.monotonic()
    work=dict(config)
    tasks=make_tasks(source,config,directory)
    data={};outcomes={}
    try:
        with preserve_rng():
            for split in ('fit','development','unseen'):
                publish('critic_collecting',critic_calibration={'split':split,'games':len(tasks[split]),'actor_frozen':True})
                records,rows,_=rollout_bank(pool,model,None,work,device,len(tasks[split]),None,choose,
                     log_path=directory/(split+'-episodes.jsonl'),tasks=tasks[split],greedy=True,
                     source='calibration',keep_value_records=True)
                if len(rows)!=len(tasks[split]):raise ValueError('Incomplete critic calibration games')
                data[split]=thin_records(records,cfg['states_per_game']);outcomes[split]=rows
                del records
            baseline=evaluate(model,data['development'],outcomes['development'],device)
            unseen_before=evaluate(model,data['unseen'],outcomes['unseen'],device)
            json_write(directory/'before.json',{'development':baseline,'unseen':unseen_before})
            for n,p in model.named_parameters():p.requires_grad_(value_parameter(n))
            for group in optimizer.param_groups:group['lr']=cfg['learning_rate']
            allowed={n:p for n,p in model.named_parameters() if value_parameter(n)}
            # Hold episodes/decks together in evaluation; balance the five idols
            # in optimization instead of letting the largest score scale dominate.
            grouped=defaultdict(list)
            for row in data['fit']:grouped[row['profile']].append(row)
            rng=random.Random(150915)
            best=None;history=[]
            for epoch in range(cfg['epochs']):
                losses=[]
                for step in range(cfg['steps_per_epoch']):
                    batch_rows=[]
                    for pid in sorted(grouped):batch_rows.extend(rng.choices(grouped[pid],k=cfg['batch_per_profile']))
                    rng.shuffle(batch_rows);optimizer.zero_grad(set_to_none=True)
                    loss_total=0.
                    for offset in range(0,len(batch_rows),24):
                        chunk=batch_rows[offset:offset+24]
                        mean,atoms=model.value_outputs(collate([r['encoded'] for r in chunk],device))
                        targets=torch.tensor([r['return'] for r in chunk],device=device)
                        loss=(quantile_loss(atoms,targets)+.25*torch.nn.functional.smooth_l1_loss(mean,targets,reduction='none')).sum()/len(batch_rows)
                        if not torch.isfinite(loss):raise FloatingPointError('Nonfinite calibration loss')
                        loss.backward();loss_total+=float(loss.detach())
                    torch.nn.utils.clip_grad_norm_(list(allowed.values()),1.,error_if_nonfinite=True)
                    optimizer.step();losses.append(loss_total)
                dev=evaluate(model,data['development'],outcomes['development'],device)
                result={'epoch':epoch+1,'fit_loss':statistics.mean(losses),'development':dev}
                history.append(result);json_write(directory/'history.json',history)
                publish('critic_fitting',critic_calibration={'epoch':epoch+1,'epochs':cfg['epochs'],
                    'actor_frozen':True,'best4_mae':dev['macro_best4_mae'],'quantile_loss':dev['macro_quantile_loss']})
                if best is None or dev['macro_best4_mae']<best['evaluation']['macro_best4_mae']:
                    best={'epoch':epoch+1,'evaluation':dev,
                          'parameters':{n:p.detach().clone() for n,p in allowed.items()},
                          'optimizer':{n:copy.deepcopy(optimizer.state.get(p,{})) for n,p in allowed.items()}}
            with torch.no_grad():
                for n,p in allowed.items():p.copy_(best['parameters'][n]);optimizer.state[p]=best['optimizer'][n]
            unseen_after=evaluate(model,data['unseen'],outcomes['unseen'],device)
            selected=best['evaluation']
            passed=(selected['macro_best4_mae'] < baseline['macro_best4_mae']
                    and selected['macro_quantile_loss'] < baseline['macro_quantile_loss']
                    and unseen_after['macro_quantile_loss'] <= unseen_before['macro_quantile_loss']*1.05
                    and unseen_after['macro_best4_mae'] <= unseen_before['macro_best4_mae']*1.10)
            report={'status':'passed' if passed else 'failed','selected_epoch':best['epoch'],
                    'before':baseline,'after':selected,'unseen_before':unseen_before,'unseen_after':unseen_after,
                    'games':{k:len(v) for k,v in outcomes.items()},'value_states':{k:len(v) for k,v in data.items()},
                    'actor_sha256':frozen_actor,'actor_unchanged':frozen_actor==state_digest(model,lambda n:n.startswith(('actor.', 'actor_relational.')) or 'policy_head' in n),
                    'non_exam_value_parameters_unchanged':before==state_digest(model,lambda n:not value_parameter(n)),
                    'wall_seconds':time.monotonic()-start,'policy_version':config['_policy_version'],
                    'value_target':'Own real terminal score distribution; Best-of-4 integrated once. No sibling-state max labels, no theoretical ceiling claim.',
                    'selection':'Development seeds only; unseen-loadout quantile-loss nonregression gate; original fixed validation untouched.'}
            if not report['actor_unchanged'] or not report['non_exam_value_parameters_unchanged']:raise ValueError('Calibration altered frozen parameters')
            json_write(directory/'report.json',report)
            if not passed:raise ValueError('Critic calibration did not pass held-out validation gate')
            return report
    finally:
        for n,p in model.named_parameters():p.requires_grad_(original_flags[n])
        for group,rate in zip(optimizer.param_groups,rates):group['lr']=rate
        optimizer.zero_grad(set_to_none=True)
        random.setstate(rng_state)
