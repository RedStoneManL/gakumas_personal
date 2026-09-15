import copy
import random
import unittest
import torch
from test_joint_search import DraftPolicy, groups, config, records
from draftrl.ppo import update
from draftrl.critic_completion import complete_values, value_parameter, SETTINGS
from draftrl.kl_value_migration import validate_config
from draftrl.value_calibration import state_digest


class CriticCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): torch.set_num_threads(2)

    def setUp(self):
        torch.manual_seed(42); random.seed(43)

    def test_early_stop_completes_values_without_changing_actor_or_actor_adam(self):
        original = DraftPolicy(width=32, lexical=8, quantiles=32)
        data = records(original)*16
        cfg = config(); cfg.update(target_kl=.0001, effective_minibatch=4)
        baseline, completed = copy.deepcopy(original), copy.deepcopy(original)
        optimizers = [groups(m, dict.fromkeys(('exam','drink','draft','guidance','memory'), .001))
                      for m in (baseline, completed)]
        random.seed(43)
        first = update(baseline, optimizers[0], data, cfg, 'cpu')
        random.seed(43)
        second = update(completed, optimizers[1], data,
                        {**cfg, 'critic_completion': SETTINGS}, 'cpu')
        self.assertTrue(first['kl_early_stop'])
        self.assertLess(first['update_coverage']['accepted_fraction'], 1.)
        self.assertEqual(first['update_coverage'], second['update_coverage'])
        self.assertEqual(first['optimizer_steps'], second['optimizer_steps'])
        self.assertEqual(second['critic_update_coverage']['accepted_fraction'], 1.)
        self.assertGreater(second['critic_completion']['optimizer_steps'], 0)
        self.assertEqual(second['critic_completion']['completed_records'],
                         len(data)-first['update_coverage']['accepted_unique'])
        self.assertEqual(state_digest(baseline, lambda n:not value_parameter(n)),
                         state_digest(completed, lambda n:not value_parameter(n)))
        self.assertFalse(torch.equal(baseline.exam_quantile_head.weight,
                                     completed.exam_quantile_head.weight))
        for (name, a), (_, b) in zip(baseline.named_parameters(), completed.named_parameters()):
            if value_parameter(name): continue
            sa, sb = optimizers[0].state.get(a, {}), optimizers[1].state.get(b, {})
            self.assertEqual(sa.keys(), sb.keys())
            for key in sa:
                if isinstance(sa[key], torch.Tensor): self.assertTrue(torch.equal(sa[key], sb[key]))
                else: self.assertEqual(sa[key], sb[key])

    def test_no_extra_pass_when_joint_update_already_covers_all_records(self):
        model=DraftPolicy(width=32, lexical=8, quantiles=32)
        opt=groups(model, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0001))
        result=update(model, opt, records(model), {**config(), 'critic_completion':SETTINGS}, 'cpu')
        self.assertEqual(result['update_coverage']['accepted_fraction'], 1.)
        self.assertEqual(result['critic_completion']['optimizer_steps'], 0)
        self.assertEqual(result['critic_completion']['completed_records'], 0)

    def test_only_unaccepted_records_are_used_and_targets_remain_real(self):
        model=DraftPolicy(width=32, lexical=8, quantiles=32)
        opt=groups(model, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0005))
        data=records(model); truth=torch.tensor([r['return'] for r in data])
        used=[]; original=model.value_outputs
        def capture(batch):
            used.extend(batch['phase'].tolist()); return original(batch)
        model.value_outputs=capture
        result=complete_values(model,opt,data,truth,torch.ones(4),{0,1},{0,1},list(range(4)),
                               {**config(),'critic_completion':SETTINGS},'cpu')
        self.assertEqual(used,[0,0])
        self.assertEqual(result['completed_records'],2)
        self.assertEqual(truth.tolist(),[r['return'] for r in data])
        self.assertTrue(all(p.requires_grad for p in model.parameters()))

    def test_completion_restores_flags_on_bad_target_without_actor_update(self):
        model=DraftPolicy(width=32, lexical=8, quantiles=32)
        opt=groups(model, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0005))
        data=records(model); before=state_digest(model,lambda n:not value_parameter(n))
        with self.assertRaises(FloatingPointError):
            complete_values(model,opt,data,torch.full((4,),float('nan')),torch.ones(4),set(),set(),
                            list(range(4)),{**config(),'critic_completion':SETTINGS},'cpu')
        self.assertEqual(before,state_digest(model,lambda n:not value_parameter(n)))
        self.assertTrue(all(p.requires_grad for p in model.parameters()))

    def test_migration_only_doubles_kl_and_enables_completion(self):
        old={'target_kl':.015,'clip':.2,'search':{'soft_floor':.25}}
        new={**copy.deepcopy(old),'target_kl':.03,'critic_completion':SETTINGS}
        self.assertEqual(validate_config(old,new)['block_stop_kl'],.06)
        for key,value in [('clip',.4),('target_kl',.1)]:
            bad=copy.deepcopy(new);bad[key]=value
            with self.assertRaises(ValueError):validate_config(old,bad)

    def test_auditor_requires_real_full_value_coverage_and_preserves_old_failure(self):
        import importlib.util
        from pathlib import Path
        path=Path(__file__).resolve().parents[1]/'verify_update.py'
        spec=importlib.util.spec_from_file_location('value_audit_test',path)
        auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
        joint={'record_count':10,'accepted_unique':2,'accepted_fraction':.2}
        coverage={'record_count':10,'accepted_unique':10,'accepted_fraction':1.,
                  'groups':{'phase:exam':{'accepted_fraction':1.}}}
        metric={'update_coverage':joint,'critic_update_coverage':coverage,'kl_early_stop':True,
                'ppo_stop_reason':'block_kl','critic_completion':{'coverage':coverage,
                'completed_records':8,'optimizer_steps':2,'actor_unchanged':True,'policy_replay':False,
                'actor_sha256_before':'a'*64,'actor_sha256_after':'a'*64}}
        self.assertTrue(auditor.coverage_problems(metric,{}))
        self.assertEqual(auditor.coverage_problems(metric,{'critic_completion':SETTINGS}),[])
        metric['critic_completion']['actor_unchanged']=False
        self.assertTrue(auditor.coverage_problems(metric,{'critic_completion':SETTINGS}))

    def test_new_supervisor_preserves_the_existing_quantile_model_boundary(self):
        import tempfile
        from pathlib import Path
        from continue_kl_value import audit_boundary
        from draftrl.source_identity import source_version
        old_config={'target_kl':.015,'search':{'simulations':32}}
        new_config={**copy.deepcopy(old_config),'target_kl':.03,'critic_completion':SETTINGS}
        state={'model_state':{'exam_quantile_head.weight':torch.tensor([1.])},'model_config':{'quantiles':32},
               'batches':13,'decisions':176185,'next_episode_index':7,'fork_next_seed':8,
               'search_seed_counter':9,'arena_sha256':'a','search_version':{'v':1},'setup_sha256':{},
               'python_rng':(1,2),'torch_rng':torch.tensor([4]),'cuda_rng':[],
               'training_config':old_config,'optimizer_state':{'state':{},'param_groups':[{'lr':.1,'params':[0]}]},
               'committed_log_offsets':{'train-episodes.jsonl':4}}
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/'old';new=Path(d)/'new';old.mkdir();new.mkdir()
            (old/'train-episodes.jsonl').write_bytes(b'abcd');(new/'train-episodes.jsonl').write_bytes(b'abcdef')
            torch.save(state,old/'latest.pt');target=copy.deepcopy(state)
            target.update(training_config=new_config,rl_source_sha256=source_version())
            torch.save(target,new/'kl-value-boundary.pt')
            self.assertEqual(audit_boundary(old,new,new_config)['status'],'passed')
            target['model_state']['exam_quantile_head.weight']+=1
            torch.save(target,new/'kl-value-boundary.pt')
            with self.assertRaisesRegex(ValueError,'model_state'):audit_boundary(old,new,new_config)


if __name__=='__main__': unittest.main()
