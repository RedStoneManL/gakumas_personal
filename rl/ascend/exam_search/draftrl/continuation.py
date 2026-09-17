"""Versioned continuation into a new directory after a completed source run."""
import copy
import ctypes
import json
import os
import shutil
from datetime import datetime,timedelta,timezone
from pathlib import Path
import torch
from .checkpoint import digest,json_write,load,source_version
from .recovery import restore_random
from .search_budgets import validate_timeout_change


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def process_alive(pid):
    if not pid:return False
    if os.name!='nt':
        # POSIX: a reaped pid has no /proc entry; an unreaped zombie (this container
        # has no init reaper) has state Z and is just as exited.
        try:
            stat=Path('/proc/%d/stat'%int(pid)).read_text(encoding='utf-8',errors='replace')
        except FileNotFoundError:
            return False
        except OSError:
            try:os.kill(int(pid),0)
            except ProcessLookupError:return False
            except PermissionError:return True
            return True
        return stat.rsplit(')',1)[-1].split()[0] not in ('Z','X')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x1000,False,int(pid))
    if not handle:
        if ctypes.get_last_error()==5:raise PermissionError('Cannot establish source trainer exit')
        return False
    try:
        code=ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise OSError('Cannot read trainer exit code')
        return code.value==259
    finally:kernel.CloseHandle(handle)


