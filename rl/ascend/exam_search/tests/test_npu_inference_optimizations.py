"""Cache and structural-index equivalence, including nonzero relational gradients."""
import copy
import unittest
from unittest.mock import patch
import torch
from test_relational_model import examples, NODE_TYPES
from draftrl.fast_collate import _collate_base
from draftrl.relational_model import RelationalStem
from draftrl.lexical_cache import lexical

def side_batch():
    pairs=[examples(p)[1:] for p in (0,2)]
    batch=_collate_base([p[0] for p in pairs])
    batch['node_types']=torch.tensor([t for p in pairs for t in p[1]])
    return batch

class InferenceOptimizationTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(34)

    def test_cached_relational_lexemes_match_and_gradients_bypass_cache(self):
        stem=RelationalStem(width=16,lexical=4)
        batch=side_batch()
        with torch.inference_mode():
            expected=lexical(stem,batch)
            stem._search_lex_cache={}
            with patch.object(stem,'word_vectors',wraps=stem.word_vectors) as call:
                cold=lexical(stem,batch);warm=lexical(stem,batch)
                self.assertEqual(call.call_count,1)
            torch.testing.assert_close(expected,cold,rtol=0,atol=0)
            torch.testing.assert_close(expected,warm,rtol=0,atol=0)
        self.assertTrue(all(not x.requires_grad for x in stem._search_lex_cache.values()))
        with patch.object(stem,'word_vectors',wraps=stem.word_vectors) as call:
            lexical(stem,batch).square().sum().backward()
            self.assertEqual(call.call_count,1)
        self.assertGreater(float(stem.byte.weight.grad.abs().sum()),0)
        with torch.no_grad():
            stem.byte.weight.add_(.1)
            stem._search_lex_cache.clear()
            torch.testing.assert_close(lexical(stem,batch),stem.word_vectors(batch['bytes'],batch['lengths']))

    def test_precomputed_type_indices_preserve_forward_and_backward(self):
        stem=RelationalStem(width=16,lexical=4)
        other=copy.deepcopy(stem)
        batch=side_batch();prepared=dict(batch);types=batch['node_types']
        prepared['type_indices']=tuple((types==i).nonzero(as_tuple=True)[0] for i in range(len(NODE_TYPES)))
        scopes={'program_encoder':(1,2,3,4,5),'state_encoder':(0,6),'event_encoder':(7,12),
                'time_encoder':(8,),'zone_encoder':(9,),'constraint_encoder':(10,)}
        prepared['scope_indices']={k:torch.tensor([i for i,t in enumerate(types.tolist()) if t in ids],dtype=torch.long) for k,ids in scopes.items()}
        out=stem(batch)[0];candidate=other(prepared)[0]
        torch.testing.assert_close(out,candidate,rtol=0,atol=0)
        out.square().sum().backward();candidate.square().sum().backward()
        for (name,p),(_,q) in zip(stem.named_parameters(),other.named_parameters()):
            if p.grad is not None:torch.testing.assert_close(p.grad,q.grad,rtol=0,atol=0,msg=name)

class SegmentedPoolingTests(unittest.TestCase):
    def test_bucketed_max_matches_reference_and_tied_gradients(self):
        from round2rl.model import _segment_amax, prepare_segment_plan
        import numpy as np
        torch.set_num_threads(1)
        for sizes in ([0,1,3,2,17], [1000,1,1,0], [0,0], [4,4,4]):
            groups=np.repeat(np.arange(len(sizes)),sizes)
            order=np.random.default_rng(88).permutation(len(groups))
            groups=groups[order]
            plain=torch.from_numpy(groups.copy())
            prepared=plain.clone()
            prepared._arena_segment_plan=prepare_segment_plan(groups,len(sizes),'cpu')
            # Repeated integer values deliberately exercise shared maxima gradients.
            x=torch.randint(-2,3,(len(groups),7)).float().requires_grad_()
            y=x.detach().clone().requires_grad_()
            counts=torch.bincount(plain,minlength=len(sizes))
            a=_segment_amax(x,plain,len(sizes),counts)
            c=_segment_amax(y,prepared,len(sizes),counts)
            torch.testing.assert_close(a,c,rtol=0,atol=0)
            if len(groups):
                a[torch.isfinite(a)].sum().backward()
                c[torch.isfinite(c)].sum().backward()
                torch.testing.assert_close(x.grad,y.grad,rtol=0,atol=0)

if __name__=='__main__':unittest.main()
