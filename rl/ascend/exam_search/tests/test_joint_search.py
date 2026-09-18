import copy
import random
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(HERE/'runtime/shared'), str(HERE/'runtime/arena')]

import torch
from draftrl.legacy_model import DraftPolicy as LegacyPolicy
from draftrl.model import DraftPolicy, MODEL_SCHEMA
from draftrl.migration import migrate, migrate_adam, groups
from draftrl.encoding import collate
from draftrl.distribution import distributions
from draftrl.ppo import update
from draftrl.checkpoint import save, load
from draftrl.search_service import SearchService
from round2rl.encoding import Encoded, flatten
from gakumas_arena.engine.search import SearchClient
from gakumas_arena.engine.training import make_training_entry


def example(phase):
    nodes = [{'phase': phase, 'turns': 9}, {'effect': 'buff', 'amount': 5}, {'effect': 'score', 'amount': 10}]
    atoms = [(i, path, kind, text, number) for i, node in enumerate(nodes)
             for path, kind, text, number in flatten(node)]
    e = Encoded(atoms, [(1, 2, 'target')], 3, [1, 2], [{'pick': 1}, {'pick': 2}])
    e.phase = phase
    return e


def config():
    return {'_policy_version': 'test:0', 'sample_efficiency': {'advantage_mode': 'mc', 'ppo_epochs_max': 1},
            'search': {'loss_coefficient': .1}, 'practice': {}, 'epochs': 1, 'effective_minibatch': 4,
            'minibatch': 2, 'clip': .2, 'target_kl': .05, 'value_coefficient': .5, 'max_grad': .5}


def records(model):
    out = []
    settings = {'temperature': 1.2, 'uniform_mix': .1, 'entropy_coefficient': .01}
    for phase, action, target, kind in [(2, 0, 2., 'ppo'), (2, 1, 1., 'ppo'),
                                        (0, 1, 2., 'search'), (0, 0, .5, 'ppo')]:
        e = example(phase)
        with torch.no_grad():
            batch = collate([e], 'cpu')
            logits, values = model(batch)
            dist, _ = distributions(logits, batch['mask'], [settings])
            old = float(dist.log_prob(torch.tensor([action]))[0])
        row = {'encoded': e, 'action': action, 'old_logp': old if kind=='ppo' else None,
               'old_value': float(values[0]), 'return': target, 'profile': 'same-idol',
               'loss_kind': kind, 'exploration': settings, 'policy_version': 'test:0'}
        if kind == 'search':
            row['search'] = {'actions': copy.deepcopy(e.submissions), 'target_policy': [.1, .9],
                             'target_budget_eligible': True, 'root_action_coverage': 1.}
        out.append(row)
    return out


class JointSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        torch.manual_seed(271)

    def test_function_and_adam_migrate_without_aliasing(self):
        legacy = LegacyPolicy()
        optimizer = groups(legacy, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0005))
        b = collate([example(i) for i in range(5)], 'cpu')
        logits, values = legacy(b)
        (logits.square().mean()+values.square().mean()).backward()
        optimizer.step()
        info = {'model_schema': 'hif-memory-draft-drink-exam-policy/1', 'model_config': legacy.config,
                'model_state': legacy.state_dict(), 'optimizer_state': optimizer.state_dict()}
        new = migrate(info)
        target = groups(new, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0005))
        result = migrate_adam(info, new, target)
        self.assertGreater(result['copied_parameter_tensors'], 0)
        self.assertGreater(result['fresh_parameter_tensors'], 0)
        for left, right in zip(legacy(b), new(b)):
            torch.testing.assert_close(left, right, atol=1e-6, rtol=1e-5)
        params = dict(new.named_parameters())
        p, q = [params[f'actor.towers.{kind}.update.0.0.weight'] for kind in ('exam','build')]
        torch.testing.assert_close(target.state[p]['exp_avg'], target.state[q]['exp_avg'])
        self.assertNotEqual(target.state[p]['exp_avg'].data_ptr(), target.state[q]['exp_avg'].data_ptr())
        self.assertNotIn(params['actor.towers.exam.update.3.0.weight'], target.state)

    def test_joint_update_uses_search_distribution_without_fake_logp(self):
        model = DraftPolicy()
        optimizer = groups(model, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0001))
        rows = records(model)
        before_build = model.draft_policy_head[-1].weight.detach().clone()
        before_exam = model.policy_head[-1].weight.detach().clone()
        result = update(model, optimizer, rows, config(), 'cpu')
        self.assertEqual(result['search_records'], 1)
        self.assertEqual(result['ppo_records'], 3)
        self.assertFalse(torch.equal(before_build, model.draft_policy_head[-1].weight))
        self.assertFalse(torch.equal(before_exam, model.policy_head[-1].weight))
        self.assertEqual(result['update_coverage']['groups']['loss:search']['accepted_fraction'], 1.)

    def test_save_restore_next_update_matches(self):
        model = DraftPolicy()
        optimizer = groups(model, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0001))
        update(model, optimizer, records(model), config(), 'cpu')
        with tempfile.TemporaryDirectory(prefix='arena-joint-test-') as temporary:
            path = Path(temporary)/'roundtrip.pt'
            save(path, model, optimizer, batches=1)
            restored, info = load(path, 'cpu')
            self.assertEqual(info['model_schema'], MODEL_SCHEMA)
            reoptimizer = groups(restored, dict.fromkeys(('exam','drink','draft','guidance','memory'), .0001))
            reoptimizer.load_state_dict(info['optimizer_state'])
            rows = records(model)
            random.seed(123)
            update(model, optimizer, rows, config(), 'cpu')
            random.seed(123)
            update(restored, reoptimizer, rows, config(), 'cpu')
            for key, value in model.state_dict().items():
                torch.testing.assert_close(value, restored.state_dict()[key], atol=0, rtol=0)

    def test_parallel_search_reaches_real_terminal_and_preserves_recorder(self):
        model = DraftPolicy(width=32, lexical=8)
        entry = make_training_entry([647]*8, turn_types=['vocal']*2)
        with SearchClient(max_worlds=2) as recording:
            live = recording.create_recorded_exam(entry, seed=31)
            history = live.export_public_history()
            tasks = [{'entry': entry, 'history': history, 'score_scale': 150000.,
                      'policy_version': 'test:0', 'search_seed': 731+i,
                      'simulations': 16, 'particles': 4, 'seconds': 15., 'sampling_ms': 2000,
                      'max_depth': 8, 'rollout_steps': 8} for i in range(2)]
            with SearchService(model, 'cpu', parallel_roots=2, inference_batch=4) as service:
                results = service.search_many(tasks)
                self.assertTrue(all(r['valid_training_target'] for r in results), results)
                self.assertGreater(sum(r['search']['cost']['terminal_evaluations'] for r in results), 0)
                self.assertLess(service.stats['inference_batches'], service.stats['inference_examples'])
            self.assertEqual(live.export_public_history(), history)
            live.close()


