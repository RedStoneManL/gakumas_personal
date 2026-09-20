"""Prepared graph partitions preserve outputs, tied-max VJPs and unused branches."""
import copy
import unittest
import numpy as np
import torch
from torch import nn
from draftrl.model import TaskTower
from draftrl.legacy_model import DraftPolicy
from draftrl.relational_model import RelationTower
from draftrl.tower_inputs import prepare_tower_inputs, forward_towers


class TowerInputTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(117)

    def compare(self, relational=False, phases=(0,2,0,4), tied=False):
        # Noncontiguous group ids plus cross-task edges exercise the original mask.
        groups=np.array([2,0,3,1,0,1,2,3,2],dtype=np.int64)
        src=np.array([0,1,2,3,4,5,6,7],dtype=np.int64)
        dst=np.array([6,4,7,5,3,1,8,0],dtype=np.int64)
        words=np.arange(len(src))%5
        parts=prepare_tower_inputs(groups,phases,src,dst,words,'cpu')
        prototype=RelationTower(8,4,2) if relational else TaskTower(DraftPolicy(width=8,lexical=4).actor,2)
        original=nn.ModuleDict({name:copy.deepcopy(prototype) for name in ('exam','build')})
        candidate=copy.deepcopy(original)
        x=(torch.ones(len(groups),8) if tied else torch.randn(len(groups),8)).requires_grad_()
        y=x.detach().clone().requires_grad_()
        lex=torch.randn(5,4,requires_grad=True);other=lex.detach().clone().requires_grad_()
        b=dict(batch_size=len(phases),tower_inputs=parts)
        expected=torch.zeros_like(x);states=x.new_zeros(len(phases),8)
        g=torch.tensor(groups);p=torch.tensor(phases);s=torch.tensor(src);d=torch.tensor(dst);w=torch.tensor(words)
        for name,tower in original.items():
            mask=p==0 if name=='exam' else p!=0
            if not mask.any():continue
            entities=mask[g];ids=entities.nonzero(as_tuple=True)[0]
            lookup=torch.full((len(x),),-1,dtype=torch.long);lookup[ids]=torch.arange(len(ids))
            edges=entities[s]&entities[d]
            a,c=tower(x[ids],g[ids],len(phases),lex,lookup[s[edges]],lookup[d[edges]],w[edges])
            expected=expected.index_copy(0,ids,a)
            samples=mask.nonzero(as_tuple=True)[0];states=states.index_copy(0,samples,c[samples])
        actual=forward_towers(candidate,y,b,other)
        for a,c in zip((expected,states),actual):torch.testing.assert_close(a,c,atol=1e-6,rtol=1e-5)
        probes=[torch.randn_like(a) for a in actual]
        sum((a*q).sum() for a,q in zip((expected,states),probes)).backward()
        sum((a*q).sum() for a,q in zip(actual,probes)).backward()
        for a,c in [(x.grad,y.grad),(lex.grad,other.grad),
                    *((a.grad,c.grad) for a,c in zip(original.parameters(),candidate.parameters()))]:
            self.assertEqual(a is None,c is None)
            if a is not None:torch.testing.assert_close(a,c,atol=2e-5,rtol=2e-5)
        for part in parts.values():self.assertTrue(hasattr(part['batches'],'_arena_segment_plan'))

    def test_legacy_mixed(self):self.compare()
    def test_relational_mixed(self):self.compare(relational=True)
    def test_tied_maxima(self):self.compare(tied=True)
    def test_empty_task(self):self.compare(phases=(0,0,0,0))
    def test_unknown_phase(self):
        with self.assertRaisesRegex(ValueError,'Unknown phase'):
            prepare_tower_inputs([0],[5],[],[],[],'cpu')


if __name__=='__main__':unittest.main()
