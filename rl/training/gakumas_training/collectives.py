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


class CollectiveGroup:
    def sum_values(self, values):
        if self.size == 1:
            return values
        names = sorted(values)
        tensor = torch.tensor([values[k] for k in names], dtype=torch.float32, device=self.device)
        dist.all_reduce(tensor, group=self.data_group)
        return dict(zip(names, tensor.cpu().tolist()))

    def gather_lists(self, values):
        if self.size == 1:
            return values
        results = [None] * self.size
        dist.all_gather_object(results, values)
        return [item for result in results for item in result]

    def __init__(self, requested, *, torch_threads=2):
        from .device import device_kind, resolve_device
        kind = device_kind(requested)
        if type(torch_threads) is not int or torch_threads < 1:
            raise ValueError('torch_threads must be a positive integer')
        torch.set_num_threads(torch_threads)
        self.rank = int(os.environ.get('RANK', '0'))
        self.size = int(os.environ.get('WORLD_SIZE', '1'))
        if self.size < 1 or int(os.environ.get('LOCAL_WORLD_SIZE', self.size)) != self.size:
            raise ValueError('This port requires one host and a positive learner count')
        local_rank = int(os.environ.get('LOCAL_RANK', '0'))
        if not 0 <= self.rank < self.size or local_rank != self.rank:
            raise ValueError('Invalid rank mapping for a single-host learner group')
        selected = requested if self.size == 1 else ('cpu' if kind == 'cpu' else f'{kind}:{local_rank}')
        self.device = resolve_device(selected)
        self.data_group = None
        if self.size > 1:
            # Collecting a full public-search batch can take hours. Failed ranks
            # still terminate the job through torchrun's process supervision.
            timeout = timedelta(hours=72)
            dist.init_process_group('gloo', timeout=timeout)
            backend = {'npu': 'hccl', 'cuda': 'nccl', 'cpu': 'gloo'}[kind]
            self.data_group = dist.new_group(backend=backend, timeout=timeout)

    def broadcast(self, value=None):
        if self.size == 1:
            return value
        box = [value if self.rank == 0 else None]
        dist.broadcast_object_list(box, src=0)
        return box[0]

    def shuffle(self, order):
        if self.rank == 0:
            random.shuffle(order)
        order[:] = self.broadcast(order)

    def totals(self, counter):
        if self.size == 1:
            return counter
        names = ('loss', 'policy_loss', 'value_loss', 'distribution_loss',
                 'search_loss', 'entropy_bonus', 'kl_sum', 'kl_count', 'clip_count')
        values = torch.tensor([counter[k] for k in names], dtype=torch.float32, device=self.device)
        dist.all_reduce(values, group=self.data_group)
        # Assign the sum; Counter.update would add it to the local values.
        for name, value in zip(names, values.cpu().tolist()):
            counter[name] = value
        return counter

    def gradients(self, model):
        if self.size == 1:
            return
        parameters = [p for p in model.parameters() if p.requires_grad]
        present = torch.tensor([p.grad is not None for p in parameters], dtype=torch.float32, device=self.device)
        dist.all_reduce(present, op=dist.ReduceOp.MAX, group=self.data_group)
        active = present.cpu().tolist()
        selected = [p for p, yes in zip(parameters, active) if yes]
        if not selected:
            return
        # Current models are FP32. Refuse silent cast if mixed precision is added.
        if any(p.dtype != torch.float32 for p in selected):
            raise ValueError('Distributed learner currently requires FP32 parameters')
        flat = torch.cat([(p.grad if p.grad is not None else torch.zeros_like(p)).reshape(-1) for p in selected])
        dist.all_reduce(flat, op=dist.ReduceOp.SUM, group=self.data_group)
        offset = 0
        for p in selected:
            p.grad = flat[offset:offset+p.numel()].view_as(p).clone()
            offset += p.numel()
