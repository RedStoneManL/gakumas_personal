"""The existing one-layer GRU equations without PackedSequence device kernels."""
import torch
from torch.nn import functional as F


def cpu_packed_hidden(gru, padded, lengths):
    """Native CPU GRU with differentiable copies to/from the owning accelerator."""
    packed = torch.nn.utils.rnn.pack_padded_sequence(
        padded.to('cpu'), lengths.to('cpu'), batch_first=True, enforce_sorted=False)
    parameters = {name: parameter.to('cpu') for name, parameter in gru.named_parameters()}
    _, state = torch.func.functional_call(gru, parameters, (packed,))
    return state[0].to(padded.device)


def final_hidden(gru, padded, lengths):
    if gru.num_layers != 1 or gru.bidirectional or not gru.batch_first or gru.dropout:
        raise ValueError('Portable lexical GRU requires one unidirectional layer without dropout')
    if padded.device.type == 'npu':
        import os
        backend = os.environ.get('GAKUMAS_LEXICAL_GRU_BACKEND', 'cpu-buffered')
        if backend not in ('cpu', 'cpu-buffered', 'portable'):
            raise ValueError('Unknown lexical GRU backend')
        if backend == 'cpu-buffered':
            if torch.is_grad_enabled():
                from .buffered_gru import cpu_buffered_hidden
                return cpu_buffered_hidden(gru, padded, lengths)
            return cpu_packed_hidden(gru, padded, lengths)
        if backend == 'cpu':
            return cpu_packed_hidden(gru, padded, lengths)
    hidden = padded.new_zeros((len(padded), gru.hidden_size))
    lengths = lengths.to(device=padded.device)
    inputs = F.linear(padded, gru.weight_ih_l0, gru.bias_ih_l0)
    for step in range(padded.shape[1]):
        ir, iz, inn = inputs[:, step].chunk(3, -1)
        hr, hz, hn = F.linear(hidden, gru.weight_hh_l0, gru.bias_hh_l0).chunk(3, -1)
        reset, update = torch.sigmoid(ir + hr), torch.sigmoid(iz + hz)
        candidate = torch.tanh(inn + reset * hn)
        proposed = candidate + update * (hidden - candidate)
        hidden = torch.where((lengths > step)[:, None], proposed, hidden)
    return hidden
