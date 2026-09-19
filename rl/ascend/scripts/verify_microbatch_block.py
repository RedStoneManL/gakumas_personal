"""Bounded PPO accumulation/input-pipeline gates using real public fixtures.

Synthetic rewards/labels are diagnostics only. Never creates training data or
checkpoints. Restores the same checkpoint and named Adam groups for both runs.
This verifies a local block, not distributed or end-to-end throughput.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--device', default='npu:7')
    p.add_argument('--memory-fraction', type=float, default=.6)
    p.add_argument('--mode', choices=['microbatch','tower-inputs','prefetch'], default='microbatch')
    args = p.parse_args()
    if args.report.exists():
        p.error('Use a new report path to preserve evidence')
    exam = args.root/'exam-search'
    if not exam.exists():
        exam = args.root/'exam_search'
    sys.path[:0] = [str(exam), str(exam/'tests'), str(exam/'runtime/shared'),
                   str(exam/'runtime/arena'), str(args.root/'training')]
    os.environ['GAKUMAS_LEXICAL_GRU_BACKEND'] = 'cpu-buffered'
    os.environ['GAKUMAS_PARALLEL_LEXICAL'] = '1'
    import torch
    import torch_npu  # noqa: F401
    from draftrl.model import DraftPolicy
    from draftrl.fast_collate import collate, prepare_encoded
    from draftrl.distribution import distributions
    from draftrl.ppo import update
    from test_relational_runtime import RelationalRuntimeTests as Fixtures

    torch.npu.set_device(args.device)
    if not 0 < args.memory_fraction <= .6:
        p.error('Diagnostic memory fraction must be in (0, .6]')
    torch.npu.set_per_process_memory_fraction(args.memory_fraction, args.device)
    started = time.monotonic()
    runs = [(64,'0'),(128,'0')] if args.mode=='microbatch' else [(128,'0'),(128,'1')]
    report = dict(schema='arena-ppo-microbatch-verification/1', device=args.device,mode=args.mode,
                  checkpoint=str(args.checkpoint), checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                  scope=('Two local PPO blocks' if args.mode=='prefetch' else 'One local PPO block') + ', real public inputs with diagnostic rewards/search labels; no production trajectories',
                  microbatches=[x[0] for x in runs],memory_fraction=args.memory_fraction,results=[],
                  limits=dict(gradient_max=2e-5, gradient_relative_l2=1e-4, adam_parameter_max=5e-6),
                  source_files={name: hashlib.sha256((exam/'draftrl'/name).read_bytes()).hexdigest()
                                for name in ['ppo.py','model.py','relational_model.py','buffered_gru.py','parallel_lexical.py','fast_collate.py',
                                             *([name for name in ('tower_inputs.py','batch_pipeline.py','critic_completion.py') if (exam/'draftrl'/name).exists()])]})
    ready = False
    try:
        info = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
        Fixtures.setUpClass(); ready = True
        torch.set_num_threads(4)
        examples = [(profile,prepare_encoded(copy.deepcopy(e)))
                    for profile in sorted(Fixtures.examples) for e in Fixtures.examples[profile]]
        row_count = 256 if args.mode == 'prefetch' else 128
        inputs = [examples[i % len(examples)] for i in range(row_count)]
        settings = dict(temperature=1.2, uniform_mix=.1, entropy_coefficient=.01)

        if args.mode == 'prefetch':
            from draftrl.batch_pipeline import prepare_cpu, transfer
            direct = collate([e for _,e in inputs[:128]], args.device)
            staged = transfer(prepare_cpu([e for _,e in inputs[:128]], npu=True), args.device)
            checked = [0]

            def equal(a, b):
                if isinstance(a, torch.Tensor):
                    assert a.device == b.device and a.dtype == b.dtype
                    torch.testing.assert_close(a, b, atol=0, rtol=0)
                    checked[0] += 1
                    ap, bp = getattr(a, '_arena_segment_plan', None), getattr(b, '_arena_segment_plan', None)
                    if ap is not None or bp is not None:
                        equal(ap, bp)
                elif isinstance(a, dict):
                    assert a.keys() == b.keys()
                    for key in a: equal(a[key], b[key])
                elif isinstance(a, (list, tuple)):
                    assert type(a) == type(b) and len(a) == len(b)
                    for x, y in zip(a, b): equal(x, y)
                else:
                    assert a == b
            equal(direct, staged)
            report['input_tensors_bit_identical'] = checked[0]
            del direct, staged

        def make_model():
            m = DraftPolicy(**info['model_config'])
            m.load_state_dict(info['model_state'], strict=True)
            return m.to(args.device)

        m = make_model()
        # Warm both lexical backward and accelerator kernels without an update.
        warm = collate([e for _,e in examples],args.device)
        logits,values,atoms = m.learning_forward(warm)
        (logits[warm['mask']].mean()+values.square().mean()+atoms.square().mean()).backward()
        with torch.no_grad():
            old, old_values = [], []
            for start in range(0, row_count, 128):
                part = inputs[start:start+128]
                b = collate([e for _,e in part],args.device)
                logits,values = m(b)
                actions = torch.tensor([(start+i)%len(e.submissions) for i,(_,e) in enumerate(part)],device=args.device)
                dist,_ = distributions(logits,b['mask'],[settings]*len(part))
                old.extend(dist.log_prob(actions).cpu().tolist())
                old_values.extend(values.cpu().tolist())
        del m,warm,logits,values,atoms,b,dist,actions
        torch.npu.empty_cache()
        rows = []
        for i,(profile,e) in enumerate(inputs):
            kind = 'search' if e.phase==0 and i%2==0 else 'ppo'
            row = dict(encoded=e,profile=profile,action=i%len(e.submissions),
                       old_logp=old[i] if kind=='ppo' else None,old_value=old_values[i],
                       **{'return': old_values[i]+(i%7-3)*.2},
                       loss_kind=kind,exploration=settings,policy_version='microbatch-gate:0')
            if kind=='search':
                count=len(e.submissions)
                row['search']=dict(actions=copy.deepcopy(e.submissions),target_policy=[1/count]*count,
                                   target_budget_eligible=True,root_action_coverage=1.)
            rows.append(row)
        report.update(profiles=sorted(Fixtures.examples),phases=sorted({e.phase for _,e in inputs}),
                      records=len(rows),search_records=sum(r['loss_kind']=='search' for r in rows))
        results=[]
        for micro,prepared_towers in runs:
            if args.mode == 'prefetch':
                os.environ['GAKUMAS_PREPARED_TOWERS']='1'
                os.environ['GAKUMAS_PPO_PREFETCH']=prepared_towers
            else:
                os.environ['GAKUMAS_PREPARED_TOWERS']=prepared_towers
                os.environ['GAKUMAS_PPO_PREFETCH']='0'
            model=make_model(); named=dict(model.named_parameters())
            groups=[]
            for saved,names in zip(info['optimizer_state']['param_groups'],info['optimizer_parameter_names'],strict=True):
                groups.append({**{k:v for k,v in saved.items() if k!='params'},'params':[named[n] for n in names]})
            optimizer=torch.optim.Adam(groups,foreach=False)
            optimizer.load_state_dict(copy.deepcopy(info['optimizer_state']))
            for group in optimizer.param_groups: group['foreach']=False
            cfg=dict(_policy_version='microbatch-gate:0',sample_efficiency={'advantage_mode':'mc','ppo_epochs_max':1},
                     search={'loss_coefficient':.1},practice={},epochs=1,effective_minibatch=128,
                     minibatch=micro,clip=.2,target_kl=.05,value_coefficient=.5,max_grad=.5,
                     value_calibration=info['training_config'].get('value_calibration',{}))
            random.seed(19613);torch.manual_seed(19613);torch.npu.manual_seed_all(19613)
            torch.npu.synchronize();torch.npu.reset_peak_memory_stats()
            tick=time.monotonic()
            metrics=update(model,optimizer,rows,cfg,args.device)
            torch.npu.synchronize();elapsed=time.monotonic()-tick
            grads={n:v.grad.detach().cpu() for n,v in named.items() if v.grad is not None}
            weights={n:v.detach().cpu() for n,v in named.items()}
            result=dict(microbatch=micro,prepared_towers=prepared_towers,seconds=elapsed,peak_allocated_bytes=torch.npu.max_memory_allocated(),
                        peak_reserved_bytes=torch.npu.max_memory_reserved(),optimizer_steps=metrics['optimizer_steps'],
                        loss=metrics['loss'],search_loss=metrics['search_loss'],
                        input_pipeline=metrics.get('input_pipeline'))
            if args.mode == 'prefetch':
                result.update(prepared_towers='1', prefetch=prepared_towers)
            results.append((result,grads,weights))
            report['results'].append(result)
            print(json.dumps(result),flush=True)
            del optimizer,model,named,groups
            torch.npu.empty_cache()
        (left,lg,lw),(right,rg,rw)=results
        assert lg.keys()==rg.keys(),'Gradient presence changed'
        a=torch.cat([v.flatten() for v in lg.values()]);b=torch.cat([rg[n].flatten() for n in lg])
        delta=b-a
        report.update(results=[left,right],gradient_tensors=len(lg),gradient_elements=a.numel(),
                      gradient_max=float(delta.abs().max()),gradient_relative_l2=float(delta.norm()/a.norm().clamp_min(1e-30)),
                      adam_parameter_max=max(float((lw[n]-rw[n]).abs().max()) for n in lw))
        assert torch.isfinite(a).all() and torch.isfinite(b).all()
        assert all(torch.isfinite(v).all() for v in rw.values())
        assert left['optimizer_steps']==right['optimizer_steps']==row_count//128
        for key,limit in report['limits'].items():
            assert report[key]<=limit,(key,report[key],limit)
        report['passed']=True
    except Exception as exc:
        report.update(passed=False,error=type(exc).__name__+': '+str(exc))
    finally:
        if ready: Fixtures.tearDownClass()
        report['elapsed_seconds']=time.monotonic()-started
        args.report.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
    return 0 if report.get('passed') else 1


if __name__=='__main__':
    raise SystemExit(main())
