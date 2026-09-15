"""Best-of-K objectives, distinct from an ever-growing record maximum.

For independent complete exams R_i, sum_i grad(log p_i) * (M-M_{-i})
is a score-function estimator of grad E[max_i R_i]. Other outcomes form an
action-independent baseline for exam i; environment randomness is not optimized.
PPO clipping, advantage scaling, and search distillation remain approximations.
"""
import math
import statistics
import copy
from collections import defaultdict


def group_credit(values):
    if len(values) < 2 or any(not math.isfinite(v) for v in values):
        raise ValueError('Best-of credit requires finite independent complete outcomes')
    maximum = max(values)
    return maximum, [maximum - max(values[:i] + values[i+1:]) for i in range(len(values))]


def apply_exam_credit(rows, value, credit, replicas, prefix, branch, peer_max=None):
    for row in rows:
        if row['encoded'].phase != 0 or not math.isclose(row['return'], value):
            raise ValueError('Best-of exam credit must retain its own real terminal return')
        row.update(prefix_id=prefix, branch_id=branch, fork_replicas=replicas,
                   loss_weight=1/replicas, policy_advantage=replicas*credit,
                   policy_advantage_kind='best_of_k_leave_one_out_max',
                   own_terminal_return=value, group_marginal_gain=credit,peer_max_return=peer_max)


def empirical_best(values, k=4):
    """E[max of K draws] from an empirical return distribution, with replacement.

Used ONLY as a bounded-search heuristic. It is not an unbiased certificate of
the true tail: few/adaptively collected samples and scalar bootstraps limit it.
"""
    if type(k) is not int or k < 1 or not values or any(not math.isfinite(v) for v in values):
        raise ValueError('Invalid empirical Best-of-K distribution')
    ordered = sorted(values)
    n = len(ordered)
    return math.fsum(value * (((i+1)/n)**k-(i/n)**k) for i,value in enumerate(ordered))


def summarize_groups(groups):
    if not groups:
        return None
    profiles = {}
    for profile in sorted({g['profile'] for g in groups}):
        rows = [g for g in groups if g['profile'] == profile]
        profiles[profile] = {'groups':len(rows),
            'best_of_k':statistics.mean(max(g['raw_scores']) for g in rows),
            'normalized_best_of_k':statistics.mean(max(g['returns']) for g in rows),
            'mean_score':statistics.mean(statistics.mean(g['raw_scores']) for g in rows),
            'minimum_score':statistics.mean(min(g['raw_scores']) for g in rows)}
    return {'objective':'best_of_k','replicas':sorted({g['replicas'] for g in groups}),
            'groups':len(groups),'profiles':profiles,
            'normalized_macro_best':statistics.mean(p['normalized_best_of_k'] for p in profiles.values())}


def repeat_bank_tasks(tasks, next_seed, replicas=4):
    expanded=[]
    for task in tasks:
        prefix='bank:'+str(task['replay_seed'])
        for branch in range(replicas):
            current=copy.deepcopy(task)
            if branch:
                current['replay_seed']=next_seed
                next_seed+=1
            current['metadata'].update(prefix_id=prefix,branch_id=branch,fork_replicas=replicas)
            expanded.append(current)
    return expanded,next_seed


def apply_bank_returns(records, results, tasks):
    expected={(t['metadata']['prefix_id'],t['metadata']['branch_id']) for t in tasks}
    if len(expected)!=len(tasks) or {(s['prefix_id'],s['branch_id']) for s in results}!=expected or len(results)!=len(tasks):
        raise ValueError('Bank repeated exams are incomplete or duplicated')
    groups=defaultdict(list)
    for s in results:groups[s['prefix_id']].append(s)
    plans=[]
    for prefix,outcomes in groups.items():
        outcomes.sort(key=lambda s:s['branch_id'])
        replicas=outcomes[0]['fork_replicas']
        if [s['branch_id'] for s in outcomes]!=list(range(replicas)):
            raise ValueError('Bank branch identities changed')
        for key in ('policy_version','entry_sha256','score_scale','resolved_turn_types','exploration_mode'):
            if any(s.get(key)!=outcomes[0].get(key) for s in outcomes):
                raise ValueError('Bank repeat changed '+key)
        if len({s['seed'] for s in outcomes})!=replicas or len({s['action_rng_seed'] for s in outcomes})!=replicas:
            raise ValueError('Bank repeats reused randomness')
        values=[s['normalized_score'] for s in outcomes]
        maximum,credits=group_credit(values)
        for branch,s in enumerate(outcomes):
            rows=[r for r in records if r['prefix_id']==prefix and r['branch_id']==branch]
            if not rows or any(r['encoded'].phase!=0 or not math.isclose(r['return'],values[branch]) for r in rows):
                raise ValueError('Bank outcomes do not match exam records')
            plans.append((rows,values[branch],credits[branch],replicas,prefix,branch,
                          max(values[:branch]+values[branch+1:])))
    for plan in plans:apply_exam_credit(*plan)
    return [{'prefix_id':prefix,'profile':outcomes[0]['profile'],'replicas':len(outcomes),
             'policy_version':outcomes[0]['policy_version'],'objective':'best_of_k',
             'raw_scores':[s['score'] for s in outcomes],
             'returns':[s['normalized_score'] for s in outcomes]} for prefix,outcomes in groups.items()]


