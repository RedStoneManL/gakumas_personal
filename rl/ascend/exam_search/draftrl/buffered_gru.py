"""First-order packed GRU backward with one buffer per gate gradient.

CPU's composite packed GRU builds a slice backward for every time step. Each
slice backward can zero a full packed gate tensor before adding its gradient.
Here each step writes its own rows once, followed by batched weight reductions.
The equations, parameter ownership, dtype and variable-length packing are kept.
"""
import torch
from torch.autograd.function import once_differentiable
from torch.nn import functional as F


class _PackedFinal(torch.autograd.Function):
    @staticmethod
    def forward(ctx, data, sizes, weight_ih, weight_hh, bias_ih, bias_hh):
        width = weight_hh.shape[1]
        hidden = data.new_zeros((sizes[0], width))
        inputs = F.linear(data, weight_ih, bias_ih)
        # Previous state, reset, update, candidate and recurrent candidate input.
        tape = data.new_empty((len(data), 5 * width))
        offset = 0
        for count in sizes:
            end = offset + count
            previous, reset, update, candidate, recurrent_n = tape[offset:end].chunk(5, -1)
            previous.copy_(hidden[:count])
            ir, iz, inn = inputs[offset:end].chunk(3, -1)
            hr, hz, hn = F.linear(previous, weight_hh, bias_hh).chunk(3, -1)
            reset.copy_(torch.sigmoid(ir + hr))
            update.copy_(torch.sigmoid(iz + hz))
            recurrent_n.copy_(hn)
            candidate.copy_(torch.tanh(inn + reset * hn))
            hidden[:count].copy_(candidate + update * (previous - candidate))
            offset = end
        ctx.save_for_backward(data, weight_ih, weight_hh, tape)
        ctx.sizes = sizes
        ctx.has_bias = (bias_ih is not None, bias_hh is not None)
        return hidden

    @staticmethod
    @once_differentiable
    def backward(ctx, grad_hidden):
        data, weight_ih, weight_hh, tape = ctx.saved_tensors
        width = weight_hh.shape[1]
        input_grads = data.new_empty((len(data), 3 * width))
        recurrent_grads = torch.empty_like(input_grads)
        # Shorter sequences retain their final-state gradient until their last
        # time step enters the growing active prefix during reverse traversal.
        hidden_grad = grad_hidden.clone()
        end = len(data)
        for count in reversed(ctx.sizes):
            start = end - count
            previous, reset, update, candidate, recurrent_n = tape[start:end].chunk(5, -1)
            dh = hidden_grad[:count]
            dn = dh * (1 - update) * (1 - candidate.square())
            dz = dh * (previous - candidate) * update * (1 - update)
            dr = dn * recurrent_n * reset * (1 - reset)
            ir, iz, inn = input_grads[start:end].chunk(3, -1)
            hr, hz, hn = recurrent_grads[start:end].chunk(3, -1)
            ir.copy_(dr); iz.copy_(dz); inn.copy_(dn)
            hr.copy_(dr); hz.copy_(dz); hn.copy_(dn * reset)
            hidden_grad[:count].copy_(dh * update + recurrent_grads[start:end] @ weight_hh)
            end = start
        needs = ctx.needs_input_grad
        grad_data = input_grads @ weight_ih if needs[0] else None
        grad_ih = input_grads.T @ data if needs[2] else None
        grad_hh = recurrent_grads.T @ tape[:, :width] if needs[3] else None
        grad_bi = input_grads.sum(0) if ctx.has_bias[0] and needs[4] else None
        grad_bh = recurrent_grads.sum(0) if ctx.has_bias[1] and needs[5] else None
        return grad_data, None, grad_ih, grad_hh, grad_bi, grad_bh


def cpu_buffered_hidden(gru, padded, lengths):
    """Return the zero-initialized final state, preserving accelerator leaves.

This is a first-order training backend; higher-order differentiation is not
supported. Packing and device copies stay outside the custom autograd function
so the normal embedding and owning-device parameter gradients are preserved.
"""
    if gru.num_layers != 1 or gru.bidirectional or not gru.batch_first or gru.dropout:
        raise ValueError('Buffered lexical GRU requires one unidirectional layer without dropout')
    packed = torch.nn.utils.rnn.pack_padded_sequence(
        padded.to('cpu'), lengths.to('cpu'), batch_first=True, enforce_sorted=False)
    parameters = [getattr(gru, name, None) for name in
                  ('weight_ih_l0', 'weight_hh_l0', 'bias_ih_l0', 'bias_hh_l0')]
    parameters = [parameter.to('cpu') if parameter is not None else None for parameter in parameters]
    state = _PackedFinal.apply(packed.data, tuple(packed.batch_sizes.tolist()), *parameters)
    if packed.unsorted_indices is not None:
        state = state.index_select(0, packed.unsorted_indices)
    return state.to(padded.device)
