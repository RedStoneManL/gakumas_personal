"""Safe background handoff to critic warm-up and soft-budget search."""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE/'runtime/shared'),str(HERE/'runtime/arena'),str(ROOT/'rl/generalist')]
from monitor import alive,read,write_status
from draftrl.source_identity import digest,source_version
from draftrl.soft_value_migration import validate_config


def equal(a,b):
    import torch
    if isinstance(a,torch.Tensor):return isinstance(b,torch.Tensor) and torch.equal(a,b)
    if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return type(a)==type(b) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b


def audit_boundary(previous,folder,config):
    import torch
    torch.set_num_threads(2)
    old=torch.load(previous/'latest.pt',map_location='cpu',weights_only=True)
    new=torch.load(folder/'value-boundary.pt',map_location='cpu',weights_only=True)
    validate_config(old['training_config'],config)
    for key in ('model_state','model_config','batches','decisions','next_episode_index','fork_next_seed',
                'search_seed_counter','arena_sha256','search_version','setup_sha256','python_rng','torch_rng','cuda_rng'):
        if not equal(old[key],new[key]):raise ValueError('Boundary changed '+key)
    if not equal(old['optimizer_state']['state'],new['optimizer_state']['state']):raise ValueError('Adam changed')
    strip=lambda state:[{k:v for k,v in g.items() if k!='lr'} for g in state['param_groups']]
    if not equal(strip(old['optimizer_state']),strip(new['optimizer_state'])):raise ValueError('Adam groups changed')
    if new['training_config']!=config or new['rl_source_sha256']!=source_version():raise ValueError('Wrong boundary revision')
    logs={}
    for name,length in old['committed_log_offsets'].items():
        if name=='monitor-history.jsonl':continue
        hashes=[]
        for path in (previous/name,folder/name):
            h=hashlib.sha256();remaining=length
            with path.open('rb') as f:
                while remaining:
                    block=f.read(min(remaining,1024*1024))
                    if not block:raise ValueError('Truncated history '+name)
                    h.update(block);remaining-=len(block)
            hashes.append(h.hexdigest())
        if hashes[0]!=hashes[1]:raise ValueError('History changed '+name)
        logs[name]={'bytes':length,'sha256':hashes[0]}
    result={'status':'passed','checkpoint_batch':old['batches'],'checkpoint_decisions':old['decisions'],
            'model_adam_rng_identical_before_calibration':True,'committed_log_prefixes':logs,
            'source_checkpoint_sha256':digest(previous/'latest.pt'),'code_sha256':source_version()}
    write_status(folder/'continuation-state-audit.json',result)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--wait-minutes',type=float,default=240);args=p.parse_args()
    previous=args.source.resolve();accept=read(HERE/'acceptance.json')
    if accept.get('status')!='passed' or accept['candidate_source_sha256']!=source_version():raise ValueError('Untested revision')
    if accept['supervisor_sha256']!=digest(Path(__file__)):raise ValueError('Supervisor changed')
    if digest(HERE/'training-config.json')!=accept['training_config_sha256']:raise ValueError('Settings changed')
    pilot=Path(accept['calibration_report'])
    if digest(pilot)!=accept['calibration_report_sha256'] or read(pilot).get('status')!='passed':raise ValueError('Calibration not validated')
    config=read(HERE/'training-config.json');pointer_path=ROOT/'rl/generalist/active.json';old=read(pointer_path)
    if previous.parent!=ROOT/'rl/generalist/runs' or Path(old['output']).resolve()!=previous:raise ValueError('Wrong active source')
    source_manifest=read(previous/'manifest.json');validate_config(source_manifest['config'],config)
    if source_manifest['rl_source_sha256']!=accept['source_code_sha256']:raise ValueError('Source changed')
    if config['absolute_deadline']!=old['expected_training_end']:raise ValueError('Deadline changed')
    stop=previous/'stop-after-batch.json';marker=previous/'soft-value-continuation.json'
    if stop.exists() or marker.exists():raise ValueError('Existing transition requires inspection')
    state={'status':'waiting','source_run':str(previous),'target_code':str(HERE),'supervisor_pid':os.getpid()}
    with marker.open('x',encoding='utf-8') as f:json.dump(state,f)
    with stop.open('x',encoding='utf-8') as f:json.dump({'supervisor_pid':os.getpid(),'transition':str(marker),
        'reason':'User requested soft search and critic calibration; finish current full batch.'},f)
    try:
        print(json.dumps(state),flush=True);start=time.monotonic()
        while True:
            if read(pointer_path).get('output')!=old['output']:raise RuntimeError('Active writer changed')
            progress=read(previous/'progress.json')
            if progress.get('status')=='complete' and alive(progress.get('trainer_pid')) is False:break
            if progress.get('status')=='failed' or time.monotonic()-start>args.wait_minutes*60:raise RuntimeError('Source did not finish safely')
            time.sleep(15)
        if datetime.fromisoformat(config['absolute_deadline'])<=datetime.now(timezone.utc):raise ValueError('Deadline expired')
        name='joint-mcts-soft-value-'+datetime.now().strftime('%Y%m%d-%H%M%S')
        folder=ROOT/'rl/generalist/runs'/name;job=ROOT/'rl/generalist/jobs'/name;job.mkdir()
        write_status(job/'previous-active.json',old);write_status(job/'config.json',config)
        command=[sys.executable,'-B','-X','utf8','-u',str(HERE/'train.py'),'--config',str(job/'config.json'),
                 '--continue-from',str(previous),'--output',str(folder)]
        with (job/'stdout.log').open('ab') as out,(job/'stderr.log').open('ab') as err:
            process=subprocess.Popen(command,cwd=ROOT,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        state.update(status='starting',target_run=str(folder),job=str(job),launcher_pid=process.pid);write_status(marker,state)
        deadline=time.monotonic()+300
        while True:
            progress=read(folder/'progress.json')
            if process.poll() is not None or progress.get('status')=='failed':raise RuntimeError('Candidate failed: '+str(job))
            if (folder/'value-boundary.pt').exists() and progress.get('status')=='running':break
            if time.monotonic()>deadline:raise RuntimeError('No sealed pre-calibration boundary')
            time.sleep(1)
        audit=audit_boundary(previous,folder,config)
        if read(pointer_path).get('output')!=old['output']:raise RuntimeError('Active pointer raced another writer')
        write_status(pointer_path,{**old,'output':str(folder),'code_root':str(HERE),'launcher_pid':process.pid,
            'stdout':str(job/'stdout.log'),'stderr':str(job/'stderr.log'),'config_path':str(job/'config.json'),
            'search':copy.deepcopy(config['search']),'value_calibration':config['value_calibration'],
            'migration_source_run':str(previous),'continued_at':datetime.now(timezone.utc).isoformat()})
        state.update(status='calibrating',boundary_audit=audit['status']);write_status(marker,state)
        with (job/'monitor.log').open('ab') as out,(job/'monitor-error.log').open('ab') as err:
            monitor=subprocess.Popen([sys.executable,'-B','-X','utf8','-u',str(ROOT/'rl/generalist/monitor.py')],
                cwd=ROOT,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        write_status(ROOT/'rl/generalist/monitor-process.json',{'pid':monitor.pid,'run':str(folder)})
        deadline=time.monotonic()+7200
        while True:
            progress=read(folder/'progress.json');report=read(folder/'value-calibration/report.json')
            if process.poll() is not None or progress.get('status')=='failed':raise RuntimeError('Critic warm-up failed: '+str(job))
            if report.get('status')=='passed' and (folder/'critic-calibrated.pt').exists():break
            if time.monotonic()>deadline:raise RuntimeError('Calibration timed out')
            time.sleep(15)
        state.update(status='continued',calibration_status='passed',actor_unchanged=report['actor_unchanged'],
            checkpoint_batch=progress['batches'],checkpoint_decisions=progress['decisions'])
        write_status(marker,state);print(json.dumps(state),flush=True)
    except BaseException as error:
        state.update(status='failed',error=f'{type(error).__name__}: {error}');write_status(marker,state);raise


if __name__=='__main__':main()
