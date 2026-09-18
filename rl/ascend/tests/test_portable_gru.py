import copy
import unittest
import torch
from draftrl.portable_gru import final_hidden


class PortableGRUTests(unittest.TestCase):
    def test_variable_length_outputs_and_all_parameter_gradients(self):
        torch.manual_seed(139)
        original = torch.nn.GRU(4, 7, batch_first=True)
        portable = copy.deepcopy(original)
        a = torch.randn(5, 9, 4, requires_grad=True)
        b = a.detach().clone().requires_grad_()
        lengths = torch.tensor([1, 9, 4, 7, 4])
        packed = torch.nn.utils.rnn.pack_padded_sequence(a, lengths, batch_first=True, enforce_sorted=False)
        expected = original(packed)[1][0]
        actual = final_hidden(portable, b, lengths)
        torch.testing.assert_close(actual, expected, rtol=2e-5, atol=2e-6)
        target = torch.randn_like(actual)
        (actual * target).sum().backward()
        (expected * target).sum().backward()
        torch.testing.assert_close(a.grad, b.grad, rtol=2e-5, atol=2e-6)
        for old, new in zip(original.parameters(), portable.parameters()):
            torch.testing.assert_close(old.grad, new.grad, rtol=2e-5, atol=2e-6)


class PackedCPUBridgeTests(unittest.TestCase):
    def test_functional_cpu_bridge_preserves_outputs_gradients_and_parameter_ownership(self):
        from draftrl.portable_gru import cpu_packed_hidden
        torch.manual_seed(139)
        original = torch.nn.GRU(4, 7, batch_first=True)
        candidate = copy.deepcopy(original)
        identities = [id(p) for p in candidate.parameters()]
        a = torch.randn(5, 9, 4, requires_grad=True)
        b = a.detach().clone().requires_grad_()
        lengths = torch.tensor([1, 9, 4, 7, 4])
        expected = final_hidden(original, a, lengths)
        actual = cpu_packed_hidden(candidate, b, lengths)
        target = torch.randn_like(actual)
        (actual * target).sum().backward()
        (expected * target).sum().backward()
        torch.testing.assert_close(actual, expected, rtol=2e-5, atol=2e-6)
        torch.testing.assert_close(a.grad, b.grad, rtol=2e-5, atol=2e-6)
        self.assertEqual(identities, [id(p) for p in candidate.parameters()])
        for left, right in zip(original.parameters(), candidate.parameters()):
            self.assertTrue(right.is_leaf)
            torch.testing.assert_close(left.grad, right.grad, rtol=2e-5, atol=2e-6)