def stage(source,output,setup,config,arena_hash):
    source,output,setup=Path(source).resolve(),Path(output).resolve(),Path(setup).resolve()
    if output.exists():raise FileExistsError('Continuation output must be a new directory')
    required=('latest.pt','best.pt','initial.pt','manifest.json','progress.json',
              'validation-initial.json','validation-history.jsonl','metrics.jsonl')
    if any(not (source/name).is_file() for name in required):
        raise ValueError('Source run is missing continuation evidence')
    progress=read(source/'progress.json')
    migration=read(source/'migration-ready.json') if (source/'migration-ready.json').exists() else None
    paused=progress.get('status')=='paused' and migration is not None
    if (progress.get('status')!='complete' and not paused) or process_alive(progress.get('trainer_pid')):
        raise ValueError('Source trainer must finish its complete checkpoint and exit before continuation')
    checkpoint_hash=digest(source/'latest.pt')
    if paused and migration.get('checkpoint_sha256')!=checkpoint_hash:
        raise ValueError('Paused source checkpoint differs from verified migration boundary')
    info=torch.load(source/'latest.pt',map_location='cpu',weights_only=True)
    if info['arena_sha256']!=arena_hash:raise ValueError('Arena changed; not an equivalent continuation')
    if any(digest(setup/n)!=h for n,h in info['setup_sha256'].items()):
        raise ValueError('Original prepared scenario files differ from checkpoint')
    from .learning_settings import SIGNED, SEARCH
    already_signed = (config.get('signed_exam_credit') == SIGNED
                      and info['training_config'].get('signed_exam_credit') == SIGNED
                      and config.get('search', {}).get('learning_target') == SEARCH
                      and info['training_config'].get('search', {}).get('learning_target') == SEARCH)
    if already_signed:
        # Same audited learning settings on both sides: no feature migration to
        # validate. The permitted-key diff below audits the rest, except the keys the
        # critic-completion branch adds to `permitted`; pin those here explicitly.
        for key in ('target_kl','critic_completion','signed_exam_credit'):
            if config.get(key)!=info['training_config'].get(key):
                raise ValueError('Same-feature continuation may not change %s'%key)
    elif config.get('signed_exam_credit'):
        from .learning_settings import validate_config as validate_signed
        validate_signed(info['training_config'], config)
    elif config.get('critic_completion'):
        from .kl_value_migration import validate_config as validate_kl_value
        validate_kl_value(info['training_config'], config)
    elif config.get('value_calibration'):
        from .soft_value_migration import validate_config as validate_soft_value
        validate_soft_value(info['training_config'],config)
    else:
        validate_timeout_change(info['training_config'].get('search'), config.get('search'))
    if not config.get('value_calibration') and config.get('exploration_schedule', {}).get('basis') == 'meaningful_decisions':
        from .ultra_migration import validate_config
        validate_config(info['training_config'], config, decisions=info['decisions'],
                        snapshot=info['run_progress']['active_exploration'])
    permitted={'name','max_minutes','absolute_deadline','sample_efficiency','update_duty_cycle',
               'evaluation_interval_minutes','final_seed_base','resource_mode','practice',
               'batch_decisions','exploration','exploration_schedule','search','value_calibration'}
    if config.get('critic_completion'):
        permitted.update({'target_kl', 'critic_completion'})
    if config.get('signed_exam_credit'):
        permitted.add('signed_exam_credit')
    # Authorized 64 -> 512 gradient accumulation migration. Keep the physical
    # GPU microbatch and every other optimizer/scenario field audited below.
    old_block = info['training_config'].get('effective_minibatch',64)
    new_block = config.get('effective_minibatch',64)
    if new_block != old_block:
        if type(new_block) is not int or (old_block,new_block) != (64,512):
            raise ValueError('Unaudited effective gradient batch transition')
        permitted.add('effective_minibatch')
    # An explicit validated schedule is required for this version's authorized
    # LR migration. Adam moments remain intact; the runner reapplies group LRs.
    if config.get('learning_rate_schedule') is not None:
        from .learning_rates import PHASE_KEYS, validate_schedule
        validate_schedule(config)
        permitted.update(PHASE_KEYS.values())
        permitted.add('learning_rate_schedule')
    old={k:v for k,v in info['training_config'].items() if k not in permitted}
    new={k:v for k,v in config.items() if k not in permitted}
    if old!=new:raise ValueError('Continuation changed unaudited model/optimizer/scenario configuration')
    if (info['batches'],info['decisions'])!=(progress['batches'],progress['decisions']):
        raise ValueError('Progress is not at the final saved checkpoint')
    metric_lines=(source/'metrics.jsonl').read_text(encoding='utf-8').splitlines()
    if metric_lines:
        latest_metric=json.loads(metric_lines[-1])
        if (latest_metric['batch'],latest_metric['decisions'])!=(info['batches'],info['decisions']):
            raise ValueError('Metrics and saved checkpoint disagree')
    began=datetime.fromisoformat(progress['started_at'])
    deadline=began+timedelta(minutes=config['max_minutes'])
    if config.get('absolute_deadline'):
        deadline=min(deadline,datetime.fromisoformat(config['absolute_deadline']))
    if deadline<=datetime.now(timezone.utc):raise ValueError('Requested total training window has already ended')
    files=[p for p in source.iterdir() if p.is_file()]
    exclusions={'result.json','monitor.json','monitor-history.jsonl','training-window.json',
                'recovery.json','stop-after-batch.json','continuation.json','migration-ready.json',
                'decision-exploration-continuation.json','ultra-continuation.json','ultra-scale-continuation.json',
                'soft-value-continuation.json','kl-value-continuation.json','signed-credit-continuation.json'}
    if paused:
        unfinished=migration.get('source_progress',{}).get('evaluation_label')
        if unfinished:exclusions.update({unfinished+'.json',unfinished+'-episodes.jsonl'})
    files=[p for p in files if p.name not in exclusions and not p.name.endswith('.tmp')]
    if shutil.disk_usage(output.parent).free < sum(p.stat().st_size for p in files)+512*2**20:
        raise OSError('Insufficient space to preserve source history in a separate continuation')
    output.mkdir(parents=True)
    json_write(output/'continuation-staging.json',{'source':str(source),'complete':False})
    for p in files:shutil.copy2(p,output/p.name)
    calibration_provenance=None
    if config.get('critic_completion'):
        calibration = source/'value-calibration'
        if (calibration/'report.json').is_file():
            if read(calibration/'report.json').get('status') != 'passed':
                raise ValueError('Missing passed distribution calibration provenance')
            shutil.copytree(calibration, output/'value-calibration')
            calibration_provenance={'status':'copied','path':str(calibration)}
        elif already_signed and info['training_config'].get('critic_completion')==config.get('critic_completion'):
            # Same-feature continuation of a run that itself began from a portable checkpoint
            # snapshot (deploy/checkpoints/provenance.json: quantile head and Adam imported,
            # source logs deliberately not copied): the calibration evidence stayed with the
            # original run. Nothing in training reads this directory; the runner still refuses
            # to continue unless the model carries exam_quantile_head.
            calibration_provenance={'status':'absent_in_source','reason':'portable checkpoint start',
                'source_transfer':read(source/'manifest.json').get('transfer') if (source/'manifest.json').is_file() else None}
        else:
            raise ValueError('Missing passed distribution calibration provenance')
    # An explicit resource-only continuation may request a new preset. Do not
    # let the copied source request silently override the target configuration.
    if config.get('resource_mode') != info['training_config'].get('resource_mode'):
        from uuid import uuid4
        from .resource_modes import SCHEMA, validate_request
        request=validate_request({'schema':SCHEMA,'mode':config['resource_mode'],
            'request_id':str(uuid4()),'requested_at':datetime.now(timezone.utc).isoformat(),
            'reason':'User requested resource preset for versioned continuation'})
        json_write(output/'resource-mode.json',request)
    if digest(source/'latest.pt')!=checkpoint_hash or digest(output/'latest.pt')!=checkpoint_hash:
        raise ValueError('Source checkpoint changed while staging; do not launch staged output')
    baseline=read(output/'validation-initial.json')
    history=[json.loads(l) for l in (output/'validation-history.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    if any(r['batch']>info['batches'] for r in history):raise ValueError('Validation history exceeds saved checkpoint')
    # Preserve any interrupted future rollout only in source evidence; never train
    # or display it as committed continuation data.
    discarded=[];retained=[];training_log=output/'train-episodes.jsonl'
    if paused and training_log.exists():
        bank_limit=1_500_000_000+(info.get('sample_bank') or {}).get('replay_counter',0)
        for line in training_log.read_bytes().splitlines(keepends=True):
            try:
                row=json.loads(line)
                source_kind=row.get('sampling_source')
                limit=(bank_limit if source_kind=='bank_exam' else info.get('fork_next_seed',1_600_000_000)
                       if source_kind=='fork_exam' else info['next_episode_index'])
                (retained if row['seed']<limit else discarded).append(line)
            except (ValueError,KeyError):discarded.append(line)
        if discarded:
            (output/'continuation-uncommitted-tail.jsonl').write_bytes(b''.join(discarded))
            training_log.write_bytes(b''.join(retained))
    audit={'source_run':str(source),'source_checkpoint_sha256':checkpoint_hash,'source_code_sha256':info['rl_source_sha256'],
           'code_sha256':source_version(),'checkpoint_batch':info['batches'],'checkpoint_decisions':info['decisions'],
           'optimizer_restored':True,'rng_restored':True,'old_weights_preserved':True,
           'source_history_copied':True,'target_config':config,
           'paused_boundary':paused,'uncommitted_tail_rows_archived':len(discarded),
           'calibration_provenance':calibration_provenance,
           'configuration_changes':{k:{'old':info['training_config'].get(k),'new':config.get(k)}
                                    for k in permitted if info['training_config'].get(k)!=config.get(k)}}
    old_limit = info['training_config'].get('practice',{}).get('duplicates',{}).get('max_same_name')
    new_limit = config.get('practice',{}).get('duplicates',{}).get('max_same_name')
    old_overrides = info['training_config'].get('practice',{}).get('duplicates',{}).get('max_same_name_overrides',{})
    new_overrides = config.get('practice',{}).get('duplicates',{}).get('max_same_name_overrides',{})
    cap_changed = (old_limit,old_overrides) != (new_limit,new_overrides)
    # practice.duplicates.keep_benchmark_history: change the copy cap without archiving
    # the validation lineage or measuring a new baseline. The index from this point on
    # is measured under the new cap against the ORIGINAL baseline, so part of any rise
    # is the cap itself; the audit and construction-benchmark.json say so.
    keep_history = bool(config.get('practice',{}).get('duplicates',{}).get('keep_benchmark_history'))
    reset_joint_reference = cap_changed and not keep_history
    if cap_changed and keep_history:
        audit['construction_benchmark_change'] = {
            'old_max_same_name':old_limit,'new_max_same_name':new_limit,
            'old_overrides':old_overrides,'new_overrides':new_overrides,
            'history_kept':True,'change_batch':info['batches'],
            'reference':'original baseline retained; validation index after this batch includes the cap change',
            'fixed_play_reference_unchanged':True}
        json_write(output/'construction-benchmark.json',{'max_same_name':new_limit,
            'max_same_name_overrides':new_overrides,'start_batch':info['batches'],'baseline_index':None,
            'history_kept':True,'reference':'validation lineage kept across the copy-cap change',
            'fixed_play_unchanged':True})
    if reset_joint_reference:
        # Only files already copied into this NEW continuation are relocated.
        # Keep the original run intact and the fixed-play evaluation unchanged.
        archive = output/'previous-construction-benchmark'
        archive.mkdir()
        for path in output.glob('validation-*'):
            if path.is_file():
                path.rename(archive/path.name)
        if (output/'construction-benchmark.json').exists():
            (output/'construction-benchmark.json').rename(archive/'construction-benchmark.json')
        for path in output.glob('best*.pt'):
            shutil.copy2(path, archive/path.name)
        shutil.copy2(output/'latest.pt', output/'construction-boundary.pt')
        (output/'validation-history.jsonl').write_text('',encoding='utf8')
        audit['construction_benchmark_change'] = {
            'old_max_same_name':old_limit,'new_max_same_name':new_limit,
            'old_overrides':old_overrides,'new_overrides':new_overrides,
            'reference':'same resumed policy, now under the new construction cap',
            'fixed_play_reference_unchanged':True,'archive':str(archive)}
    json_write(output/'training-window.json',{'schema':'arena-training-window/1','absolute_deadline':deadline.isoformat(),
        'max_minutes':config['max_minutes'],'requested_at':datetime.now(timezone.utc).isoformat(),
        'reason':'User-selected total continuation horizon, measured from the original run start.'})
    progress.update(status='prepared',run_dir=str(output))
    json_write(output/'progress.json',progress)
    json_write(output/'continuation-staging.json',{'source':str(source),'complete':True,'checkpoint_sha256':checkpoint_hash})
    return info,{'progress':progress,'baseline':baseline,'history':history,'audit':audit,'setup':str(setup),
                'reset_joint_reference':reset_joint_reference}


def prepare(source,output,setup,config,arena_hash,device):
    info,context=stage(source,output,setup,config,arena_hash)
    model,loaded=load(Path(output)/'latest.pt',device)
    if not all(torch.isfinite(v).all() for v in model.state_dict().values()):raise ValueError('Nonfinite continuation weights')
    return model,loaded,context


def commit_recovery(output,info,context):
    output=Path(output);audit=copy.deepcopy(context['audit'])
    audit['resumed_at']=datetime.now(timezone.utc).isoformat()
    manifest=read(output/'manifest.json')
    manifest.setdefault('continuations',[]).append(audit)
    manifest.update(config=audit['target_config'],rl_source_sha256=source_version(),
        active_code_root=str(Path(context['setup']).parent),training_arena_path=str(Path(context['setup']).parent/'runtime/arena'),
        effective_training_window=read(output/'training-window.json'))
    json_write(output/'manifest.json',manifest);json_write(output/'continuation.json',audit)
    return audit
