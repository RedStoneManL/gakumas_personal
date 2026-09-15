import copy
import math
import tempfile
import unittest
from pathlib import Path
from test_joint_search import torch, DraftPolicy, example, collate, groups, records, config
from draftrl.public_mcts import Evaluation, search
from draftrl.value_distribution import mixture_best_of, quantile_loss, best_of_tensor
from draftrl.value_calibration import value_parameter, state_digest
from draftrl.checkpoint import save, load
from draftrl.ppo import update
from draftrl.soft_value_migration import validate_config, SEARCH_SETTINGS


class SoftValueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(2)

    def test_low_value_keeps_budget_high_value_receives_more(self):
        class World:
            def observe(self):return {'done':False}
            def step(self,a):return {'done':True,'score':float(a)}
        def evaluate(v):
            return Evaluation([],[],v['score'],v['score']) if v['done'] else Evaluation(list(range(8)),[.125]*8,0.)
        result=search({'done':False},World,evaluate,simulations=128,max_depth=1,
                      root_selection='soft_budget',objective_k=4,search_seed=43)
        self.assertGreaterEqual(min(result['root_visits']),2)
        self.assertGreater(result['root_visits'][7],result['root_visits'][0])
        self.assertTrue(all(p>=.25/8 for p in result['target_policy']))
        self.assertEqual(result['soft_allocation']['permanently_eliminated_actions'],0)
        self.assertTrue(result['target_budget_eligible'])

    def test_bootstrap_distribution_not_best4_twice(self):
        atoms=[0.]*24+[100.]*8
        class World:
            def observe(self):return {'depth':0}
            def step(self,a):return {'depth':1}
        def evaluate(v):return Evaluation(['a','b'],[.5,.5],25.,return_atoms=atoms)
        result=search({'depth':0},World,evaluate,simulations=16,max_depth=1,rollout_steps=0,
                      root_selection='soft_budget',objective_k=4)
        expected=100*(1-.75**4)
        for q in result['root_objective_returns']:self.assertAlmostEqual(q,expected,places=7)
        self.assertEqual(result['cost']['bootstrap_evaluations'],16)
        self.assertEqual(result['cost']['terminal_evaluations'],0)

    def test_each_simulation_equal_mass_despite_atom_count(self):
        self.assertAlmostEqual(mixture_best_of([0.,[100.]*32],4),93.75)
        self.assertAlmostEqual(mixture_best_of([0.,[100.]*32],1),50.)
        x=torch.tensor([[0.]*24+[100.]*8])
        self.assertAlmostEqual(float(best_of_tensor(x)[0]),100*(1-.75**4),places=5)

    def test_quantile_supervision_can_learn_rare_high_outcomes(self):
        logits=torch.nn.Parameter(torch.zeros(1,32))
        opt=torch.optim.Adam([logits],lr=.08)
        targets=torch.tensor([0.,0.,0.,8.])
        for _ in range(160):
            opt.zero_grad();loss=quantile_loss(logits.expand(4,-1),targets).mean();loss.backward();opt.step()
        self.assertGreater(float(best_of_tensor(logits.detach())[0]),4.)
        self.assertLess(float(logits.detach().mean()),3.)

    def test_real_process_inference_transports_quantiles_and_soft_budget(self):
        from test_joint_search import SearchService, SearchClient, make_training_entry
        model=DraftPolicy(width=32,lexical=8,quantiles=32)
        entry=make_training_entry([647]*8,turn_types=['vocal']*2)
        with SearchClient(max_worlds=2) as client:
            live=client.create_recorded_exam(entry,seed=97);history=live.export_public_history()
            task={'entry':entry,'history':history,'score_scale':150000.,'policy_version':'soft-value-test',
                  'search_seed':398,'simulations':16,'particles':4,'seconds':20.,'sampling_ms':2000,
                  'max_depth':1,'rollout_steps':0,'objective_k':4,'root_selection':'soft_budget'}
            with SearchService(model,'cpu',parallel_roots=2,inference_batch=4) as service:
                results=service.search_many([task,{**copy.deepcopy(task),'search_seed':399}])
            for r in results:
                self.assertTrue(r['valid_training_target'],r)
                self.assertEqual(r['search']['soft_allocation']['permanently_eliminated_actions'],0)
                self.assertIsNotNone(r['search']['root_value_best4'])
                self.assertGreaterEqual(min(r['search']['root_visits']),2)
            self.assertEqual(live.export_public_history(),history)
            live.close()

    def test_add_head_preserves_policy_mean_and_adam_mapping(self):
        model=DraftPolicy(width=32,lexical=8)
        opt=groups(model,dict.fromkeys(('exam','drink','draft','guidance','memory'),.0005))
        b=collate([example(i) for i in range(5)],'cpu')
        before=[t.detach().clone() for t in model(b)]
        actor=state_digest(model,lambda n:not value_parameter(n))
        model.enable_quantiles(32,opt)
        for a,v in zip(before,model(b)):torch.testing.assert_close(a,v,rtol=0,atol=0)
        self.assertEqual(actor,state_digest(model,lambda n:not value_parameter(n)))
        before_actor=state_digest(model,lambda n:not value_parameter(n))
        for n,p in model.named_parameters():p.requires_grad_(value_parameter(n))
        mean,atoms=model.value_outputs(collate([example(0)],'cpu'))
        loss=quantile_loss(atoms,torch.tensor([8.])).mean()+mean.square().mean()
        opt.zero_grad(set_to_none=True);loss.backward();opt.step()
        self.assertEqual(before_actor,state_digest(model,lambda n:not value_parameter(n)))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test.pt';save(path,model,opt)
            other,info=load(path,'cpu')
            new_opt=groups(other,dict.fromkeys(('exam','drink','draft','guidance','memory'),.0005))
            new_opt.load_state_dict(info['optimizer_state'])
            for p in new_opt.param_groups[0]['params']:
                state=new_opt.state.get(p)
                if state:self.assertEqual(state['exp_avg'].shape,p.shape)

    def test_online_quantile_loss_uses_own_terminal_return(self):
        model=DraftPolicy(width=32,lexical=8,quantiles=32)
        opt=groups(model,dict.fromkeys(('exam','drink','draft','guidance','memory'),.0005))
        rows=records(model);values=[r['return'] for r in rows]
        result=update(model,opt,rows,config(),'cpu')
        self.assertGreater(result['distribution_loss'],0.)
        self.assertEqual(values,[r['return'] for r in rows])

    def test_migration_rejects_unrelated_change(self):
        source={'search':{'simulations':32},'learning_rate':.0005}
        target=copy.deepcopy(source);target['search'].update(SEARCH_SETTINGS)
        target['value_calibration']={'quantiles':32,'objective_k':4}
        validate_config(source,target)
        target['learning_rate']=.005
        with self.assertRaises(ValueError):validate_config(source,target)

    @unittest.skip('Historical Windows supervisor; Ascend does not claim this migration path')
    def test_supervisor_requires_identical_precalibration_boundary(self):
        import json
        from continue_soft_value import audit_boundary
        from draftrl.source_identity import source_version
        old_config={'search':{'simulations':32},'learning_rate':.0005}
        new_config=copy.deepcopy(old_config);new_config['search'].update(SEARCH_SETTINGS)
        new_config['value_calibration']={'quantiles':32,'objective_k':4}
        state={'model_state':{'weight':torch.tensor([1.])},'model_config':{'width':32},'batches':9,'decisions':100,
               'next_episode_index':7,'fork_next_seed':8,'search_seed_counter':9,'arena_sha256':'a',
               'search_version':{'v':1},'setup_sha256':{},'python_rng':(1,2),'torch_rng':torch.tensor([4]),
               'cuda_rng':[],'training_config':old_config,'optimizer_state':{'state':{},'param_groups':[{'lr':.1,'params':[0]}]},
               'committed_log_offsets':{'train-episodes.jsonl':4}}
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/'old';new=Path(d)/'new';old.mkdir();new.mkdir()
            (old/'train-episodes.jsonl').write_bytes(b'abcd');(new/'train-episodes.jsonl').write_bytes(b'abcdef')
            torch.save(state,old/'latest.pt');target=copy.deepcopy(state)
            target.update(training_config=new_config,rl_source_sha256=source_version())
            torch.save(target,new/'value-boundary.pt')
            self.assertEqual(audit_boundary(old,new,new_config)['status'],'passed')
            target['model_state']['weight']+=1;torch.save(target,new/'value-boundary.pt')
            with self.assertRaisesRegex(ValueError,'model_state'):audit_boundary(old,new,new_config)


if __name__=='__main__':unittest.main()
