import copy
import random
import unittest
from test_joint_search import DraftPolicy,SearchService,SearchClient,make_training_entry,torch
from draftrl.public_mcts import Evaluation,search


class BestOfSearchTests(unittest.TestCase):
    def test_tail_objective_can_prefer_risky_action_over_higher_mean(self):
        def run(k):
            rng=random.Random(442)
            class World:
                def __init__(self):self.hit=rng.random()<.2
                def observe(self):return {'terminal':False}
                def step(self,action):return {'terminal':True,'score':30.*self.hit if action=='risky' else 10.}
            def evaluate(view):
                if view['terminal']:return Evaluation([],[],view['score'],view['score'])
                return Evaluation(['safe','risky'],[.5,.5],10.)
            return search({'terminal':False},World,evaluate,simulations=1000,max_depth=1,
                          rollout_steps=0,root_selection='puct',search_seed=315,objective_k=k)
        mean=run(1);tail=run(4)
        self.assertEqual(mean['selected_action'],'safe')
        self.assertEqual(tail['selected_action'],'risky')
        self.assertLess(tail['root_mean_returns'][1],10.)
        self.assertGreater(tail['root_objective_returns'][1],10.)

    def test_real_arena_roots_keep_best4_objective_and_recorder_isolation(self):
        torch.set_num_threads(2)
        model=DraftPolicy(width=32,lexical=8)
        entry=make_training_entry([647]*8,turn_types=['vocal']*2)
        with SearchClient(max_worlds=2) as client:
            live=client.create_recorded_exam(entry,seed=89)
            history=live.export_public_history()
            task={'entry':entry,'history':history,'score_scale':150000.,'policy_version':'best4-test',
                  'search_seed':391,'simulations':16,'particles':4,'seconds':15.,'sampling_ms':2000,
                  'max_depth':8,'rollout_steps':8,'objective_k':4}
            with SearchService(model,'cpu',parallel_roots=2,inference_batch=4) as service:
                results=service.search_many([task,{**copy.deepcopy(task),'search_seed':392}])
            self.assertTrue(all(r['valid_training_target'] for r in results),results)
            self.assertTrue(all(r['objective_k']==r['search']['objective_k']==4 for r in results))
            self.assertTrue(all(r['search']['cost']['terminal_evaluations']>0 for r in results))
            self.assertEqual(live.export_public_history(),history)
            live.close()

if __name__=='__main__':unittest.main()
