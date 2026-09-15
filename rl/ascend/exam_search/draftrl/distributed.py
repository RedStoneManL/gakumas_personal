"""One sampler/coordinator and synchronous sharded learners under torchrun.

Control traffic uses CPU Gloo; NPU gradients use HCCL (CUDA: NCCL). Every
microbatch loss is divided by the GLOBAL optimizer block size. Gradients are
summed, not averaged again, preserving the single-learner objective exactly.
"""
from datetime import timedelta
import os
import random

import torch
import torch.distributed as dist

ACTIVE = None


def cpu_copy(value):
    if torch.is_tensor(value):
        return value.detach().cpu()
    if isinstance(value, dict):
        return {k: cpu_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [cpu_copy(v) for v in value]
    if isinstance(value, tuple):
        return tuple(cpu_copy(v) for v in value)
    return value


from gakumas_training.collectives import CollectiveGroup


class LearnerGroup(CollectiveGroup):
    def update(self, model, optimizer, records, config, progress=None):
        from .ppo import update
        if self.size > 1:
            names = {id(p): name for name, p in model.named_parameters()}
            groups = [[names[id(p)] for p in g['params']] for g in optimizer.param_groups]
            payload = {'command': 'update', 'model_config': model.config,
                       'model': cpu_copy(model.state_dict()), 'optimizer': cpu_copy(optimizer.state_dict()),
                       'groups': groups, 'records': records,
                       'config': {k: v for k, v in config.items() if k not in ('_search_router', '_coverage')}}
            self.broadcast(payload)
        return update(model, optimizer, records, config, self.device, progress=progress, mesh=self)

    def serve(self):
        from .model import DraftPolicy
        from .ppo import update
        from gakumas_training.device import optimizer_options, load_optimizer_state
        while True:
            payload = self.broadcast()
            if payload['command'] == 'stop':
                return
            if payload['command'] != 'update':
                raise ValueError('Unknown learner command')
            torch.set_num_threads(payload['config'].get('torch_threads', 2))
            model = DraftPolicy(**payload['model_config']).to(self.device)
            model.load_state_dict(payload['model'], strict=True)
            named = dict(model.named_parameters())
            optimizer = torch.optim.Adam([{'params': [named[n] for n in names]} for names in payload['groups']],
                                         **optimizer_options(model))
            load_optimizer_state(optimizer, payload['optimizer'], self.device)
            update(model, optimizer, payload['records'], payload['config'], self.device, mesh=self)
            del model, optimizer, payload

    def stop(self):
        if self.rank == 0 and self.size > 1:
            self.broadcast({'command': 'stop'})

    def close(self):
        if dist.is_initialized():
            dist.destroy_process_group()


def update_distributed(model, optimizer, records, config, device, progress=None):
    if ACTIVE is not None:
        return ACTIVE.update(model, optimizer, records, config, progress)
    from .ppo import update
    return update(model, optimizer, records, config, device, progress)
