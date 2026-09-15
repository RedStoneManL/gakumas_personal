import copy
import itertools
import math
import unittest
import torch
from test_joint_search import DraftPolicy, example, config, groups
from draftrl.runner import choose
from draftrl.best_of import group_credit, apply_exam_credit
from draftrl.signed_credit import prepare, KIND
from draftrl.learning_settings import SIGNED, SEARCH, validate_config
from draftrl.search_learning import improve
from draftrl.public_mcts import search, Evaluation
from draftrl.ppo import update
from draftrl.kl_value_migration import SETTINGS as COMPLETION


def credit_rows(model):
    e=example(0);settings={'temperature':1.,'uniform_mix':0.,'entropy_coefficient':0.}
    actions,logs,values,settings_list,diagnostics=choose(model,[e]*4,'cpu',settings_override=[settings]*4)
    returns=[1.,2.,3.,10.];_,credits=group_credit(returns);result=[]
    for i in range(4):
        row={'encoded':e,'action':actions[i],'old_logp':logs[i],'old_value':values[i],
             'exploration':settings_list[i],'profile':'same-idol','plan':'logic','loss_kind':'ppo',
             'policy_version':'test:0','return':returns[i],**diagnostics[i]}
        row['old_return_atoms']=[0.,4.,6.,12.]*8
        apply_exam_credit([row],returns[i],credits[i],4,'prefix',i,max(returns[:i]+returns[i+1:]))
        result.append(row)
    return result


class SignedLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(2)

    def test_signed_contributions_and_own_targets(self):
        rows=credit_rows(DraftPolicy(width=32,lexical=8,quantiles=32));truths=[r['return'] for r in rows]
        result=prepare(rows,SIGNED)
        self.assertEqual([r['policy_advantage'] for r in rows],[-2.,-2.,-2.,15.])
        self.assertEqual([r['return'] for r in rows],truths)
        self.assertEqual(result['groups']['all_exam']['negative'],3)

    def test_missing_frozen_prediction_fails_before_mutating_any_credit(self):
        rows=credit_rows(DraftPolicy(width=32,lexical=8,quantiles=32))
        before=[r['policy_advantage'] for r in rows];rows[-1].pop('old_return_atoms')
        with self.assertRaises(ValueError):prepare(rows,SIGNED)
        self.assertEqual(before,[r['policy_advantage'] for r in rows])

    def test_baseline_uses_pre_action_prediction_not_observed_own_return(self):
        rows=credit_rows(DraftPolicy(width=32,lexical=8,quantiles=32));prepare(rows,SIGNED)
        self.assertEqual(rows[0]['contribution_baseline'],rows[1]['contribution_baseline'])
        self.assertNotEqual(rows[0]['return'],rows[1]['return'])

    def test_exact_best4_score_gradient_preserved_by_contribution_baseline(self):
        p=.3;original=0.;signed=0.;negative=0
        for actions in itertools.product((0,1),repeat=4):
            probability=math.prod(p if a else 1-p for a in actions)
            values=[2.*a for a in actions];_,credits=group_credit(values)
            for i,a in enumerate(actions):
                peer=max(values[:i]+values[i+1:]);baseline=p*max(2-peer,0.)
                original+=probability*(a-p)*credits[i]
                signed+=probability*(a-p)*(credits[i]-baseline)
                negative+=credits[i]-baseline<0
        expected=8*p*(1-p)**4
        self.assertAlmostEqual(original,expected);self.assertAlmostEqual(signed,expected)
        self.assertGreater(negative,0)

    def test_real_update_preserves_signed_signs_and_completes_critic(self):
        model=DraftPolicy(width=32,lexical=8,quantiles=32);rows=credit_rows(model)
        cfg=config();cfg.update(signed_exam_credit=SIGNED,critic_completion=COMPLETION)
        result=update(model,groups(model,dict.fromkeys(('exam','drink','draft','guidance','memory'),.0001)),rows,cfg,'cpu')
        counts=result['signed_credit']['groups']['all_exam']
        self.assertEqual(counts['accepted_ppo_negative'],3)
        self.assertEqual(counts['accepted_ppo_positive'],1)
        self.assertEqual(result['critic_update_coverage']['accepted_fraction'],1.)

    def test_equal_or_tiny_search_evidence_preserves_nonuniform_prior(self):
        prior=[.95,.05]
        for samples in ([[1.,1.],[1.,1.]],[[1.,1.],[1.001,1.001]]):
            target,diag=improve(prior,samples,4,SEARCH)
            self.assertEqual(target,prior);self.assertEqual(diag['weight'],0.)

    def test_repeatable_large_advantage_can_overcome_lower_prior(self):
        target,diag=improve([.9,.1],[[0.,0.,0.],[4.,4.,4.]],4,SEARCH)
        self.assertGreater(target[1],.9);self.assertGreater(diag['estimated_gain'],0.)
        self.assertEqual(diag['weight'],1.)

    def test_small_noisy_search_is_not_mislabeled_certain(self):
        _,diag=improve([.5,.5],[[0.,100.],[0.,99.]],4,SEARCH)
        self.assertEqual(diag['weight'],0.)
        self.assertTrue(all(x>0 for x in diag['simulation_standard_errors']))

    def test_simulation_mean_and_best4_do_not_get_nested_max(self):
        _,diag=improve([.5,.5],[[0.,2.],[1.,1.]],4,SEARCH)
        self.assertAlmostEqual(diag['action_values'][0],1.875)
        self.assertAlmostEqual(diag['action_values'][1],1.)

    def test_search_keeps_broad_behavior_and_distinct_learning_target(self):
        class World:
            def __init__(self):self.view={'done':False}
            def observe(self):return self.view
            def step(self,action):self.view={'done':True,'r':4.*action['a']};return self.view
        def evaluate(view):
            return Evaluation([],[],view['r'],view['r']) if view['done'] else Evaluation([{'a':0},{'a':1}],[.9,.1],0.)
        result=search({'done':False},World,evaluate,simulations=16,max_depth=2,rollout_steps=1,
                      root_selection='soft_budget',objective_k=4,learning_target=SEARCH)
        self.assertGreater(min(result['behavior_policy']),.1)
        self.assertGreater(result['target_policy'][1],.9)
        self.assertTrue(all(n>=2 for n in result['root_visits']))

    def test_migration_allows_only_the_two_learning_changes_and_pending_kl(self):
        old={'target_kl':.015,'search':{'simulations':32},'learning_rate':.0002}
        new={**copy.deepcopy(old),'target_kl':.03,'critic_completion':COMPLETION,'signed_exam_credit':SIGNED}
        new['search']['learning_target']=SEARCH
        self.assertEqual(validate_config(old,new)['target_kl'],.03)
        prior={**copy.deepcopy(old),'target_kl':.03,'critic_completion':COMPLETION}
        self.assertEqual(validate_config(prior,new)['target_kl'],.03)
        new['learning_rate']=.001
        with self.assertRaises(ValueError):validate_config(prior,new)

    def test_signed_boundary_preserves_model_adam_rng_and_rejects_weight_change(self):
        import tempfile
        from pathlib import Path
        from continue_signed_credit import audit_boundary
        from draftrl.source_identity import source_version
        old={'target_kl':.03,'critic_completion':COMPLETION,'search':{'simulations':32}}
        new=copy.deepcopy(old);new['signed_exam_credit']=SIGNED;new['search']['learning_target']=SEARCH
        state={'model_state':{'exam_quantile_head.weight':torch.tensor([1.])},'model_config':{'quantiles':32},
            'batches':14,'decisions':190584,'next_episode_index':7,'fork_next_seed':8,'search_seed_counter':9,
            'arena_sha256':'a','search_version':{'v':1},'setup_sha256':{},'python_rng':(1,2),
            'torch_rng':torch.tensor([4]),'cuda_rng':[],'training_config':old,
            'optimizer_state':{'state':{},'param_groups':[{'lr':.1,'params':[0]}]},
            'committed_log_offsets':{'train-episodes.jsonl':4}}
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'old';target=Path(d)/'new';source.mkdir();target.mkdir()
            (source/'train-episodes.jsonl').write_bytes(b'abcd');(target/'train-episodes.jsonl').write_bytes(b'abcdef')
            torch.save(state,source/'latest.pt');dest=copy.deepcopy(state)
            dest.update(training_config=new,rl_source_sha256=source_version())
            torch.save(dest,target/'kl-value-boundary.pt')
            self.assertEqual(audit_boundary(source,target,new)['status'],'passed')
            dest['model_state']['exam_quantile_head.weight']+=1;torch.save(dest,target/'kl-value-boundary.pt')
            with self.assertRaises(ValueError):audit_boundary(source,target,new)

    def test_auditor_rejects_missing_credit_and_mismatched_search_directions(self):
        import importlib.util
        from pathlib import Path
        path=Path(__file__).resolve().parents[1]/'verify_update.py'
        spec=importlib.util.spec_from_file_location('signed_auditor',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        rows=credit_rows(DraftPolicy(width=32,lexical=8,quantiles=32));credit=prepare(rows,SIGNED)
        metric={'signed_credit':credit,'phase_decisions':{'0':4},'search_records':0,
            'search_learning':{'roots':0,'weighted_roots':0,'mean_weight':0.,'mean_target_entropy':0.,
                               'mean_prior_entropy':0.,'mean_behavior_entropy':0.}}
        self.assertEqual(module.learning_problems(metric,{'signed_exam_credit':SIGNED}),[])
        metric['signed_credit']['samples'][0]['advantage']+=1
        self.assertTrue(module.learning_problems(metric,{'signed_exam_credit':SIGNED}))
        self.assertTrue(module.learning_problems({}, {'signed_exam_credit':SIGNED}))

    def test_gradient_diagnostic_uses_new_signed_credit_without_parameter_updates(self):
        from draftrl.gradient_diagnostics import inspect_gradients
        model=DraftPolicy(width=32,lexical=8,quantiles=32);rows=credit_rows(model)
        before={k:v.detach().clone() for k,v in model.state_dict().items()}
        report=inspect_gradients(model,rows,{'signed_exam_credit':SIGNED},'cpu')
        self.assertTrue(report['signed_credit']);self.assertEqual(rows[0]['policy_advantage'],-2.)
        self.assertTrue(all(torch.equal(v,model.state_dict()[k]) for k,v in before.items()))


if __name__=='__main__':unittest.main()
