"""First-order packed GRU backward with one buffer per gate gradient.

CPU's composite packed GRU builds a slice backward for every time step. Each
slice backward can zero a full packed gate tensor before adding its gradient.
Here each step writes its own rows once, followed by batched weight reductions.
The equations, parameter ownership, dtype and variable-length packing are kept.
"""
import torch
from typing import List
from torch.autograd.function import once_differentiable
from torch.nn import functional as F


@torch.jit.script
def _recurrent_backward(tape: torch.Tensor, grad_hidden: torch.Tensor,
                        weight_hh: torch.Tensor, sizes: List[int]):
    """Run the reverse recurrence without a Python dispatch for each gate."""
    width = weight_hh.shape[1]
    input_grads = tape.new_empty((len(tape), 3 * width))
    recurrent_grads = torch.empty_like(input_grads)
    hidden_grad = grad_hidden.clone()
    end = len(tape)
    for step in range(len(sizes) - 1, -1, -1):
        count = sizes[step]
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
    return input_grads, recurrent_grads


def packed_forward(data, sizes, weight_ih, weight_hh, bias_ih, bias_hh):
    width = weight_hh.shape[1]
    # Keep the recurrence in ATen rather than dispatching every gate from
    # Python. The custom backward still avoids the native slice-backward
    # allocations. Reconstruct its tape in two batched matrix products from
    # the native packed output; there is no second recurrent forward pass.
    batch_sizes = torch.tensor(sizes, dtype=torch.long)
    parameters = [weight_ih, weight_hh]
    if (bias_ih is None) != (bias_hh is None):
        raise ValueError('Packed GRU requires both biases or neither')
    if bias_ih is not None:
        parameters.extend((bias_ih, bias_hh))
    output, hidden = torch.ops.aten.gru.data(
        data, batch_sizes, data.new_zeros((1, sizes[0], width)),
        parameters, bias_ih is not None, 1, 0., False, False)
    # At t>0, packed row offset_t+i follows offset_(t-1)+i. The
    # difference is the previous time step's active batch size.
    previous_indices = (torch.arange(sizes[0], len(data))
                        - torch.repeat_interleave(batch_sizes[:-1], batch_sizes[1:]))
    previous = torch.cat((data.new_zeros((sizes[0], width)),
                          output.index_select(0, previous_indices)))
    ir, iz, inn = F.linear(data, weight_ih, bias_ih).chunk(3, -1)
    hr, hz, hn = F.linear(previous, weight_hh, bias_hh).chunk(3, -1)
    reset = torch.sigmoid(ir + hr)
    update = torch.sigmoid(iz + hz)
    candidate = torch.tanh(inn + reset * hn)
    tape = torch.cat((previous, reset, update, candidate, hn), -1)
    return hidden[0], tape


def packed_backward(grad_hidden, data, weight_ih, weight_hh, tape, sizes, has_bias, needs):
    width = weight_hh.shape[1]
    # Shorter sequences retain their final-state gradient until their last
    # time step enters the growing active prefix during reverse traversal.
    input_grads, recurrent_grads = _recurrent_backward(
        tape, grad_hidden, weight_hh, list(sizes))
    grad_data = input_grads @ weight_ih if needs[0] else None
    grad_ih = input_grads.T @ data if needs[1] else None
    grad_hh = recurrent_grads.T @ tape[:, :width] if needs[2] else None
    grad_bi = input_grads.sum(0) if has_bias[0] and needs[3] else None
    grad_bh = recurrent_grads.sum(0) if has_bias[1] and needs[4] else None
    return grad_data, grad_ih, grad_hh, grad_bi, grad_bh


class _PackedFinal(torch.autograd.Function):
    @staticmethod
    def forward(ctx, data, sizes, weight_ih, weight_hh, bias_ih, bias_hh):
        hidden, tape = packed_forward(data, sizes, weight_ih, weight_hh, bias_ih, bias_hh)
        ctx.save_for_backward(data, weight_ih, weight_hh, tape)
        ctx.sizes = sizes
        ctx.has_bias = (bias_ih is not None, bias_hh is not None)
        return hidden

    @staticmethod
    @once_differentiable
    def backward(ctx, grad_hidden):
        gradients = packed_backward(grad_hidden, *ctx.saved_tensors, ctx.sizes,
            ctx.has_bias, (ctx.needs_input_grad[0], *ctx.needs_input_grad[2:]))
        return gradients[0], None, *gradients[1:]


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
