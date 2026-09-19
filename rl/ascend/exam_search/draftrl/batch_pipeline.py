"""Bounded CPU input preparation ahead of the owning learner thread.

Only immutable input structure is prefetched. Parameters, RNG, accelerator
transfers, collectives and optimizer steps remain on the learner thread.
"""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import os
import time
import torch
from .encoding import collate


def prepare_cpu(examples, *, npu=False):
    batch = collate(examples, 'cpu')
    if npu:
        from round2rl.model import attach_pool_metadata
        from .fast_collate import _tower_metadata, _typed_metadata

        def metadata(part):
            for key, size in (('entities', part['entity_count']),
                              ('batches', part['batch_size'])):
                groups = part[key]
                attach_pool_metadata(groups, groups.numpy(), size, 'cpu')
            _tower_metadata(part, part['batches'].numpy(), part['phase'].numpy(),
                            part['edge_src'].numpy(), part['edge_dst'].numpy(),
                            part['edge_word'].numpy(), 'cpu', prepare_npu=True)
            if 'node_types' in part:
                _typed_metadata(part, part['node_types'].numpy(), 'cpu', prepare_npu=True)
            if 'relational' in part:
                metadata(part['relational'])

        metadata(batch)
    return batch


def transfer(batch, device):
    """Retain CPU packing lengths and tensor-attached grouped-max plans."""
    def move(value, key=None):
        if isinstance(value, torch.Tensor):
            if key == 'lengths':
                return value
            result = value.to(device)
            plan = getattr(value, '_arena_segment_plan', None)
            if plan is not None:
                result._arena_segment_plan = move(plan)
            counts = getattr(value, '_arena_segment_counts', None)
            if counts is not None:
                result._arena_segment_counts = move(counts)
            return result
        if isinstance(value, dict):
            return {k: move(v, k) for k, v in value.items()}
        if isinstance(value, tuple):
            return tuple(move(v) for v in value)
        return value
    return move(batch)


class BatchStream:
    """At most two CPU microbatches ahead; close on KL stop or any exception."""
    def __init__(self, records, shards, microbatch, device, *, enabled=None, depth=2):
        if microbatch < 1 or depth < 1:
            raise ValueError('Positive microbatch and prefetch depth required')
        mode = os.environ.get('GAKUMAS_PPO_PREFETCH', 'auto')
        if mode not in ('0', '1', 'auto'):
            raise ValueError('GAKUMAS_PPO_PREFETCH must be 0, 1 or auto')
        self.npu = str(device).startswith('npu')
        self.enabled = (mode == '1' or (mode == 'auto' and self.npu)) if enabled is None else enabled
        self.records, self.device, self.depth = records, device, depth
        self.blocks = [[shard[i:i+microbatch] for i in range(0, len(shard), microbatch)]
                       for shard in shards]
        self.tasks = iter((block, indices) for block, chunks in enumerate(self.blocks) for indices in chunks)
        self.pending = deque()
        self.executor = None
        self.next_block = 0
        self.stats = dict(enabled=self.enabled, microbatches=0, prepare_seconds=0.,
                          wait_seconds=0., transfer_seconds=0.)

    def _prepare(self, task):
        block, indices = task
        tick = time.monotonic()
        batch = prepare_cpu([self.records[i]['encoded'] for i in indices], npu=self.npu)
        return block, indices, batch, time.monotonic() - tick

    def _fill(self):
        while len(self.pending) < self.depth:
            task = next(self.tasks, None)
            if task is None:
                break
            self.pending.append(self.executor.submit(self._prepare, task))

    def __enter__(self):
        if self.enabled:
            self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ppo-input')
            self._fill()
        return self

    def block(self, block):
        if block != self.next_block:
            raise ValueError('Input blocks must follow optimizer order')
        self.next_block += 1
        for indices in self.blocks[block]:
            if self.enabled:
                tick = time.monotonic()
                prepared_block, prepared_indices, cpu, seconds = self.pending.popleft().result()
                self.stats['wait_seconds'] += time.monotonic() - tick
                if prepared_block != block or prepared_indices != indices:
                    raise RuntimeError('Prefetched input ownership mismatch')
                self.stats['prepare_seconds'] += seconds
                self._fill()
                tick = time.monotonic()
                batch = transfer(cpu, self.device)
                self.stats['transfer_seconds'] += time.monotonic() - tick
            else:
                tick = time.monotonic()
                batch = collate([self.records[i]['encoded'] for i in indices], self.device)
                self.stats['prepare_seconds'] += time.monotonic() - tick
            self.stats['microbatches'] += 1
            yield indices, batch

    def __exit__(self, *_):
        for future in self.pending:
            future.cancel()
        if self.executor is not None:
            self.executor.shutdown(wait=True, cancel_futures=True)
        self.pending.clear()