class RecoveryTests(unittest.TestCase):
    def test_lexical_cache_matches_fresh_inference_and_bypasses_gradients(self):
        model=DraftPolicy(width=32,lexical=8)
        batches=[collate([example(p)],'cpu') for p in range(5)]
        with torch.inference_mode():
            expected=[model(batch) for batch in batches]
            model.actor._search_lex_cache={};model.critic._search_lex_cache={}
            for batch,reference in zip(batches,expected):
                actual=model(batch)
                for a,b in zip(actual,reference):torch.testing.assert_close(a,b,atol=1e-6,rtol=1e-5)
            self.assertGreater(len(model.actor._search_lex_cache),0)
        # Detached inference tensors must never be used by a gradient update.
        logits,value=model(batches[0])
        (logits[0,0]+value.sum()).backward()
        self.assertIsNotNone(model.actor.byte.weight.grad)
        self.assertIsNotNone(model.critic.byte.weight.grad)

    def test_uncommitted_tail_is_archived_and_seed_position_restored(self):
        import json
        from draftrl import recovery
        from draftrl.checkpoint import source_version, digest
        from gakumas_arena.engine.search import search_content_version
        with tempfile.TemporaryDirectory(prefix='arena-recovery-test-') as folder:
            root=Path(folder); setup=root/'setup'; setup.mkdir()
            (setup/'profiles.json').write_text('{}',encoding='utf8')
            cfg={'absolute_deadline':'2026-10-01T00:00:00+00:00'}
            progress={'started_at':'2026-09-29T00:00:00+00:00'}
            model=DraftPolicy(); optimizer=groups(model,{p:.0005 for p in ('exam','drink','draft','guidance','memory')})
            (root/'manifest.json').write_text(json.dumps({'rl_source_sha256':source_version()}),encoding='utf8')
            committed=b'{"batch":1}\n'
            (root/'train-episodes.jsonl').write_bytes(committed)
            save(root/'latest.pt',model,optimizer,training_config=cfg,arena_sha256='test',
                 search_version=search_content_version(), setup_sha256={'profiles.json':digest(setup/'profiles.json')},
                 batches=1,decisions=10,next_episode_index=123,search_seed_counter=7,
                 run_progress=progress,committed_log_offsets={'train-episodes.jsonl':len(committed)})
            with (root/'train-episodes.jsonl').open('ab') as stream:stream.write(b'{"batch":2}\npartial')
            (root/'search-roots.jsonl').write_text('uncommitted',encoding='utf8')
            _,info,context=recovery.prepare(root,setup,cfg,'test','cpu')
            audit=recovery.commit_recovery(root,info,context)
            self.assertEqual((root/'train-episodes.jsonl').read_bytes(),committed)
            self.assertEqual((root/'search-roots.jsonl').read_bytes(),b'')
            self.assertEqual(audit['search_seed_counter'],7)
            self.assertTrue(audit['preserve_original_deadline'])
            self.assertEqual((Path(audit['evidence_backup'])/'train-episodes.jsonl.uncommitted').read_bytes(),b'{"batch":2}\npartial')


if __name__ == '__main__':
    unittest.main()
