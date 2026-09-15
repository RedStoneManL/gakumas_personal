"""The existing one-layer GRU equations without PackedSequence device kernels."""
import torch
from torch.nn import functional as F


def final_hidden(gru, padded, lengths):
    if gru.num_layers != 1 or gru.bidirectional or not gru.batch_first or gru.dropout:
        raise ValueError('Portable lexical GRU requires one unidirectional layer without dropout')
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
