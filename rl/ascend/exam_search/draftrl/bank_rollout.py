"""Fresh on-policy exams from remembered public, pre-opening loadouts."""
import copy
import hashlib
import json
import math
import random
import time
from collections import Counter
from .choice import ChoiceState
from .async_decisions import AsyncDecisions
from .encoding import encode_exam
from . import stage_progress
from .practice import routed_parameters, auxiliary_controller
from . import keycard_focus
from .duplicate_limits import limit as copy_limit, validate as validate_copy_limit, overrides as copy_overrides


def rollout_bank(pool,model,bank,config,device,count,exploration,choose,log_path=None,
                 *,tasks=None,greedy=False,source='bank_exam',keep_value_records=False):
    if keep_value_records and (not greedy or bank is not None):
        raise ValueError('Value calibration must use explicit frozen-policy tasks')
    tasks=bank.sample(count) if tasks is None else tasks
    if greedy and bank is not None:
        raise ValueError('Evaluation must not modify the training bank')
    if bank is not None:
        tasks = keycard_focus.filter_bank_tasks(tasks, config)
    if not tasks:return [],[],0
    pending=iter(tasks);active={};records=[];summaries=[];meaningful=0
    started_at=time.monotonic()
    last_log=started_at
    router = config.get('_search_router') if not greedy else None
    controller = auxiliary_controller(config) if not greedy else None
    flow = AsyncDecisions(router) if router else None
    from . import distributed as _dist
    stage_progress.begin(source,len(tasks),'episodes',
        shards=_dist.ACTIVE.size if _dist.ACTIVE is not None else 1)
    print(json.dumps({'event':'bank_rollout_begin','count':len(tasks),'policy_version':config['_policy_version']}),flush=True)
    while True:
        for i in range(min(config['workers'],len(tasks))):
            if i in active:continue
            task=next(pending,None)
            if task is None:continue
            if controller is not None and task['metadata'].get('fork_replicas') is not None:
                if task['metadata'].get('controller_contract') != controller:
                    raise ValueError('Auxiliary continuation has a different behavior controller')
            # Historical fixed-play evaluation remains an explicit unchanged
            # diagnostic. Every PPO-producing bank/fork entry must obey the cap.
            if not greedy and copy_limit(config) is not None:
                validate_copy_limit(task['entry']['cards'], config['_card_families'], copy_limit(config),copy_overrides(config))
            # Arena initializes opening effects and shuffles from a new seed.
            # There is no restore of a historical hand/deck order or engine RNG.
            pool.send(i,'reset',(task['entry'],task['replay_seed']))
            _answer=pool.receive(i)
            obs=_answer['observation']
            if obs['result']['terminated'] or obs['result']['truncated']:
                raise ValueError('bank opening is not a live exam')
            active[i]={'task':task,'obs':obs,'pre_encoded':_answer.get('encoded'),'choice':None,'records':[],
                       'keycard_tracking':keycard_focus.tracker(task['entry']),
                       'submissions':[],'choice_steps':[],'steps':0,'drink_used':0,
                       'rng':random.Random(task['replay_seed']+40_000_000)}
        if not active:break
        blocked=set(flow.pending) if flow else set()
        ready=flow.poll(wait=bool(blocked) and len(blocked)==len(active)) if flow else []
        ids=[i for i in active if i not in blocked];examples=[]
        for i in ids:
            row=active[i]
            if row['obs'].get('choice'):
                if row['choice'] is None:row['choice']=ChoiceState(row['obs'])
                examples.append(row['choice'].encode())
            else:examples.append(row['pre_encoded'] if row.get('pre_encoded') is not None else encode_exam(row['obs']))
        modes=[active[i]['task']['metadata'].get('exploration_mode','normal') for i in ids]
        overrides=routed_parameters(examples,modes,exploration,config)
        if ids:
            actions,logps,values,settings,diagnostics=choose(model,examples,device,greedy,'policy',
                [active[i]['rng'] for i in ids],exploration,settings_override=overrides)
        else:
            actions,logps,values,settings,diagnostics=[],[],[],[],[]
        proposals=list(zip(ids,examples,actions,logps,values,settings,diagnostics))
        if flow is not None:
            items = [
                {'worker': i, 'encoded': e, 'enabled': bool(row['task']['metadata'].get('search_enabled', False)),
                 'entry': row['task']['entry'], 'observation': row['obs'],
                 'profile': row['task']['metadata']['profile'], 'score_scale': row['task']['metadata']['score_scale'],
                 'episode_id': f"{source}:{row['task']['replay_seed']}",
                 'partial_selection': row['choice'].selected if row['choice'] else []}
                for i, e in zip(ids, examples) for row in [active[i]]]
            ready.extend(flow.submit(pool,items,proposals,config['_policy_version']))
        else:
            ready.extend((*proposal,{'loss_kind':'ppo'}) for proposal in proposals)
        awaiting=[]
        for i,e,action,logp,value,setting,diagnostic,extra in ready:
            row=active[i];task=row['task'];meta=task['metadata']
            command=e.submissions[action]
            row['records'].append({'encoded':e,'action':action,'old_logp':logp,'old_value':value,
                'exploration':setting,'profile':meta['profile'],'plan':meta['plan'],
                'course_id':meta['course_id'],'drink_capacity':meta['drink_capacity'],
                'memory_mode':meta['memory_mode'],'memory_capacity':meta['memory_capacity'],
                'condition_cell':meta['condition_cell'],'sampling_source':source,
                'exploration_mode':meta.get('exploration_mode','normal'),
                'prefix_id':meta.get('prefix_id'),'branch_id':meta.get('branch_id'),
                'episode_id':f"{source}:{task['replay_seed']}",'policy_version':config['_policy_version'],
                'terminal':False,**diagnostic,**extra})
            if controller is not None:
                row['records'][-1]['controller_contract'] = dict(controller)
            row['steps']+=1;meaningful+=len(e.submissions)>1
            if row['steps']>config['max_episode_decisions']:raise RuntimeError('bank decision guard exceeded')
            if row['choice'] is not None:
                row['choice_steps'].append({'native_decision_version':row['obs']['decision_version'],
                    'selected_before':list(row['choice'].selected),'command':command})
                command=row['choice'].apply(command)
                if command is None:continue
                row['choice']=None
            row['drink_used']+=command.get('action',{}).get('type')=='drink'
            keycard_focus.observe(row['keycard_tracking'],row['obs'],command)
            row['submissions'].append(command);pool.send(i,'step',command);awaiting.append(i)
        for i in awaiting:
            row=active[i];task=row['task'];_answer=pool.receive(i)
            row['obs']=_answer['observation'];row['pre_encoded']=_answer.get('encoded')
            result=row['obs']['result']
            if result['truncated']:raise RuntimeError('truncated bank game cannot be a PPO target')
            if not result['terminated']:continue
            score=result['final_score']
            if score is None or not math.isfinite(score):raise RuntimeError('invalid bank terminal score')
            meta=copy.deepcopy(task['metadata']);normalized=score/meta['score_scale']
            if controller is not None:
                meta['controller_contract'] = dict(controller)
            else:
                # Retained loadout metadata describes an old controller. Do
                # not label greedy evaluation or legacy acting-search as the
                # auxiliary rollout that originally supplied this loadout.
                meta.pop('controller_contract', None)
            for record in row['records']:record['return']=normalized
            row['records'][-1]['terminal']=True
            if not greedy:records.extend(row['records'])
            elif keep_value_records:
                for record in row['records']:
                    record.update(loss_kind='value_only', old_logp=None)
                records.extend(row['records'])
            sleeps={c['instance_id'] for c in task['entry']['cards'] if c['definition_id']==23}
            meta.update(seed=task['replay_seed'],entry=task['entry'],sampling_source=source,
                environment_seed=task['replay_seed'],action_rng_seed=task['replay_seed']+40_000_000,
                exploration_schedule_snapshot=exploration,
                keycard_usage=keycard_focus.finish(row['keycard_tracking']),
                schema='arena-generalist-joint-search/1',source_sha256=config['_policy_version'].split(':',1)[0],
                entry_sha256=hashlib.sha256(json.dumps(task['entry'],sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                bank_key=task['key'],policy_version=config['_policy_version'],score=score,normalized_score=normalized,
                submissions=row['submissions'],choice_steps=row['choice_steps'],decisions=row['steps'],
                resolved_turn_types=list(row['obs']['context']['turn_types']),
                removed_sleep_count=len(sleeps.intersection(row['obs']['zones']['removed'])),
                turns_elapsed=row['obs']['state']['turnsElapsed'],final_stamina=row['obs']['state']['stamina'],
                drinks_used=row['drink_used'],memory_phase_decisions=0,
                draft_choices=[],guidance_choices=[],drink_choices=[],memory_choices=[],
                draft_finish_reason='historical_loadout_replayed_with_current_policy')
            if log_path:
                with log_path.open('a',encoding='utf-8') as f:f.write(json.dumps(meta,ensure_ascii=False)+'\n')
            summaries.append({k:v for k,v in meta.items() if k not in ('entry','submissions')})
            if bank is not None:bank.feedback(task['key'],normalized)
            del active[i]
        if time.monotonic()-last_log>30:
            _done=len(summaries);_elapsed=time.monotonic()-started_at
            _rate=_done/_elapsed if _elapsed>0 and _done else 0.
            _batch=str(config.get('_policy_version','')).split(':')[1:2]
            print('[PROGRESS] batch=%s stage=%-9s episodes %s/%s (%s%%) | %s/min | elapsed %sm | eta %sm | %d live' % (
                _batch[0] if _batch else '?', source, _done, len(tasks),
                round(100.*_done/len(tasks),1), round(_rate*60,1), round(_elapsed/60,1),
                round((len(tasks)-_done)/_rate/60,1) if _rate else 0, len(active)), flush=True)
            print(json.dumps({'event':'bank_rollout','source':source,
                'completed':_done,'total':len(tasks),'active':len(active),
                'percent':round(100.*_done/len(tasks),1),
                'episodes_per_minute':round(_rate*60,1),
                'elapsed_minutes':round(_elapsed/60,1),
                'eta_minutes':round((len(tasks)-_done)/_rate/60,1) if _rate else None}),flush=True)
            stage_progress.update(_done,len(active))
            last_log=time.monotonic()
    if flow: flow.assert_drained()
    stage_progress.end()
    print(json.dumps({'event':'bank_rollout_ready','episodes':len(summaries),'meaningful_decisions':meaningful,
                      'total':len(tasks),'source':source,
                      'elapsed_minutes':round((time.monotonic()-started_at)/60,1),
                      'profiles':dict(Counter(r['profile'] for r in summaries))}),flush=True)
    return records,summaries,meaningful
