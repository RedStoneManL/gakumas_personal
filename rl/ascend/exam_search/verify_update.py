"""Read-only CPU audit of a committed checkpoint, separate from live log tails."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def coverage_problems(metric, config):
    joint = metric.get('update_coverage', {})
    setting = config.get('critic_completion')
    if not setting:
        return [] if joint.get('accepted_fraction') == 1 else ['Some records unused by accepted updates']
    problems = []
    def check(ok, message):
        if not ok: problems.append(message)
    check(setting == {'enabled': True, 'minimum_passes': 1, 'actor_frozen': True},
          'Unaudited critic completion configuration')
    total, used = joint.get('record_count', 0), joint.get('accepted_unique', 0)
    done = metric.get('critic_completion') or {}
    coverage = metric.get('critic_update_coverage') or {}
    check(total > 0 and 0 < used <= total, 'Invalid joint update counts')
    check(coverage.get('record_count') == total and coverage.get('accepted_unique') == total
          and coverage.get('accepted_fraction') == 1
          and all(g.get('accepted_fraction') == 1 for g in coverage.get('groups', {}).values()),
          'Critic has unused rollout records')
    check(done.get('coverage') == coverage and done.get('completed_records') == total-used,
          'Critic completion coverage/linkage differs')
    check(done.get('actor_unchanged') is True and done.get('policy_replay') is False
          and len(done.get('actor_sha256_before', '')) == 64
          and done.get('actor_sha256_before') == done.get('actor_sha256_after'),
          'Missing frozen actor evidence for critic completion')
    check((total-used == 0 and done.get('optimizer_steps') == 0)
          or (total-used > 0 and done.get('optimizer_steps', 0) > 0),
          'Critic-only optimizer count differs from remaining records')
    if used < total:
        check(metric.get('kl_early_stop') is True and metric.get('ppo_stop_reason') in ('block_kl','epoch_kl'),
              'Partial actor update lacks an explicit KL stop')
    return problems


def learning_problems(metric, config):
    if not config.get('signed_exam_credit'):
        return []
    problems=[]
    def check(ok,message):
        if not ok:problems.append(message)
    credit=metric.get('signed_credit') or {};groups=credit.get('groups',{});all_exam=groups.get('all_exam',{})
    expected=metric.get('phase_decisions',{}).get('0',0)
    check(credit.get('mode')=='best_of_k_state_contribution' and expected>0
          and all_exam.get('records')==expected,'Signed credit does not cover all exam records')
    check(credit.get('frozen_pre_action_baselines') is True and credit.get('own_terminal_targets_preserved') is True
          and len(credit.get('records_sha256',''))==64,'Missing signed credit provenance')
    check(sum(all_exam.get(k,0) for k in ('positive','negative','zero'))==expected,'Signed credit counts differ')
    for row in credit.get('samples',[]):
        check(math.isclose(row['advantage'],4*(row['actual_contribution']-row['baseline']),abs_tol=1e-6),
              'Recorded signed contribution formula differs')
        check(math.isclose(row['actual_contribution'],max(row['own_return']-row['peer_max'],0.),abs_tol=1e-6),
              'Signed credit altered the Best4 contribution')
    learning=metric.get('search_learning') or {}
    label_count=(metric.get('search_records') or 0)+(metric.get('auxiliary_search_records') or 0)
    check(learning.get('roots')==label_count and 0<=learning.get('weighted_roots',-1)<=learning.get('roots',0),
          'Search learning direction counts differ')
    for key in ('mean_weight','mean_target_entropy','mean_prior_entropy','mean_behavior_entropy'):
        value=learning.get(key)
        check(isinstance(value,(int,float)) and math.isfinite(value) and 0<=value<=1.00001,
              'Missing or invalid search learning '+key)
    return problems


def search_record_problems(metric, config):
    """Separate action ownership, budget admission, evidence gates and CE weight."""
    problems=[]
    def check(ok, message):
        if not ok: problems.append(message)
    counts=(metric.get('search_batch') or {}).get('counts',{})
    actor=metric.get('search_records',0)
    raw=metric.get('auxiliary_search_roots',0)
    labels=metric.get('auxiliary_search_records',0)
    ppo=metric.get('ppo_records',0)
    if any(type(n) is not int or n<0 for n in (actor,raw,labels,ppo)):
        return ['Invalid search/PPO record counters']
    budget=counts.get('accepted_targets',0)
    check(type(budget) is int and budget>=0,'Invalid search budget-admission count')
    if type(budget) is not int or budget<0:
        return problems
    distributed=(metric.get('learner_world_size',config.get('learner_world_size',1)) or 1)>1
    if config.get('search',{}).get('execution_mode','act')=='auxiliary':
        auxiliary=metric.get('auxiliary_search') or {}
        check(actor==0,'Auxiliary search replaced real policy actions')
        check(0<=labels<=raw<=ppo,'Auxiliary roots/labels must be subsets of real PPO records')
        check(auxiliary.get('mode')=='peer_marginal' and auxiliary.get('roots')==raw
              and auxiliary.get('accepted_roots')==labels,'Auxiliary evidence-gate counts differ')
        rejected,weighted=auxiliary.get('rejected_roots'),auxiliary.get('weighted_roots')
        check(type(rejected) is int and rejected>=0 and rejected+labels==raw,
              'Auxiliary accepted/rejected evidence does not account for all roots')
        check(type(weighted) is int and 0<=weighted<=labels,'Auxiliary weighted-label count differs')
        learning=metric.get('search_learning') or {}
        check(learning.get('roots')==labels and learning.get('weighted_roots')==weighted,
              'Auxiliary CE direction counts differ')
        check(auxiliary.get('independent_heldout_validation') is False,
              'Auxiliary search evidence must not claim independent held-out validation')
        # search_batch is the main router's local counter; PPO statistics above
        # are reduced over learner ranks. Never multiply local counts by ranks.
        check(budget<=raw if distributed else budget==raw,
              'Auxiliary raw roots differ from comparable budget-admission counts')
    else:
        check(raw==0 and labels==0,'Legacy acting-search batch unexpectedly contains auxiliary labels')
        check(budget<=actor if distributed else budget==actor,
              'Search action records differ from comparable budget-admission counts')
    return problems


def audit(folder):
    folder = Path(folder)
    progress = read(folder/'progress.json')
    if progress.get('batches',0) == 0:
        return {'status':'pending','reason':'No published formal update yet','run':folder.name}
    import torch
    torch.set_num_threads(2)
    info = torch.load(folder/'latest.pt',map_location='cpu',weights_only=True)
    manifest = read(folder/'manifest.json')
    problems = []
    def check(condition, message):
        if not condition: problems.append(message)
    check(info['rl_source_sha256']==manifest['rl_source_sha256'],'Checkpoint and manifest revisions differ')
    check(info['training_config']==manifest['config'],'Checkpoint and manifest configs differ')
    check(info['arena_sha256']==manifest['arena_sha256'],'Arena metadata differs')
    check(info['search_version']==manifest['search_version'],'Search version metadata differs')
    check(all(torch.isfinite(t).all().item() for t in info['model_state'].values()),'Nonfinite model weights')
    check(all(torch.isfinite(t).all().item() for s in info['optimizer_state']['state'].values()
              for t in s.values() if isinstance(t,torch.Tensor)),'Nonfinite optimizer state')
    offset = info['committed_log_offsets'].get('metrics.jsonl',0)
    with (folder/'metrics.jsonl').open('rb') as stream:
        metrics = [json.loads(line) for line in stream.read(offset).splitlines() if line]
    last = metrics[-1] if metrics else {}
    check((last.get('batch'),last.get('decisions'))==(info['batches'],info['decisions']),
          'Committed metrics and checkpoint counters differ')
    for key in ('loss','policy_loss','search_loss','value_loss','kl','grad_norm'):
        check(isinstance(last.get(key),(float,int)) and math.isfinite(last[key]),'Missing/nonfinite '+key)
    counts = last.get('search_batch',{}).get('counts',{})
    check(last.get('fork_coverage',{}).get('coverage')==1,'Not every new deck received its repeat')
    check(last.get('optimizer_steps',0)>0,'No accepted optimizer update')
    current_revision = last.get('source_sha256') == info['rl_source_sha256']
    inherited_completion = bool(info['training_config'].get('critic_completion') and not current_revision)
    if not inherited_completion:
        problems.extend(coverage_problems(last, info['training_config']))
        problems.extend(learning_problems(last, info['training_config']))
        problems.extend(search_record_problems(last, info['training_config']))
    expected_profiles = {p['id'] for p in manifest['profiles']}
    check(set(last.get('profiles',{}))==expected_profiles,'Not all configured idols represented')
    best = info.get('committed_best')
    check(bool(best),'Missing committed best snapshot')
    if best:
        path = folder/best['path']
        check(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==best['sha256'],
              'Committed best snapshot hash differs')
    objective=info['training_config'].get('practice',{}).get('forks',{}).get('objective','mean')
    best4=info.get('committed_best4')
    # A continuation's inherited mean batch can precede its first best4 baseline.
    # Require a sealed best4 winner only once a best4 batch is actually committed.
    if last.get('construction_objective')=='best_of_k':
        check(bool(best4),'Missing committed Best-of-4 snapshot')
        if best4:
            path=folder/best4['path']
            check(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==best4['sha256'],
                  'Committed Best-of-4 snapshot hash differs')
        check(last.get('construction_replicas')==4,'Best-of-4 batch has incorrect repeat count')
    initial = torch.load(folder/'initial.pt',map_location='cpu',weights_only=True)
    added=set(info['model_state'])-set(initial['model_state'])
    removed=set(initial['model_state'])-set(info['model_state'])
    calibration_path=folder/'value-calibration/report.json'
    calibration=read(calibration_path) if calibration_path.exists() else None
    allowed_added={'exam_quantile_head.weight','exam_quantile_head.bias'}
    if added:
        check(added==allowed_added and info['model_config'].get('quantiles')==32,
              'Unrecognized model parameter additions')
        check(bool(calibration and calibration.get('status')=='passed' and calibration.get('actor_unchanged')),
              'New value distribution lacks a passed critic-only calibration report')
    check(not removed,'Initial model parameters were removed')
    changed = sum(not torch.equal(value,initial['model_state'][key]) for key,value in info['model_state'].items()
                  if key in initial['model_state'])
    check(changed>0,'No model tensors changed from the search-run initial weights')
    return {'status':'issues' if problems else ('pending' if inherited_completion else 'passed'),'run':folder.name,
        'reason':'Inherited source batch; awaiting first formal KL/value batch' if inherited_completion else None,
        'checked_at':datetime.now(timezone.utc).isoformat(),'batch':info['batches'],'decisions':info['decisions'],
        'problems':problems,'changed_parameter_tensors_vs_initial':changed,
        'added_parameter_tensors':sorted(added),
        'formal_batch_from_current_revision':last.get('source_sha256')==info['rl_source_sha256'],
        'value_calibration_status':calibration.get('status') if calibration else None,
        'source_sha256':info['rl_source_sha256'],'original_deadline':info['training_config']['absolute_deadline'],
        'joint_games':last.get('joint_episode_count'),'fork_games':last.get('fork_episode_count'),
        'fork_coverage':last.get('fork_coverage',{}).get('coverage'),
        'search_records':last.get('search_records'),'ppo_records':last.get('ppo_records'),
        'actor_search_records':last.get('search_records'),
        'auxiliary_search_roots':last.get('auxiliary_search_roots',0),
        'auxiliary_search_records':last.get('auxiliary_search_records',0),
        'auxiliary_weighted_labels':(last.get('auxiliary_search') or {}).get('weighted_roots',0),
        'auxiliary_search':last.get('auxiliary_search'),
        'search_counter_scope':'main-router budget counts; learner-global PPO and CE counts',
        'configured_objective':objective,'committed_objective':last.get('construction_objective','mean'),
        'search_activity':'roots_attempted' if counts.get('attempted_roots',0)>0 else 'no_roots_in_this_batch',
        'committed_best4':best4,
        'search_counts':counts,'collection_seconds':last.get('collection_seconds'),
        'update_seconds':last.get('update_seconds'),'loss':last.get('loss'),
        'search_loss':last.get('search_loss'),'kl':last.get('kl'),
        'post_update_kl':last.get('post_update_kl',{}).get('mean_kl'),
        'update_coverage':last.get('update_coverage',{}).get('accepted_fraction'),
        'critic_update_coverage':(last.get('critic_update_coverage') or {}).get('accepted_fraction'),
        'critic_completion_steps':(last.get('critic_completion') or {}).get('optimizer_steps'),
        'signed_credit':last.get('signed_credit'),'search_learning':last.get('search_learning'),
        'partial_actor_update':last.get('update_coverage',{}).get('accepted_fraction',0)<1,
        'optimizer_steps':last.get('optimizer_steps'),'learning_rates':last.get('learning_rates'),
        'limitations':'Checkpoint and aggregated log checks; does not prove search is stronger or inspect every in-memory loss record.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path)
    parser.add_argument('--save',action='store_true')
    args=parser.parse_args()
    folder=args.run or Path(read(ROOT/'rl/generalist/active.json')['output'])
    result=audit(folder)
    if args.save:
        target=HERE/'watch-reports'/folder.name
        target.mkdir(parents=True,exist_ok=True)
        (target/('checkpoint-audit-'+str(result.get('batch','pending'))+'.json')).write_text(
            json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
