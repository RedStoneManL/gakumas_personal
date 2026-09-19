"""Independent branch gradients, accumulation and unused-output semantics."""
import copy
import unittest
import torch
from draftrl.parallel_lexical import parallel_cpu_hidden
from draftrl.portable_gru import cpu_packed_hidden


class ParallelLexicalTests(unittest.TestCase):
    def test_four_branches_inputs_parameters_and_adam(self):
        torch.manual_seed(871)
        original = [torch.nn.GRU(4, 7, batch_first=True, bias=i % 2 == 0).double()
                    for i in range(4)]
        parallel = copy.deepcopy(original)
        lengths = [torch.tensor(x) for x in ([1, 7, 3], [6, 2], [4, 1, 9, 7], [1])]
        inputs = [torch.randn(len(x), int(x.max()) + 2, 4, dtype=torch.float64,
                              requires_grad=True) for x in lengths]
        copied = [x.detach().clone().requires_grad_() for x in inputs]
        targets = [torch.randn(len(x), 7, dtype=torch.float64) for x in lengths]
        expected = [cpu_packed_hidden(g, x, l) for g, x, l in zip(original, inputs, lengths)]
        actual = parallel_cpu_hidden(list(zip(parallel, copied, lengths)))
        for a, b in zip(expected, actual):
            torch.testing.assert_close(a, b, atol=1e-12, rtol=1e-12)
        for values in (expected, actual):
            loss = sum((value * target).sum() for value, target in zip(values, targets))
            loss.backward(retain_graph=True)
            loss.backward()
        for a, b in zip(inputs, copied):
            torch.testing.assert_close(a.grad, b.grad, atol=1e-11, rtol=1e-10)
        for a, b in zip(original, parallel):
            for left, right in zip(a.parameters(), b.parameters()):
                self.assertTrue(right.is_leaf)
                torch.testing.assert_close(left.grad, right.grad, atol=1e-11, rtol=1e-10)
            for gru in (a, b):
                torch.optim.Adam(gru.parameters(), lr=5e-4, eps=1e-5).step()
            for left, right in zip(a.parameters(), b.parameters()):
                torch.testing.assert_close(left, right, atol=1e-11, rtol=1e-10)

    def test_unused_branch_does_not_receive_fabricated_zero_gradients(self):
        torch.manual_seed(872)
        grus = [torch.nn.GRU(3, 5, batch_first=True) for _ in range(2)]
        inputs = [torch.randn(2, 4, 3, requires_grad=True) for _ in grus]
        values = parallel_cpu_hidden([(g, x, torch.tensor([4, 1])) for g, x in zip(grus, inputs)])
        values[0].square().sum().backward()
        self.assertIsNotNone(inputs[0].grad)
        self.assertIsNone(inputs[1].grad)
        self.assertTrue(all(p.grad is None for p in grus[1].parameters()))

    def test_frozen_weights_repeated_forwards_and_shared_inputs(self):
        torch.manual_seed(873)
        models = [torch.nn.GRU(3, 5, batch_first=True) for _ in range(4)]
        for model in models:
            model.requires_grad_(False)
        for _ in range(2):
            x = torch.randn(2, 4, 3, requires_grad=True)
            y = x.detach().clone().requires_grad_()
            lengths = torch.tensor([4, 2])
            expected = [cpu_packed_hidden(g, x, lengths) for g in models]
            actual = parallel_cpu_hidden([(g, y, lengths) for g in models])
            sum(v.square().sum() for v in expected).backward()
            sum(v.square().sum() for v in actual).backward()
            torch.testing.assert_close(x.grad, y.grad, atol=2e-6, rtol=2e-5)
