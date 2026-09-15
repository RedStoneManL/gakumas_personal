"""Frozen public loadouts for exam-only DEVELOPMENT evaluation, never PPO."""
import copy
import hashlib
import json
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from .checkpoint import json_write
from .practice import retained_metadata
from .bank_rollout import rollout_bank


def prepare_suite(output, config):
    path=Path(output)/'play-suite.json'
    replicas=config.get('practice',{}).get('play_evaluation',{}).get('replicas',2)
    if type(replicas) is not int or not 1<=replicas<=32:raise ValueError('Invalid evaluation replica count')
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old['replicas']==replicas:return old
        # Only migrate the NEW continuation's copied suite. Keep loadouts and
        # old seeds; expanding evaluation establishes its own reference curve.
        archive=Path(output)/f'previous-play-suite-{old["replicas"]}-to-{replicas}'
        archive.mkdir(exist_ok=False)
        for name in ('play-suite.json','play-baseline.json','play-validation-history.jsonl'):
            src=Path(output)/name
            if src.exists():src.rename(archive/name)
        grouped=defaultdict(list)
        for task in old['tasks']:grouped[task['metadata']['play_loadout_id']].append(task)
        tasks=[]
        for i, previous in sorted(grouped.items()):
            for j in range(replicas):
                task=copy.deepcopy(previous[j] if j<len(previous) else previous[0])
                if j>=len(previous):task['replay_seed']=1_860_000_000+i*1000+j
                tasks.append(task)
        suite={**old,'schema':'arena-fixed-play-suite/2','replicas':replicas,'tasks':tasks,
               'reference_reset':{'reason':'More independent seeds on unchanged public loadouts',
                                  'previous_replicas':old['replicas'],'archive':str(archive),
                                  'created_at':datetime.now(timezone.utc).isoformat()}}
        if len({t['replay_seed'] for t in tasks})!=len(tasks):raise ValueError('Evaluation seeds overlap')
        json_write(path,suite)
        return suite
    profiles=[p['id'] for p in config['_profiles']]
    initial=Path(output)/'validation-initial-episodes.jsonl'
    recent=sorted(Path(output).glob('validation-[0-9]*-episodes.jsonl'))
    sources=[initial]+recent[-1:]
    rows=[]
    for src in sources:
        rows.extend(json.loads(line) for line in src.read_text(encoding='utf-8').splitlines() if line.strip())
    selected=[]
    for profile in profiles:
        for memory in ('none','hif'):
            for has_drinks in (False,True):
                eligible=[r for r in rows if r['profile']==profile and r['memory_mode']==memory
                          and bool(r['drink_capacity'])==has_drinks]
                if not eligible:raise ValueError(f'Missing fixed-play stratum {profile}/{memory}/{has_drinks}')
                # Deterministic mixed-age selection without looking at scores.
                pick=eligible[-1] if has_drinks else eligible[0]
                selected.append(pick)
    tasks=[]
    for i,row in enumerate(selected):
        for j in range(replicas):
            meta=retained_metadata(row)
            meta['exploration_mode']='normal'
            meta['play_loadout_id']=i
            tasks.append({'key':row['entry_sha256'],'entry':copy.deepcopy(row['entry']),
                          'metadata':meta,'replay_seed':1_850_000_000+i*replicas+j})
    suite={'schema':'arena-fixed-play-suite/1','split':'development-only',
           'selection':'per-profile x memory none/hif x drink absent/present; no score selection',
           'source_files':[{ 'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],
           'replicas':replicas,'loadout_count':len(selected),'tasks':tasks}
    json_write(path,suite)
    return suite


def paired_comparison(result, baseline, bootstrap_reps=1000):
    """Paired seeds, profile-stratified loadout/seed bootstrap, descriptive CI."""
    def keyed(value):
        rows=value['episodes']
        mapping={(r['play_loadout_id'],r['seed']):r for r in rows}
        if len(mapping)!=len(rows):raise ValueError('Duplicate fixed-play outcome')
        return mapping
    current, old=keyed(result),keyed(baseline)
    if current.keys()!=old.keys():raise ValueError('Fixed-play seeds or loadouts changed')
    groups=defaultdict(lambda:defaultdict(list))
    for key,r in current.items():
        b=old[key]
        if any(r.get(k)!=b.get(k) for k in ('profile','entry_sha256','score_scale','resolved_turn_types')):
            raise ValueError('Fixed-play public conditions changed')
        groups[r['profile']][key[0]].append((r['score']-b['score'],r['normalized_score']-b['normalized_score']))
    rng=random.Random(310913)
    def interval(x):
        x=sorted(x)
        return [x[int(.025*(len(x)-1))],x[int(.975*(len(x)-1))]]
    def mean(loadouts, column):
        return statistics.mean(statistics.mean(v[column] for v in rows) for rows in loadouts.values())
    sampled={p:[] for p in groups}
    for _ in range(bootstrap_reps):
        for p,loadouts in groups.items():
            keys=list(loadouts)
            draws=[]
            for key in rng.choices(keys,k=len(keys)):
                rows=loadouts[key]
                draws.append(statistics.mean(v[1] for v in rng.choices(rows,k=len(rows))))
            sampled[p].append(statistics.mean(draws))
    aggregate=[statistics.mean(sampled[p][i] for p in sampled) for i in range(bootstrap_reps)]
    return {'episodes':len(current),'loadouts':sum(map(len,groups.values())),
            'normalized_gain':statistics.mean(mean(g,1) for g in groups.values()),
            'normalized_gain_ci95':interval(aggregate),
            'profiles':{p:{'episodes':sum(map(len,g.values())),'loadouts':len(g),
                            'raw_gain':mean(g,0),'normalized_gain':mean(g,1),
                            'normalized_gain_ci95':interval(sampled[p])} for p,g in groups.items()},
            'method':'Paired seeds; equal profiles/loadouts; percentile bootstrap of loadouts then seeds',
            'note':'Development-only descriptive interval; not an anytime-valid test or independent training-seed comparison. Equal seeds need not couple every random event.'}


def evaluate_play(pool,model,config,device,suite,choose,output,label,describe):
    records,rows,_=rollout_bank(pool,model,None,config,device,len(suite['tasks']),None,choose,
        log_path=Path(output)/(label+'-episodes.jsonl'),tasks=suite['tasks'],greedy=True,source='validation_fixed')
    if records:raise ValueError('Evaluation generated training records')
    result=describe(rows)
    if suite['replicas']%4==0:
        from .best_of import fixed_play_summary
        result['best_of_4']=fixed_play_summary(rows)
    result.update(evaluation_kind='fixed_public_loadouts',split='development-only',
                  loadout_count=suite['loadout_count'],replicas=suite['replicas'],
                  reference_reset=suite.get('reference_reset'),policy_version=config['_policy_version'])
    json_write(Path(output)/(label+'.json'),result)
    return result
