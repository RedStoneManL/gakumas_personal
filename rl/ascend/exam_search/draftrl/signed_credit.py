"""Frozen pre-action control variate for the existing Best-of-4 objective."""
import hashlib
import json
import math
from collections import Counter, defaultdict
from .learning_settings import SIGNED

KIND = 'best_of_k_state_contribution'


def prepare(records, settings):
    if settings != SIGNED:
        raise ValueError('Unvalidated signed credit configuration')
    plans = []
    for row in records:
        if row['encoded'].phase != 0:
            continue
        atoms = row.get('old_return_atoms')
        if (row.get('value_prediction_mode') != 'frozen_pre_action' or not isinstance(atoms, list)
                or len(atoms) != settings['quantiles'] or any(not math.isfinite(x) for x in atoms)):
            raise ValueError('Signed credit requires frozen pre-action return atoms')
        peer, own, gain = row.get('peer_max_return'), row['return'], row.get('group_marginal_gain')
        if (row.get('fork_replicas') != 4 or peer is None or gain is None
                or not all(math.isfinite(x) for x in (peer, own, gain))
                or not math.isclose(max(own-peer, 0.), gain, abs_tol=1e-6)
                or not math.isclose(row['own_terminal_return'], own, abs_tol=1e-6)):
            raise ValueError('Signed credit lost its real four-game contribution')
        # Peer outcomes are used only for the training control variate. They
        # never enter the actor observation or change the actual own return.
        baseline = math.fsum(max(atom-peer, 0.) for atom in atoms)/len(atoms)
        plans.append((row, baseline, 4*(gain-baseline)))
    if not plans:
        raise ValueError('Signed credit has no exam records')
    for row, baseline, advantage in plans:
        row.update(policy_advantage_kind=KIND, policy_advantage=advantage,
                   contribution_baseline=baseline, contribution_rms_floor=settings['rms_floor'])
    return summarize(records)


def summarize(records, accepted=None):
    groups = defaultdict(Counter)
    proof = hashlib.sha256()
    samples = []
    for index, row in enumerate(records):
        if row.get('policy_advantage_kind') != KIND:
            continue
        active = row['loss_kind']=='ppo' and len(row['encoded'].submissions)>1
        sign = 'positive' if row['policy_advantage']>0 else 'negative' if row['policy_advantage']<0 else 'zero'
        for key in ('all_exam', 'profile:'+row['profile'], 'loss:'+row['loss_kind']):
            groups[key]['records'] += 1
            groups[key][sign] += 1
            if active:
                groups[key]['ppo_meaningful'] += 1
                groups[key]['ppo_'+sign] += 1
                if accepted is not None and index in accepted:
                    groups[key]['accepted_ppo_'+sign] += 1
        proof.update(json.dumps([index,row['policy_version'],row['old_return_atoms'],
                                row['peer_max_return'],row['return'],row['policy_advantage']],
                               separators=(',', ':'),allow_nan=False).encode())
        if active and sum(s['profile']==row['profile'] and s['sign']==sign for s in samples)<2:
            samples.append({'profile':row['profile'],'sign':sign,'record_index':index,
                'peer_max':row['peer_max_return'],'own_return':row['return'],
                'actual_contribution':row['group_marginal_gain'],
                'baseline':row['contribution_baseline'],'advantage':row['policy_advantage']})
    return {'mode':KIND,'groups':dict(groups),'records_sha256':proof.hexdigest(),
            'frozen_pre_action_baselines':True,'own_terminal_targets_preserved':True,
            'samples':samples,'unit':'normalized score; raw signed credit before profile RMS scaling',
            'accepted_counts_available':accepted is not None}
