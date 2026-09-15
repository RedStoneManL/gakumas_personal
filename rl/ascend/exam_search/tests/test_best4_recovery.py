"""Best-of-4 crash boundaries and the narrowly authorized config transition."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from test_joint_search import DraftPolicy, config, groups, torch
from draftrl import recovery
from draftrl.checkpoint import digest, json_write, save_committed, source_version
from gakumas_arena.engine.search import search_content_version

HERE=Path(__file__).resolve().parents[1]


class Best4RecoveryTests(unittest.TestCase):
    def fixture(self, root, with_best):
        output=root/'run';output.mkdir()
        setup=root/'setup';setup.mkdir()
        json_write(setup/'profiles.json',{'test':True})
        cfg=config()
        cfg['practice']={'forks':{'replicas':4,'objective':'best_of_k','exam_credit':'leave_one_out_max'}}
        model=DraftPolicy(width=32,lexical=8)
        optimizer=groups(model,dict.fromkeys(('exam','drink','draft','guidance','memory'),.0005))
        progress={'batches':1,'decisions':4,'status':'running'}
        json_write(output/'manifest.json',{'rl_source_sha256':source_version()})
        json_write(output/'progress.json',progress)
        meta=dict(training_config=cfg,arena_sha256='test',search_version=search_content_version(),
                  setup_sha256={'profiles.json':digest(setup/'profiles.json')},batches=1,decisions=4,
                  next_episode_index=123,search_seed_counter=17,run_progress=progress)
        save_committed(output/'best.pt',model,optimizer,**meta)
        if with_best:
            json_write(output/'best4-reference.json',{'baseline':'fixed'})
            save_committed(output/'best4.pt',model,optimizer,**meta)
            (output/'best4-validation-history.jsonl').write_text('{"batch":1}\n',encoding='utf8')
        save_committed(output/'latest.pt',model,optimizer,**meta)
        return output,setup,cfg,model,optimizer,meta

    def test_restore_best4_and_archive_uncommitted_history(self):
        torch.set_num_threads(2)
        with tempfile.TemporaryDirectory(prefix='arena-best4-recovery-') as directory:
            output,setup,cfg,model,optimizer,meta=self.fixture(Path(directory),True)
            original=digest(output/'best4.pt')
            with torch.no_grad():next(model.parameters()).add_(1)
            save_committed(output/'best4.pt',model,optimizer,**{**meta,'batches':2})
            with (output/'best4-validation-history.jsonl').open('a',encoding='utf8') as stream:
                stream.write('{"batch":2}\n')
            _,info,context=recovery.prepare(output,setup,cfg,'test','cpu')
            self.assertNotEqual(digest(output/'best4.pt'),original)
            audit=recovery.commit_recovery(output,info,context)
            self.assertEqual(digest(output/'best4.pt'),original)
            self.assertEqual(digest(output/info['committed_best4']['path']),original)
            self.assertEqual((output/'best4-validation-history.jsonl').read_text(),'{"batch":1}\n')
            self.assertIn('best4-validation-history.jsonl',audit['archived_uncommitted_bytes'])
            self.assertEqual(json.loads((output/'best4-reference.json').read_text()),{'baseline':'fixed'})

    def test_uncommitted_first_baseline_must_be_rebuilt(self):
        with tempfile.TemporaryDirectory(prefix='arena-best4-baseline-') as directory:
            output,setup,cfg,model,optimizer,meta=self.fixture(Path(directory),False)
            json_write(output/'best4-reference.json',{'unfinished':True})
            save_committed(output/'best4.pt',model,optimizer,**meta)
            _,info,context=recovery.prepare(output,setup,cfg,'test','cpu')
            self.assertIsNone(info['committed_best4'])
            audit=recovery.commit_recovery(output,info,context)
            self.assertFalse((output/'best4-reference.json').exists())
            self.assertFalse((output/'best4.pt').exists())
            self.assertTrue((Path(audit['evidence_backup'])/'best4-reference.json.uncommitted').exists())

    def test_corrupt_immutable_best4_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='arena-best4-corrupt-') as directory:
            output,setup,cfg,_,_,_=self.fixture(Path(directory),True)
            _,info,_=recovery.prepare(output,setup,cfg,'test','cpu')
            (output/info['committed_best4']['path']).write_bytes(b'broken-test-fixture')
            with self.assertRaisesRegex(ValueError,'Best-of-4 snapshot differs'):
                recovery.prepare(output,setup,cfg,'test','cpu')

    def test_transition_rejects_unrelated_parameter_changes(self):
        spec=importlib.util.spec_from_file_location('best4_supervisor',HERE/'continue_run.py')
        supervisor=importlib.util.module_from_spec(spec);spec.loader.exec_module(supervisor)
        source={'practice':{'forks':{'replicas':4,'objective':'best_of_k','exam_credit':'leave_one_out_max'}},'learning_rate':.0005,'absolute_deadline':'fixed'}
        candidate=copy.deepcopy(source)
        supervisor.validate_config(source,candidate)
        for key,value in (('learning_rate',.001),('absolute_deadline','later')):
            changed=copy.deepcopy(candidate);changed[key]=value
            with self.assertRaises(ValueError):supervisor.validate_config(source,changed)
        for key,value in (('replicas',2),('objective','mean'),('exam_credit','individual')):
            changed=copy.deepcopy(candidate);changed['practice']['forks'][key]=value
            with self.assertRaises(ValueError):supervisor.validate_config(source,changed)


if __name__=='__main__':unittest.main()