def fixed_play_summary(rows, replicas=4):
    groups=defaultdict(list)
    for row in rows:groups[row['play_loadout_id']].append(row)
    summaries=[]
    for loadout,outcomes in sorted(groups.items()):
        outcomes.sort(key=lambda s:s['seed'])
        if len(outcomes)%replicas:raise ValueError('Fixed-play seed groups must be complete')
        for start in range(0,len(outcomes),replicas):
            group=outcomes[start:start+replicas]
            if any(s['entry_sha256']!=group[0]['entry_sha256'] or s['score_scale']!=group[0]['score_scale'] for s in group):
                raise ValueError('Fixed-play group must use the same pre-opening loadout')
            summaries.append({'prefix_id':f'fixed:{loadout}:{start//replicas}',
                'profile':group[0]['profile'],'replicas':replicas,
                'raw_scores':[s['score'] for s in group],'returns':[s['normalized_score'] for s in group],
                'environment_seeds':[s['seed'] for s in group]})
    return {**summarize_groups(summaries),'group_results':summaries,
            'grouping':'Prespecified consecutive seed groups per fixed loadout; best of 4, never best of 8'}


def construction_evaluation(pool,model,rows,config,device,choose,output,label):
    """Three fresh DEVELOPMENT continuations of each newly evaluated loadout."""
    from .practice import retained_metadata
    from .bank_rollout import rollout_bank
    tasks=[]
    for row in rows:
        for branch in range(1,4):
            seed=2_000_000_000+4*row['seed']+branch
            if not 0<=seed<2**32:raise ValueError('Evaluation repeat seed exceeds RNG range')
            tasks.append({'key':row['entry_sha256'],'entry':copy.deepcopy(row['entry']),
                'replay_seed':seed,'metadata':{**retained_metadata(row),
                    'evaluation_parent_seed':row['seed'],'branch_id':branch}})
    if len({t['replay_seed'] for t in tasks})!=len(tasks):raise ValueError('Duplicate evaluation repeat seeds')
    from pathlib import Path
    records,repeated,_=rollout_bank(pool,model,None,config,device,len(tasks),None,choose,
        tasks=tasks,greedy=True,source='validation_best4',log_path=Path(output)/(label+'-repeats.jsonl'))
    if records or len(repeated)!=len(tasks):raise ValueError('Invalid four-exam evaluation')
    groups=defaultdict(list)
    for row in repeated:groups[row['evaluation_parent_seed']].append(row)
    summaries=[]
    for parent in rows:
        outcomes=[parent,*sorted(groups[parent['seed']],key=lambda s:s['branch_id'])]
        if len(outcomes)!=4 or any(s['entry_sha256']!=parent['entry_sha256'] for s in outcomes):
            raise ValueError('Evaluation repeats changed the constructed deck')
        summaries.append({'prefix_id':'evaluation:'+str(parent['seed']),'profile':parent['profile'],
            'replicas':4,'raw_scores':[s['score'] for s in outcomes],
            'returns':[s['normalized_score'] for s in outcomes],
            'environment_seeds':[s['seed'] for s in outcomes]})
    return {**summarize_groups(summaries),'group_results':summaries,
            'search':False,'split':'development' if not label.startswith('test-') else 'held-out-test',
            'games':len(rows)*4,'new_constructions':len(rows)}


def comparison(current,baseline):
    old=baseline['profiles'];new=current['profiles']
    if new.keys()!=old.keys():raise ValueError('Best-of-4 evaluation profiles differ')
    a=current.get('group_results',[]);b=baseline.get('group_results',[])
    def signature(rows):
        value={r['prefix_id']:r['environment_seeds'] for r in rows}
        if len(value)!=len(rows):raise ValueError('Duplicate evaluation groups')
        return value
    if signature(a)!=signature(b):
        raise ValueError('Best-of-4 evaluation seed groups differ')
    return math.exp(statistics.mean(math.log((row['normalized_best_of_k']+.25)/
                    (old[p]['normalized_best_of_k']+.25)) for p,row in new.items()))
