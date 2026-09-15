import copy
import sys
import threading
import time
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(HERE),str(HERE/'runtime/shared'),str(HERE/'runtime/arena')]
import torch
from draftrl.model import DraftPolicy
from draftrl.encoding import collate
from draftrl.async_service import SearchService
from draftrl.search_router import SearchRouter
from draftrl.async_decisions import AsyncDecisions
from round2rl.encoding import Encoded,flatten


def example(phase=0):
    atoms=[(i,p,k,t,n) for i,node in enumerate(
        [{'turn':2},{'effect':'buff','amount':3},{'effect':'buff','amount':5}])
        for p,k,t,n in flatten(node)]
    e=Encoded(atoms,[(1,2,'next')],3,[1,2],[{'pick':1},{'pick':2}])
    e.phase=phase
    return e


class AsyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(2)

    def model(self):
        torch.manual_seed(16)
        return DraftPolicy(width=32,lexical=8)

    def test_cache_matches_forward_and_invalidates_on_policy_change(self):
        model=self.model()
        with SearchService(model,'cpu',parallel_roots=2,inference_batch=4) as service:
            def root(task):
                result=service._predict(task['encoded'],time.monotonic()+10)
                return {'valid_training_target':True,'prediction':result}
            service._root=root
            e=example()
            task={'encoded':e,'policy_version':'weights:1'}
            first=service.search_many([task])[0]['prediction']
            count=service.stats['inference_batches']
            second=service.search_many([task])[0]['prediction']
            self.assertEqual(first,second)
            self.assertEqual(service.stats['inference_batches'],count)
            self.assertGreater(service.stats['inference_cache_hits'],0)
            changed=copy.deepcopy(e)
            changed.atoms[-1]=(*changed.atoms[-1][:-1],7.)
            altered=service.search_many([{'encoded':changed,'policy_version':'weights:1'}])[0]['prediction']
            self.assertEqual(service.stats['inference_batches'],count+1)
            with torch.inference_mode():
                logits,value=model(collate([changed],'cpu'))
            torch.testing.assert_close(torch.tensor(altered[0]),logits[0].softmax(-1),atol=1e-6,rtol=1e-5)
            self.assertAlmostEqual(altered[1],float(value[0]),places=5)
            with torch.no_grad():
                next(model.parameters()).add_(.01)
            service.search_many([{'encoded':e,'policy_version':'weights:2'}])
            self.assertEqual(service.stats['inference_batches'],count+2)

    def test_cache_preserves_effect_order_phase_actions_and_signed_zero(self):
        e=example()
        baseline=SearchService.cache_key(e)
        for mutate in [
            lambda x:x.atoms.reverse(),
            lambda x:setattr(x,'phase',1),
            lambda x:x.action_entities.reverse(),
            lambda x:x.edges.append((2,1,'trigger')),
        ]:
            changed=copy.deepcopy(e);mutate(changed)
            self.assertNotEqual(baseline,SearchService.cache_key(changed))
        pos=copy.deepcopy(e);neg=copy.deepcopy(e)
        pos.atoms[-1]=(*pos.atoms[-1][:-1],0.)
        neg.atoms[-1]=(*neg.atoms[-1][:-1],-0.)
        self.assertNotEqual(SearchService.cache_key(pos),SearchService.cache_key(neg))

    def test_cache_is_bounded_and_return_values_not_aliased(self):
        model=self.model();one=SearchService.cache_key(example());two=SearchService.cache_key(example(1))
        limit=max(len(one),len(two))+160
        with SearchService(model,'cpu',inference_cache_bytes=limit) as service:
            service._put_cached(one,([.25,.75],1.))
            value=service._get_cached(one);value[0][0]=99.
            self.assertEqual(service._get_cached(one)[0],[.25,.75])
            service._put_cached(two,([.1,.9],2.))
            self.assertIsNone(service._get_cached(one))
            self.assertLessEqual(service.cache_bytes,limit)

    def test_fast_world_keeps_advancing_while_search_waits(self):
        cfg={'parallel_roots':2,'inference_batch':2,'trajectory_every':4,'simulations':16,
             'particles':4,'seconds':10,'sampling_ms':2000,'max_depth':8,'rollout_steps':8,
             'seed_base':731}
        gate=threading.Event()
        router=SearchRouter(self.model(),'cpu',cfg)
        router.service.close()
        router.service=SearchService(router.service.model,'cpu',parallel_roots=2,inference_batch=2)
        router.service._root=lambda task: (
            gate.wait(5) or None,
            {'valid_training_target':False,'status':'deadline','elapsed_seconds':.1}
        )[1]
        obs={'decision_version':1}
        class Pool:
            def public_history(self,worker):
                self.last_worker=worker
                return {'initial':{'observation':obs},'steps':[]}
        pool=Pool();e=example()
        def item(i,enabled):
            return {'worker':i,'encoded':e,'enabled':enabled,'entry':{},'observation':obs,
                    'profile':'same','score_scale':1.,'episode_id':str(i),'partial_selection':[]}
        def proposal(i):
            return (i,e,1,-.75,2.,{}, {})
        flow=AsyncDecisions(router)
        try:
            ready=flow.submit(pool,[item(0,True),item(1,False)],
                              [proposal(0),proposal(1)],'weights:1')
            self.assertEqual([p[0] for p in ready],[1])
            self.assertEqual(set(flow.pending),{0})
            ready=flow.submit(pool,[item(1,False)],[proposal(1)],'weights:1')
            self.assertEqual([p[0] for p in ready],[1])
            with self.assertRaises(ValueError):
                router.service.submit([{'policy_version':'weights:2'}])
            self.assertFalse(gate.is_set())
            gate.set()
            ready=[]
            until=time.monotonic()+5
            while not ready and time.monotonic()<until:
                ready=flow.poll(wait=True)
            self.assertEqual(len(ready),1)
            self.assertEqual(ready[0][0],0)
            self.assertEqual(ready[0][3],-.75)  # Rejected search keeps actual PPO probability.
            self.assertEqual(ready[0][-1]['loss_kind'],'ppo')
            self.assertEqual(ready[0][-1]['search_fallback_reason'],'deadline')
            flow.assert_drained()
        finally:
            gate.set();router.close()


if __name__=='__main__':unittest.main()
