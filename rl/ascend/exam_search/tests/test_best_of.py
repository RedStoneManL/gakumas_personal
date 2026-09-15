import copy
import itertools
import math
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
HERE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(HERE),str(HERE/'runtime/shared'),str(HERE/'runtime/arena')]
from draftrl.best_of import group_credit,empirical_best,fixed_play_summary,comparison
from draftrl.practice import apply_fork_returns,profile_weights
from draftrl.advantages import estimate


class BestOfTests(unittest.TestCase):
    def test_risky_deck_preferred_and_original_outcomes_retained(self):
        values=[2.,2.,2.,30.]
        parent={'seed':100,'profile':'test','policy_version':'x','normalized_score':values[0],
                'action_rng_seed':200,'score':2,'entry_sha256':'same','score_scale':1}
        branches=[{**parent,'seed':100+i,'action_rng_seed':200+i,'prefix_id':'joint:100',
                   'branch_id':i,'fork_replicas':4,'score':values[i],'normalized_score':values[i]}
                  for i in range(1,4)]
        def record(phase,branch):
            return {'encoded':SimpleNamespace(phase=phase,submissions=[0,1]),'episode_id':'joint:100',
                    'prefix_id':'joint:100','branch_id':branch,'return':values[branch],
                    'old_value':1.,'profile':'test'}
        rows=[record(2,0),record(0,0)]
        forks=[record(0,i) for i in range(1,4)]
        result=apply_fork_returns(rows,[parent],forks,branches,objective='best_of_k')
        self.assertEqual(rows[0]['return'],30)
        self.assertEqual([r['return'] for r in rows[1:]],values)
        advantages,targets=estimate(rows)
        self.assertEqual(advantages[1:],[0.,0.,0.,112.])
        self.assertEqual(result[0]['construction_target'],30.)
        self.assertEqual(result[0]['mean'],9.)
        self.assertEqual(targets[1:],values)
        import torch
        advantages=torch.tensor(advantages)
        profile_weights(advantages,rows,torch.ones(len(rows),dtype=torch.bool))
        self.assertEqual(advantages[1:4].tolist(),[0.,0.,0.])
        self.assertGreater(advantages[-1],0.)

    def test_leave_one_out_score_gradient_matches_exact_best4_derivative(self):
        # A Bernoulli policy, with independent environmental coin after success.
        # Exact E[max of 4] = 30*(1-p*0.2)^0 - 30*(1-p*0.2)^4.
        p=.37;q=.2;k=4
        estimated=0.
        for draws in itertools.product(((0,0),(0,1),(1,0),(1,1)),repeat=k):
            probability=math.prod((p if a else 1-p)*(q if luck else 1-q) for a,luck in draws)
            values=[30.*a*luck for a,luck in draws]
            _,credits=group_credit(values)
            estimated+=probability*sum((a/p-(1-a)/(1-p))*c for (a,_),c in zip(draws,credits))
        exact=30*k*q*(1-p*q)**(k-1)
        self.assertAlmostEqual(estimated,exact,places=10)

    def test_search_utility_is_best4_not_mean_or_unlimited_max(self):
        scores=[2.,2.,2.,30.]
        value=empirical_best(scores,4)
        self.assertAlmostEqual(value,2.+28*(1-.75**4))
        self.assertGreater(value,empirical_best([10.]*4,4))
        self.assertLess(value,30.)
        self.assertEqual(empirical_best(scores,1),9.)
        self.assertEqual(group_credit([10.]*4),(10.,[0.]*4))

    def test_missing_fourth_result_rejected_without_mutation(self):
        parent={'seed':1,'profile':'x','policy_version':'a','normalized_score':1.}
        branches=[{**parent,'prefix_id':'joint:1','branch_id':i,'fork_replicas':4} for i in (1,2)]
        rows=[{'encoded':SimpleNamespace(phase=2),'episode_id':'joint:1','return':1.}]
        before=copy.deepcopy(rows)
        with self.assertRaises(ValueError):apply_fork_returns(rows,[parent],[],branches,objective='best_of_k')
        self.assertEqual(rows,before)

    def test_fixed_validation_uses_two_groups_of_four_not_max_of_eight(self):
        rows=[{'play_loadout_id':1,'seed':i,'profile':'x','entry_sha256':'x','score_scale':1,
               'score':score,'normalized_score':score} for i,score in enumerate([1,1,1,5,2,2,2,9])]
        result=fixed_play_summary(rows)
        self.assertEqual(result['groups'],2)
        self.assertEqual(result['profiles']['x']['best_of_k'],7.)
        reordered=copy.deepcopy(result)
        reordered['group_results'].reverse()
        self.assertEqual(comparison(result,reordered),1.)

if __name__=='__main__':unittest.main()
