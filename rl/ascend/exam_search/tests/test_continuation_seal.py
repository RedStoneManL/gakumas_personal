"""Exercise a versioned continuation and crash recovery using real tiny updates."""
import copy
import importlib.util
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from test_joint_search import DraftPolicy, config, groups, records, torch, update
from draftrl import continuation, recovery
from draftrl.checkpoint import digest, json_write, save_committed, source_version
from gakumas_arena.engine.search import search_content_version
from draftrl.exploration_migration import make_decision_config
from draftrl.distribution import schedule


class ContinuationSealTests(unittest.TestCase):
    def test_new_revision_survives_failure_before_first_new_update(self):
        self.exercise_continuation(extend_timeout=False)

    def test_authorized_timeout_extension_preserves_real_adam_rng_and_recovery(self):
        self.exercise_continuation(extend_timeout=True)

    def test_decision_schedule_preserves_actual_update_rng_and_recovery(self):
        self.exercise_continuation(extend_timeout=False, decision_schedule=True)

    def test_ultra_and_decision_schedule_preserve_model_adam_rng(self):
        self.exercise_continuation(extend_timeout=False, decision_schedule=True, ultra=True)

    def exercise_continuation(self, extend_timeout, decision_schedule=False, ultra=False):
        torch.set_num_threads(2)
        torch.manual_seed(331)
        random.seed(331)
        model = DraftPolicy(width=32, lexical=8)
        optimizer = groups(model, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0001))
        cfg = config()
        cfg['search'].update(sampling_ms=2000,seconds=60,simulations=32,particles=8)
        start = datetime.now(timezone.utc) - timedelta(minutes=30)
        deadline = start + timedelta(minutes=180)
        cfg.update(max_minutes=180, absolute_deadline=deadline.isoformat())
        snapshot = None
        if decision_schedule:
            from test_decision_exploration import source_config
            exploration = source_config()
            cfg.update({key:exploration[key] for key in ('exploration','exploration_schedule')})
            snapshot=schedule(cfg,4,elapsed_minutes=30)
        target_cfg = copy.deepcopy(cfg)
        if extend_timeout:
            target_cfg['search'].update(sampling_ms=10000,native_action_budget=60000)
        if decision_schedule:
            target_cfg=make_decision_config(cfg,4,snapshot,200000)
        if ultra:target_cfg['resource_mode']='ultra'
        update(model, optimizer, records(model), cfg, 'cpu')
        with tempfile.TemporaryDirectory(prefix='arena-continuation-seal-') as temporary:
            root = Path(temporary)
            setup = root/'setup'; setup.mkdir()
            source = root/'source'; source.mkdir()
            target = root/'target'
            json_write(setup/'profiles.json', {'fixture': 'synthetic tiny training'})
            progress = {'status':'complete','trainer_pid':None,'started_at':start.isoformat(),
                        'batches':1,'decisions':4}
            if decision_schedule:progress['active_exploration']=snapshot
            json_write(source/'progress.json', progress)
            json_write(source/'manifest.json', {'rl_source_sha256':'previous-test-revision'})
            json_write(source/'validation-initial.json', {'fixture':True})
            for name in ('metrics.jsonl','validation-history.jsonl','monitor-history.jsonl'):
                (source/name).write_text(json.dumps({'batch':1,'decisions':4})+'\n',encoding='utf8')
            meta = dict(training_config=cfg, arena_sha256='test-arena',
                search_version=search_content_version(), setup_sha256={'profiles.json':digest(setup/'profiles.json')},
                batches=1, decisions=4, next_episode_index=123, fork_next_seed=1600000020,
                search_seed_counter=7, run_progress=progress,
                rl_source_sha256='previous-test-revision')
            save_committed(source/'best.pt', model, optimizer, **meta)
            save_committed(source/'latest.pt', model, optimizer, **meta)
            shutil.copy2(source/'latest.pt', source/'initial.pt')
            source_digest = digest(source/'latest.pt')
            moved, info, context = continuation.prepare(source,target,setup,target_cfg,'test-arena','cpu')
            moved_optimizer = groups(moved, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0001))
            moved_optimizer.load_state_dict(info['optimizer_state'])
            continuation.commit_recovery(target,info,context)
            recovery.restore_random(info)
            new_meta = {**meta, 'training_config':target_cfg, 'run_progress':{**progress,'status':'running'}}
            new_meta.pop('rl_source_sha256')
            # Same atomic operation used by runner before a continuation rollout.
            save_committed(target/'latest.pt',moved,moved_optimizer,**new_meta)
            with (target/'metrics.jsonl').open('a',encoding='utf8') as stream:
                stream.write('{"uncommitted":true}\n')
            recovered, sealed, recovered_context = recovery.prepare(target,setup,target_cfg,'test-arena','cpu')
            audit = recovery.commit_recovery(target,sealed,recovered_context)
            self.assertEqual(digest(source/'latest.pt'),source_digest)
            self.assertEqual(sealed['rl_source_sha256'],source_version())
            self.assertEqual(sealed['search_seed_counter'],7)
            self.assertEqual(sealed['fork_next_seed'],1600000020)
            self.assertEqual(sealed['training_config']['absolute_deadline'],deadline.isoformat())
            self.assertEqual(json.loads((target/'training-window.json').read_text())['absolute_deadline'],deadline.isoformat())
            self.assertTrue((target/sealed['committed_best']['path']).is_file())
            self.assertIn('metrics.jsonl',audit['archived_uncommitted_bytes'])
            spec=importlib.util.spec_from_file_location('best4_boundary_audit',Path(__file__).resolve().parents[1]/'continue_run.py')
            supervisor=importlib.util.module_from_spec(spec);spec.loader.exec_module(supervisor)
            self.assertFalse((target/'monitor-history.jsonl').exists())
            boundary=supervisor.audit_boundary(source,target,sealed,target_cfg)
            self.assertTrue(boundary['model_adam_rng_identical'])
            self.assertEqual(bool(boundary['search_budget_change']),extend_timeout)
            if decision_schedule:
                self.assertTrue(boundary['exploration_change']['continuous_at_boundary'])
                self.assertEqual(schedule(sealed['training_config'],sealed['decisions'],elapsed_minutes=99999),snapshot)
            self.assertIn('monitor-history.jsonl',boundary['omitted_monitoring_history'])
            self.assertIn('metrics.jsonl',boundary['committed_log_prefixes'])
            learning_log=target/'metrics.jsonl'
            original_log=learning_log.read_bytes()
            learning_log.write_bytes(b'!'+original_log[1:])
            with self.assertRaisesRegex(ValueError,'committed history metrics.jsonl'):
                supervisor.audit_boundary(source,target,sealed,target_cfg)
            learning_log.write_bytes(original_log)
            altered=copy.deepcopy(sealed);altered['fork_next_seed']+=1
            with self.assertRaisesRegex(ValueError,'fork_next_seed'):
                supervisor.audit_boundary(source,target,altered,target_cfg)
            reoptimizer = groups(recovered,dict.fromkeys(('exam','drink','draft','guidance','memory'),.0001))
            reoptimizer.load_state_dict(sealed['optimizer_state'])
            rows = records(model)
            recovery.restore_random(info)
            update(model,optimizer,copy.deepcopy(rows),cfg,'cpu')
            recovery.restore_random(sealed)
            update(recovered,reoptimizer,copy.deepcopy(rows),target_cfg,'cpu')
            for name, value in model.state_dict().items():
                torch.testing.assert_close(value,recovered.state_dict()[name],atol=0,rtol=0)


if __name__ == '__main__':
    unittest.main()
