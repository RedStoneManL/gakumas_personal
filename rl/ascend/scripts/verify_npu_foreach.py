"""Small optimizer-only NPU check; no games, model forward or saved weights.

Uses production Adam shapes/moments/step counts with deterministic diagnostic
parameters and gradients. Checks missing gradients, changed learning rates and
checkpoint reload; timings are local optimizer timings, not pipeline throughput.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--device', default='npu:7')
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Preserve existing evidence; choose a new report')
    import torch
    import torch_npu
    torch.set_num_threads(2)
    torch.npu.set_device(args.device)
    torch.npu.set_per_process_memory_fraction(.035, args.device)
    started = time.monotonic()
    report = dict(schema='arena-npu-foreach-optimizer-check/1', passed=False,
                  scope=__doc__, torch=str(torch.__version__), torch_npu=str(torch_npu.__version__),
                  checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), results=[])
    try:
        saved = torch.load(args.checkpoint, map_location='cpu', weights_only=True)['optimizer_state']
        identifiers = [i for g in saved['param_groups'] for i in g['params']]
        assert len(set(identifiers)) == len(identifiers)
        assert all('exp_avg' in saved['state'][i] for i in identifiers)
        generator = torch.Generator().manual_seed(1962026)
        initial = {i: torch.randn(saved['state'][i]['exp_avg'].shape, generator=generator)*.02
                   for i in identifiers}
        gradients = {i: torch.randn(p.shape, generator=generator)*.001 for i, p in initial.items()}
        report.update(parameters=len(initial), elements=sum(p.numel() for p in initial.values()),
                      groups=len(saved['param_groups']))
        versions = []
        for foreach in (False, True):
            parameters = {i: torch.nn.Parameter(p.to(args.device)) for i, p in initial.items()}
            groups = [{**{k: v for k, v in g.items() if k != 'params'},
                       'params': [parameters[i] for i in g['params']], 'foreach': foreach,
                       'fused': False, 'capturable': False} for g in saved['param_groups']]
            optimizer = torch.optim.Adam(groups)
            state = copy.deepcopy(saved)
            for g in state['param_groups']:
                g.update(foreach=foreach, fused=False, capturable=False)
            optimizer.load_state_dict(state)
            versions.append((parameters, optimizer))
        device_gradients = {i: g.to(args.device) for i, g in gradients.items()}
        parameter_max = moment_max = norm_max = 0.
        for update in range(4):
            # An entire group and some individual parameters have no gradient,
            # then return. A zero gradient must not replace an absent one.
            absent = set(saved['param_groups'][0]['params']) if update == 1 else set()
            if update == 2:
                absent.update(identifiers[::3])
            norms, timings = [], []
            for foreach, (parameters, optimizer) in zip((False, True), versions):
                optimizer.zero_grad(set_to_none=True)
                for i, p in parameters.items():
                    p.grad = None if i in absent else device_gradients[i].clone()
                for group, original in zip(optimizer.param_groups, saved['param_groups']):
                    group['lr'] = original['lr']*(1.-.03*update)
                torch.npu.synchronize()
                tick = time.monotonic()
                norm = torch.nn.utils.clip_grad_norm_(parameters.values(), .5,
                                                      error_if_nonfinite=True, foreach=foreach)
                torch.npu.synchronize()
                clipped = time.monotonic()
                optimizer.step()
                torch.npu.synchronize()
                ended = time.monotonic()
                norms.append(norm.cpu())
                timings.append(dict(foreach=foreach, clip_seconds=clipped-tick,
                                    adam_seconds=ended-clipped, total_seconds=ended-tick))
            torch.testing.assert_close(norms[0], norms[1], atol=2e-6, rtol=2e-5)
            norm_max = max(norm_max, float((norms[0]-norms[1]).abs()))
            a, b = versions
            for i in identifiers:
                left, right = a[0][i].detach().cpu(), b[0][i].detach().cpu()
                torch.testing.assert_close(left, right, atol=2e-6, rtol=2e-5)
                parameter_max = max(parameter_max, float((left-right).abs().max()))
                sa, sb = a[1].state[a[0][i]], b[1].state[b[0][i]]
                assert sa.keys() == sb.keys()
                for key in sa:
                    left, right = sa[key].cpu(), sb[key].cpu()
                    torch.testing.assert_close(left, right, atol=0 if key == 'step' else 2e-7,
                                               rtol=0 if key == 'step' else 2e-5)
                    if key != 'step':
                        moment_max = max(moment_max, float((left-right).abs().max()))
            report['results'].append(dict(update=update, absent=len(absent), timings=timings))
            if update == 2:
                # Exercise the native state-dict path before another update.
                for _, optimizer in versions:
                    optimizer.load_state_dict(copy.deepcopy(optimizer.state_dict()))
        report.update(passed=True, parameter_max_error=parameter_max,
                      moment_max_error=moment_max, norm_max_error=norm_max,
                      peak_allocated_bytes=torch.npu.max_memory_allocated(),
                      peak_reserved_bytes=torch.npu.max_memory_reserved())
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        report['seconds'] = time.monotonic()-started
        args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
