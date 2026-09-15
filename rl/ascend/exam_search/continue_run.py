"""Switch exploration to committed decisions after the live batch safely finishes."""
import argparse
import copy
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE),str(HERE/'runtime/shared'),str(HERE/'runtime/arena'),str(ROOT/'rl/generalist')]
from monitor import alive, read, write_status
from draftrl.source_identity import digest, source_version
from draftrl.search_budgets import validate_timeout_change


def validate_config(source,candidate):
    from draftrl.ultra_migration import validate_config as validate_ultra_config
    validate_timeout_change(source.get('search'),candidate.get('search'))
    validate_ultra_config({k:v for k,v in source.items() if k!='search'},
                    {k:v for k,v in candidate.items() if k!='search'})


def audit_boundary(previous,folder,info,config):
    """Require actual model/Adam/RNG identity before publishing the new writer."""
    import torch
    torch.set_num_threads(2)
    source=torch.load(previous/'latest.pt',map_location='cpu',weights_only=True)
    from draftrl.ultra_migration import validate_config as validate_ultra_config
    validate_config(source['training_config'],config)
    exploration_change = {}
    if source['training_config'].get('exploration_schedule') != config.get('exploration_schedule'):
        exploration_change = validate_ultra_config(source['training_config'],config,
            decisions=source['decisions'],snapshot=source['run_progress']['active_exploration'])['exploration_change']
    def equal(a,b):
        if isinstance(a,torch.Tensor):return isinstance(b,torch.Tensor) and torch.equal(a,b)
        if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
        if isinstance(a,(list,tuple)):return type(a)==type(b) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
        return a==b
    for name in ('model_state','model_config','python_rng','torch_rng','cuda_rng',
                 'batches','decisions','next_episode_index','fork_next_seed','search_seed_counter',
                 'arena_sha256','search_version','setup_sha256'):
        if not equal(source[name],info[name]):raise ValueError('Continuation changed '+name)
    if not equal(source['optimizer_state']['state'],info['optimizer_state']['state']):
        raise ValueError('Continuation changed Adam moments or steps')
    old_groups=source['optimizer_state']['param_groups'];new_groups=info['optimizer_state']['param_groups']
    without_lr=lambda groups:[{k:v for k,v in g.items() if k!='lr'} for g in groups]
    if not equal(without_lr(old_groups),without_lr(new_groups)):
        raise ValueError('Continuation changed optimizer groups')
    if info['training_config']!=config:raise ValueError('Continuation config changed')
    def prefix_hash(path,length):
        h=hashlib.sha256()
        with path.open('rb') as stream:
            while length:
                block=stream.read(min(length,1024*1024))
                if not block:raise ValueError('Continuation truncated '+str(path))
                h.update(block);length-=len(block)
        return h.hexdigest()
    logs={};omitted_monitoring={}
    for name,length in source['committed_log_offsets'].items():
        if name=='monitor-history.jsonl':
            # continuation.stage deliberately starts per-run process telemetry
            # afresh. All learning/evaluation histories still require equality.
            omitted_monitoring[name]={'bytes':length,'preserved_in_source':str(previous/name),
                'reason':'Per-run monitoring history is excluded by continuation.stage'}
            continue
        before=prefix_hash(previous/name,length);after=prefix_hash(folder/name,length)
        if before!=after:raise ValueError('Continuation changed committed history '+name)
        logs[name]={'bytes':length,'sha256':before}
    result={'status':'passed','checked_at':datetime.now(timezone.utc).isoformat(),
        'source_checkpoint_sha256':digest(previous/'latest.pt'),'target_source_sha256':info['rl_source_sha256'],
        'batch':info['batches'],'decisions':info['decisions'],
        'model_adam_rng_identical':True,'committed_log_prefixes':logs,
        'omitted_monitoring_history':omitted_monitoring,
        'old_learning_rates':[g['lr'] for g in old_groups],'new_learning_rates':[g['lr'] for g in new_groups],
        'original_deadline':config['absolute_deadline'],'new_objective':'best_of_k','replicas':4,
        'search_budget_change':validate_timeout_change(source['training_config'].get('search'),config.get('search')),
        'exploration_change':exploration_change,
        'resource_mode_change':{'old':source['training_config'].get('resource_mode'),'new':config.get('resource_mode')},
        'change':'Ultra parallelism with lazy Arena collector bootstrap; preserve the pending meaningful-decision schedule, model and objective'}
    write_status(folder/'continuation-state-audit.json',result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--wait-minutes',type=float,default=0)
    args = parser.parse_args()
    acceptance = read(HERE/'ultra-acceptance.json')
    if acceptance.get('status')!='passed' or source_version() != acceptance.get('candidate_source_sha256'):
        raise RuntimeError('Loaded candidate revision differs from tested acceptance')
    if digest(HERE/'continue_run.py') != acceptance.get('supervisor_sha256'):
        raise RuntimeError('Continuation supervisor differs from tested acceptance')
    for name in ('exploration-request.json','training-config.json'):
        if digest(HERE/name) != acceptance.get('sealed_files',{}).get(name):
            raise RuntimeError('Exploration request or source configuration changed after tests')
    previous = args.source.resolve()
    if previous.parent != ROOT/'rl/generalist/runs':
        raise ValueError('Source must be a workspace generalist run')
    pointer_path = ROOT/'rl/generalist/active.json'
    old = read(pointer_path)
    if Path(old['output']).resolve() != previous:
        raise ValueError('Active run differs from explicitly selected source')
    request=read(HERE/'exploration-request.json')
    if previous != Path(request['source_run']).resolve():
        raise ValueError('Exploration request names a different source run')
    source_config=read(HERE/'training-config.json')
    if read(previous/'manifest.json')['config'] != source_config:
        raise ValueError('Live source configuration differs from the sealed request')
    if read(previous/'manifest.json')['rl_source_sha256'] != acceptance['source_code_sha256']:
        raise ValueError('Live source code differs from the reviewed source')
    stop_path=previous/'stop-after-batch.json'
    adopting=False
    if stop_path.exists():
        owner=read(stop_path)
        superseded=read(previous/'ultra-continuation.json')
        if (superseded.get('status')!='superseded'
                or owner.get('supervisor_pid')!=superseded.get('supervisor_pid')
                or alive(owner.get('supervisor_pid')) is not False):
            raise RuntimeError('Another live boundary stop is pending; inspect ownership')
        adopting=True
    transition = previous/'ultra-scale-continuation.json'
    with transition.open('x',encoding='utf8') as stream:
        json.dump({'status':'waiting','target_code':str(HERE),'source_code_sha256':source_version(),
                   'supervisor_pid':os.getpid(),
                   'request':request,
                   'deadline':old['expected_training_end'],'requested_at':datetime.now(timezone.utc).isoformat()},stream)
    stop_value={'reason':'User requested Ultra parallelism and meaningful-decision exploration; preserve the current full batch',
                'supervisor_pid':os.getpid(),'transition':str(transition),'adopted_pending_stop':adopting}
    if adopting:write_status(stop_path,stop_value)
    else:
        with stop_path.open('x',encoding='utf8') as stream:json.dump(stop_value,stream)
    print(json.dumps({'status':'waiting','supervisor_pid':os.getpid(),'source':str(previous),
                      'transition':str(transition),'decay_decisions':request['decay_decisions']},ensure_ascii=False),flush=True)
    start = time.monotonic()
    while True:
        if read(pointer_path).get('output') != old['output']:
            raise RuntimeError('Active run changed; do not start another trainer')
        state = read(previous/'progress.json')
        if state.get('status') == 'complete' and alive(state.get('trainer_pid')) is False:
            break
        if state.get('status') == 'failed' or time.monotonic()-start > args.wait_minutes*60:
            raise RuntimeError('Source has not completed safely within the waiting window')
        time.sleep(15)
    if state.get('batches',0) < 1:
        raise ValueError('At least one committed formal search update is required')
    manifest = read(previous/'manifest.json')
    import torch
    from draftrl.ultra_migration import make_config
    torch.set_num_threads(2)
    boundary=torch.load(previous/'latest.pt',map_location='cpu',weights_only=True)
    if boundary['training_config'] != source_config or manifest['config'] != source_config:
        raise ValueError('Source training configuration changed while waiting')
    config=make_config(source_config,boundary['decisions'],
        boundary['run_progress']['active_exploration'],request['decay_decisions'])
    validate_config(manifest['config'],config)
    if config['absolute_deadline'] != old['expected_training_end']:
        raise ValueError('Original absolute deadline was not retained')
    if datetime.fromisoformat(config['absolute_deadline']) <= datetime.now(timezone.utc):
        raise ValueError('Original training window has expired')
    for name,fingerprint in manifest['setup_sha256'].items():
        if digest(HERE/'setup'/name) != fingerprint:
            raise ValueError('Candidate scenario changed: '+name)
    name = 'joint-mcts-ultra-scale-'+datetime.now().strftime('%Y%m%d-%H%M%S')
    folder = ROOT/'rl/generalist/runs'/name
    job = ROOT/'rl/generalist/jobs'/name
    job.mkdir()
    write_status(job/'previous-active.json',old)
    write_status(job/'config.json',config)
    command = [sys.executable,'-B','-X','utf8','-u',str(HERE/'train.py'),
        '--config',str(job/'config.json'),'--continue-from',str(previous),'--output',str(folder)]
    with (job/'stdout.log').open('ab') as stdout,(job/'stderr.log').open('ab') as stderr:
        process = subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    write_status(transition,{'status':'starting','job':str(job),'target_run':str(folder),
        'launcher_pid':process.pid,'supervisor_pid':os.getpid(),
        'exploration_schedule':config['exploration_schedule'],'deadline':old['expected_training_end']})
    limit = time.monotonic()+180
    while True:
        state = read(folder/'progress.json')
        if state.get('status') == 'failed' or process.poll() is not None:
            raise RuntimeError('Candidate trainer failed; inspect '+str(job))
        if (folder/'latest.pt').exists() and state.get('status') == 'running':
            import torch
            info = torch.load(folder/'latest.pt',map_location='cpu',weights_only=True)
            if (info['rl_source_sha256']==source_version() and info.get('committed_best')
                    and info['training_config']==config and alive(state.get('trainer_pid')) is True):
                break
        if time.monotonic() > limit:
            raise RuntimeError('New revision has not sealed a recoverable checkpoint; inspect '+str(job))
        time.sleep(1)
    if read(pointer_path).get('output') != old['output']:
        raise RuntimeError('Active pointer changed during startup; inspect new trainer '+str(job))
    audit_boundary(previous,folder,info,config)
    pointer = {**old,'launcher_pid':process.pid,'output':str(folder),'code_root':str(HERE),
        'workers':48,'resource_mode':'ultra',
        'config_path':str(job/'config.json'),'exploration_schedule':config['exploration_schedule'],
        'search':copy.deepcopy(config['search']),
        'construction_replicas':4,'construction_objective':'best_of_k','primary_checkpoint':'best4.pt',
        'stdout':str(job/'stdout.log'),'stderr':str(job/'stderr.log'),
        'continued_at':datetime.now(timezone.utc).isoformat(),'migration_source_run':str(previous)}
    write_status(pointer_path,pointer)
    with (job/'monitor.log').open('ab') as stdout,(job/'monitor-error.log').open('ab') as stderr:
        monitor = subprocess.Popen([sys.executable,'-B','-X','utf8','-u',str(ROOT/'rl/generalist/monitor.py')],
            cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    write_status(ROOT/'rl/generalist/monitor-process.json',{'pid':monitor.pid,'run':str(folder)})
    write_status(transition,{'status':'continued','target_run':str(folder),'target_code':str(HERE),
        'checkpoint_batch':info['batches'],'checkpoint_decisions':info['decisions'],
        'exploration_schedule':config['exploration_schedule'],
        'source_code_sha256':info['rl_source_sha256'],'deadline':pointer['expected_training_end']})
    print(json.dumps(pointer,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        request=read(HERE/'exploration-request.json')
        source=Path(request.get('source_run',''))
        transition=source/'ultra-scale-continuation.json'
        marker=read(transition)
        if marker.get('supervisor_pid') == os.getpid():
            write_status(transition,{**marker,'status':'failed',
                'error':f'{type(error).__name__}: {error}',
                'failed_at':datetime.now(timezone.utc).isoformat()})
        raise
