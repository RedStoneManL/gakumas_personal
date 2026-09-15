"""Complete-episode MC or optional GAE; terminal score objective keeps gamma=1."""
import math
from collections import defaultdict


def estimate(records, mode='mc', gae_lambda=0.98):
    if mode=='mc':
        return [r.get('policy_advantage',r['return']-r['old_value']) for r in records],[r['return'] for r in records]
    if any(r.get('fork_replicas') for r in records):
        raise ValueError('Replicated continuation targets require MC, not a fabricated GAE episode')
    if mode!='gae' or not 0<=gae_lambda<=1:raise ValueError('invalid advantage mode/lambda')
    grouped=defaultdict(list)
    for i,row in enumerate(records):grouped[row['episode_id']].append(i)
    advantages=[0.0]*len(records);targets=[0.0]*len(records)
    for indices in grouped.values():
        if not records[indices[-1]].get('terminal') or any(records[i].get('terminal') for i in indices[:-1]):
            raise ValueError('GAE requires exactly one complete terminal boundary per episode')
        final_return=records[indices[-1]]['return']
        if any(not math.isclose(records[i]['return'],final_return) for i in indices):
            raise ValueError('inconsistent complete-episode return')
        following_value=0.0;advantage=0.0
        for position,i in reversed(list(enumerate(indices))):
            row=records[i]
            reward=final_return if position==len(indices)-1 else 0.0
            delta=reward+following_value-row['old_value']
            advantage=delta+gae_lambda*advantage
            advantages[i]=advantage;targets[i]=advantage+row['old_value']
            following_value=row['old_value']
    return advantages,targets


def assert_current_policy(records,expected):
    if expected is None:return
    if any(r.get('policy_version')!=expected for r in records):
        raise ValueError('PPO buffer includes a stale or unversioned policy record')
