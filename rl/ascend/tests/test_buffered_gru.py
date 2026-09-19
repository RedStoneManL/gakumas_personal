"""Check the analytical recurrence against PyTorch and finite differences."""
import copy
import unittest

import torch

from draftrl.buffered_gru import cpu_buffered_hidden
from draftrl.portable_gru import cpu_packed_hidden


class BufferedGRUTests(unittest.TestCase):
    def test_ragged_outputs_inputs_parameters_and_adam(self):
        for lengths in ([1], [8, 8, 8], [1, 9, 4, 7, 4], [7, 1, 2, 2, 7]):
            for bias in (True, False):
                with self.subTest(lengths=lengths, bias=bias):
                    torch.manual_seed(719)
                    reference = torch.nn.GRU(4, 7, batch_first=True, bias=bias).double()
                    candidate = copy.deepcopy(reference)
                    identities = [id(p) for p in candidate.parameters()]
                    # Non-contiguous input and extra unused trailing padding.
                    a = torch.randn(len(lengths), max(lengths) + 2, 8,
                                    dtype=torch.float64)[:, :, ::2].requires_grad_()
                    b = a.detach().clone().requires_grad_()
                    lens = torch.tensor(lengths)
                    expected = cpu_packed_hidden(reference, a, lens)
                    actual = cpu_buffered_hidden(candidate, b, lens)
                    target = torch.randn_like(expected)
                    (expected * target).sum().backward()
                    (actual * target).sum().backward()
                    torch.testing.assert_close(actual, expected, rtol=1e-12, atol=1e-12)
                    torch.testing.assert_close(a.grad, b.grad, rtol=1e-11, atol=1e-12)
                    self.assertEqual(identities, [id(p) for p in candidate.parameters()])
                    for p, q in zip(reference.parameters(), candidate.parameters()):
                        self.assertTrue(q.is_leaf)
                        torch.testing.assert_close(q.grad, p.grad, rtol=1e-11, atol=1e-12)
                    for model in (reference, candidate):
                        torch.optim.Adam(model.parameters(), lr=5e-4, eps=1e-5).step()
                    for p, q in zip(reference.parameters(), candidate.parameters()):
                        torch.testing.assert_close(q, p, rtol=1e-11, atol=1e-12)

    def test_finite_difference_of_packed_inputs_and_all_weights(self):
        from draftrl.buffered_gru import _PackedFinal
        torch.manual_seed(719)
        gru = torch.nn.GRU(2, 3, batch_first=True).double()
        data = torch.randn(6, 2, dtype=torch.float64, requires_grad=True)
        def recurrence(inputs, *parameters):
            return _PackedFinal.apply(inputs, (3, 2, 1), *parameters)
        self.assertTrue(torch.autograd.gradcheck(
            recurrence, (data, *gru.parameters()), fast_mode=True))

    def test_input_only_gradient_with_frozen_parameters(self):
        torch.manual_seed(719)
        gru = torch.nn.GRU(4, 7, batch_first=True)
        gru.requires_grad_(False)
        a = torch.randn(4, 6, 4, requires_grad=True)
        b = a.detach().clone().requires_grad_()
        lengths = torch.tensor([4, 1, 6, 3])
        cpu_packed_hidden(gru, a, lengths).square().sum().backward()
        cpu_buffered_hidden(gru, b, lengths).square().sum().backward()
        torch.testing.assert_close(a.grad, b.grad, atol=2e-6, rtol=2e-5)

    def test_rejects_unsupported_architecture(self):
        with self.assertRaises(ValueError):
            cpu_buffered_hidden(torch.nn.GRU(4, 7, num_layers=2, batch_first=True),
                                torch.randn(2, 3, 4), torch.tensor([2, 3]))

    def test_microbatch_accumulation_and_reused_backward(self):
        torch.manual_seed(720)
        reference = torch.nn.GRU(4, 7, batch_first=True)
        candidate = copy.deepcopy(reference)
        for lengths in ([3, 1, 5], [2, 2, 4]):
            data = torch.randn(3, 5, 4)
            target = torch.randn(3, 7)
            for model, function in ((reference, cpu_packed_hidden), (candidate, cpu_buffered_hidden)):
                loss = (function(model, data, torch.tensor(lengths)) * target).mean()
                loss.backward(retain_graph=True)
                loss.backward()
        for p, q in zip(reference.parameters(), candidate.parameters()):
            torch.testing.assert_close(q.grad, p.grad, atol=2e-6, rtol=2e-5)
