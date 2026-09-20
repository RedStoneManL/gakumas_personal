"""Concurrent CPU lexical branches with one owning accelerator thread.

The four actor/critic GRUs are independent. Accelerator embeddings, parameter
copies and final-state copies stay on the caller; only CPU recurrence kernels
run on the bounded pool. A single autograd node joins their reverse passes.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os
import threading

import torch
from torch.autograd.function import once_differentiable

from .buffered_gru import packed_forward, packed_backward

_pool = None
_lock = threading.Lock()


def _run(function, arguments):
    # grad mode is thread-local; Function.forward's no-grad mode does not
    # propagate into an executor thread. These kernels supply their own VJP.
    with torch.no_grad():
        return function(*arguments)


def _parallel(function, arguments):
    global _pool
    with _lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='lexical-cpu')
    futures = [_pool.submit(_run, function, argument) for argument in arguments]
    try:
        return [future.result() for future in futures]
    finally:
        # No work may outlive a failed owning forward/backward and race a
        # subsequent optimizer step or reuse of the same parameter storage.
        for future in futures:
            try:
                future.result()
            except Exception:
                pass


class _PackedMany(torch.autograd.Function):
    @staticmethod
    def forward(ctx, sizes, *inputs):
        if not sizes or len(inputs) != 5 * len(sizes):
            raise ValueError('Unaligned parallel GRU inputs')
        groups = [inputs[5*i:5*i+5] for i in range(len(sizes))]
        results = _parallel(packed_forward, [
            (data, size, *parameters) for size, (data, *parameters) in zip(sizes, groups)])
        ctx.sizes = sizes
        ctx.has_bias = [(group[3] is not None, group[4] is not None) for group in groups]
        ctx.set_materialize_grads(False)
        ctx.save_for_backward(*(tensor for group, (_, tape) in zip(groups, results)
                                for tensor in (*group[:3], tape)))
        return tuple(hidden for hidden, _ in results)

    @staticmethod
    @once_differentiable
    def backward(ctx, *gradients):
        results = [None] * len(ctx.sizes)
        active = [i for i, gradient in enumerate(gradients) if gradient is not None]
        arguments = [(gradients[i], *ctx.saved_tensors[4*i:4*i+4], ctx.sizes[i],
                      ctx.has_bias[i], ctx.needs_input_grad[1+5*i:1+5*i+5]) for i in active]
        for index, result in zip(active, _parallel(packed_backward, arguments)):
            results[index] = result
        return (None, *(gradient for result in results
                        for gradient in (result if result is not None else (None,) * 5)))


def parallel_cpu_hidden(jobs):
    """Compute independent (GRU, padded embeddings, lengths) jobs together."""
    inputs, sizes, packed_inputs, devices = [], [], [], []
    for gru, padded, lengths in jobs:
        if gru.num_layers != 1 or gru.bidirectional or not gru.batch_first or gru.dropout:
            raise ValueError('Parallel lexical GRU requires one layer without dropout')
        packed = torch.nn.utils.rnn.pack_padded_sequence(
            padded.to('cpu'), lengths.to('cpu'), batch_first=True, enforce_sorted=False)
        parameters = [getattr(gru, name, None) for name in
                      ('weight_ih_l0', 'weight_hh_l0', 'bias_ih_l0', 'bias_hh_l0')]
        inputs.extend((packed.data, *(p.to('cpu') if p is not None else None for p in parameters)))
        sizes.append(tuple(packed.batch_sizes.tolist()))
        packed_inputs.append(packed)
        devices.append(padded.device)
    states = _PackedMany.apply(tuple(sizes), *inputs)
    return [state.index_select(0, packed.unsorted_indices).to(device)
            if packed.unsorted_indices is not None else state.to(device)
            for state, packed, device in zip(states, packed_inputs, devices)]


@contextmanager
def training_lexical(model, batch):
    """Scope differentiable lexical reuse to exactly one training forward."""
    enabled = (torch.is_grad_enabled() and batch['bytes'].device.type == 'npu'
               and os.environ.get('GAKUMAS_LEXICAL_GRU_BACKEND', 'cpu-buffered') == 'cpu-buffered'
               and os.environ.get('GAKUMAS_PARALLEL_LEXICAL', '1') == '1')
    if not enabled:
        yield
        return
    from .lexical_cache import search_encoders
    encoders = search_encoders(model)
    batches = [batch, batch]
    if hasattr(model, 'actor_relational'):
        side = model._relational_batch(batch)
        batches.extend((side, side))
    if len(encoders) != len(batches):
        raise ValueError('Unaligned actor/critic lexical branches')
    vectors = parallel_cpu_hidden([(encoder.text, encoder.byte(b['bytes']), b['lengths'])
                                  for encoder, b in zip(encoders, batches)])
    previous = [getattr(encoder, '_training_lexical', None) for encoder in encoders]
    try:
        for encoder, b, vector in zip(encoders, batches, vectors):
            encoder._training_lexical = (b, vector)
        yield
    finally:
        for encoder, old in zip(encoders, previous):
            encoder._training_lexical = old
