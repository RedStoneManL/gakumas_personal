"""Contract checks for selecting the new run without changing trainer state."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from generalist_data import GeneralistData, pool_rules, replay_runtime, tail_rows, tail_text, completed_validation


class GeneralistContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / 'rl/generalist'
        self.folder = self.base / 'runs/run-one'
        self.folder.mkdir(parents=True)
        self.write(self.base / 'active.json', {'output': str(self.folder), 'profiles': ['hiro', 'saki']})
        self.api = GeneralistData(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding='utf8')

    def test_scores_and_profiles_keep_separate_units(self):
        self.write(self.folder / 'progress.json', {'status': 'running', 'trainer_pid': 1,
                   'batches': 1, 'decisions': 2048, 'best_validation_index': 1.08})
        self.write(self.folder / 'validation-initial.json', {'mean': 200000, 'normalized_mean': 1.2,
                   'profiles': {'hiro': {'mean': 300000, 'normalized_mean': 2}}})
        (self.folder / 'metrics.jsonl').write_text(json.dumps({'batch': 1, 'decisions': 2048,
            'train_mean': 100000, 'train_normalized_mean': 1.5, 'drink_capacity_counts': {'0': 8}}) + '\n')
        (self.folder / 'validation-history.jsonl').write_text(json.dumps({'batch': 1, 'decisions': 2048,
            'mean': 190000, 'normalized_mean': 1.25, 'validation_index': 1.08,
            'profiles': {'hiro': {'mean': 310000, 'normalized_mean': 2.1}}}) + '\n')
        with patch('generalist_data.alive', return_value=True):
            value = self.api.state()
        self.assertEqual(value['metrics']['train_raw_mean'], 100000)
        self.assertEqual(value['metrics']['train_normalized_mean'], 1.5)
        self.assertEqual(value['metrics']['validation_index'], 1.08)
        self.assertEqual(value['series']['validation'][0]['validation_index'], 1)
        self.assertEqual(value['series']['validation'][0]['profiles']['hiro']['normalized_mean'], 2)
        self.assertEqual(value['profiles'][0]['validation']['normalized_mean'], 2.1)
        self.assertEqual(value['distributions']['drink_capacity_counts']['0'], 8)

    def test_no_fabricated_alive_or_score_without_progress(self):
        value = self.api.state()
        self.assertIsNone(value['trainer_alive'])
        self.assertIsNone(value['metrics']['validation_raw_mean'])
        self.assertEqual(value['series']['validation'], [])

    def test_completed_validation_is_supplemented_without_rewriting_logs(self):
        old = self.base / 'runs/old';old.mkdir()
        baseline = {'schema':'v', 'mean':10, 'normalized_mean':1.,
            'episodes':[{'seed':100,'benchmark_cell':'hiro','score_scale':10}],
            'benchmark_cells':{'hiro':{'normalized_mean':1.}}}
        final = dict(baseline,mean=20,normalized_mean=2.,
                     benchmark_cells={'hiro':{'normalized_mean':2.}})
        self.write(self.folder/'validation-initial.json',baseline)
        self.write(self.folder/'manifest.json',{'config':{'batch_decisions':4096},
                   'continuations':[{'checkpoint_batch':4}]})
        self.write(self.folder/'progress.json',{'status':'running','batches':5,'batch_decisions':2048})
        self.write(old/'progress.json',{'status':'complete','batches':4,'decisions':8000,'best_validation_index':1.8})
        self.write(old/'validation-final.json',final)
        self.write(self.folder/'validation-final.json',dict(final,mean=99999))
        self.write(self.base/'active.json',{'output':str(self.folder),'source_run':str(old)})
        log=self.folder/'validation-history.jsonl';log.write_text('')
        value=self.api.state()
        self.assertEqual(value['metrics']['validation_raw_mean'],20)
        self.assertAlmostEqual(value['metrics']['validation_index'],2.25/1.25)
        self.assertEqual(value['metrics']['validation_batch'],4)
        self.assertFalse(value['metrics']['validation_from_current_revision'])
        self.assertEqual(value['progress']['batch_decisions'],4096)
        self.assertEqual(log.read_text(),'')
        self.assertIsNone(completed_validation(self.folder,baseline))
        paused = self.base/'runs/paused'; paused.mkdir()
        self.write(paused/'progress.json',{'status':'paused','batches':5,'decisions':10000})
        self.write(paused/'validation-final.json',dict(final,mean=88888))
        self.write(self.base/'active.json',{'output':str(self.folder),'source_run':str(paused)})
        self.write(self.folder/'manifest.json',{'config':{'batch_decisions':4096},
            'continuations':[{'checkpoint_batch':4,'source_run':str(old)},
                             {'checkpoint_batch':5,'source_run':str(paused)}]})
        value=self.api.state()
        self.assertEqual(value['metrics']['validation_raw_mean'],20)
        self.assertEqual(value['metrics']['validation_batch'],4)
        self.assertEqual(log.read_text(),'')

    def test_final_validation_rejects_different_eval_seeds(self):
        self.write(self.folder/'progress.json',{'status':'complete','batches':4,'decisions':8000})
        baseline={'schema':'v','episodes':[{'seed':100,'benchmark_cell':'a','score_scale':10}],
                  'benchmark_cells':{'a':{'normalized_mean':1.}}}
        final=dict(baseline,episodes=[{'seed':999,'benchmark_cell':'a','score_scale':10}])
        self.write(self.folder/'validation-final.json',final)
        self.assertIsNone(completed_validation(self.folder,baseline))

    def test_copy_cap_does_not_restore_old_unrestricted_curve(self):
        old=self.base/'runs/old-cap';old.mkdir()
        baseline={'schema':'v','mean':10,'normalized_mean':1.,
                  'episodes':[{'seed':100,'benchmark_cell':'a','score_scale':10}],
                  'benchmark_cells':{'a':{'normalized_mean':1.}}}
        self.write(self.folder/'validation-initial.json',baseline)
        self.write(self.folder/'manifest.json',{'config':{'practice':{'duplicates':{'max_same_name':4}}}})
        self.write(self.folder/'construction-benchmark.json',{'start_batch':717,'max_same_name':4})
        self.write(old/'manifest.json',{'config':{}})
        self.write(old/'progress.json',{'status':'complete','batches':700,'decisions':2700000})
        self.write(old/'validation-final.json',baseline)
        self.write(self.base/'active.json',{'output':str(self.folder),'source_run':str(old)})
        row={'batch':717,'decisions':2800000,'mean':10,'normalized_mean':1.,'validation_index':1.,'best_index':1.}
        (self.folder/'validation-history.jsonl').write_text(json.dumps(row)+'\n')
        value=self.api.state()
        self.assertEqual([r['batch'] for r in value['series']['validation']],[717])
        self.assertEqual(value['practice']['construction_reference']['start_batch'],717)
        self.assertIn('同名卡最多 4 张',value['setup']['pool_rules']['description'])
        self.write(old/'manifest.json',{'config':{'practice':{'duplicates':{'max_same_name':4}}}})
        self.write(self.folder/'manifest.json',{'config':{'practice':{'duplicates':{'max_same_name':4,
            'max_same_name_overrides':{'精神統一':2}}}}})
        value=self.api.state()
        self.assertEqual([r['batch'] for r in value['series']['validation']],[717])
        self.assertIn('精神統一单独最多 2 张',value['setup']['pool_rules']['description'])

    def test_stale_running_status_is_not_presented_as_alive(self):
        self.write(self.folder / 'progress.json', {'status': 'running', 'trainer_pid': 1})
        with patch('generalist_data.alive', return_value=False):
            self.assertEqual(self.api.state()['status'], 'stopped')

    def test_output_cannot_escape_run_root(self):
        self.write(self.base / 'active.json', {'output': str(self.root)})
        with self.assertRaises(ValueError):
            self.api.state()

    def test_logs_are_named_and_contained(self):
        with self.assertRaises(ValueError):
            self.api.logs('../../some-file')
        self.write(self.base / 'active.json', {'output': str(self.folder), 'stdout': str(self.root / 'secret')})
        with self.assertRaises(ValueError):
            self.api.logs('stdout')

    def test_episode_sources_cannot_traverse(self):
        with self.assertRaises(ValueError):
            self.api.episode('train', '../../active.json', 1)
        with self.assertRaises(ValueError):
            self.api.episodes('../../')

    def test_partial_jsonl_and_tail_are_bounded(self):
        path = self.folder / 'tail.jsonl'
        path.write_text('\n'.join(json.dumps({'row': i}) for i in range(500)) + '\n{"row":', encoding='utf8')
        self.assertEqual([r['row'] for r in tail_rows(path, 2)], [498, 499])
        result = tail_text(path, count=3, limit=100)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['line_count'], 3)

    def test_no_drinks_and_counted_vs_physical_deck(self):
        row = {'seed': 123, 'profile': 'saki', 'score': 99, 'normalized_score': .01,
               'deck_size': 18, 'physical_deck_size': 19, 'drink_capacity': 0,
               'drinks': [], 'entry': {'cards': [{}] * 19}}
        value = self.api.summary(row, 'train-episodes.jsonl', 'train')
        self.assertEqual(value['deck_size'], 18)
        self.assertEqual(value['physical_deck_size'], 19)
        self.assertEqual(value['drink_capacity'], 0)
        self.assertEqual(value['drinks'], [])

    def test_legacy_empty_selection_is_not_inferred_as_no_hif_environment(self):
        row = {'seed': 1, 'selected_memories': [], 'entry': {'cards': []}}
        value = self.api.summary(row, 'train-episodes.jsonl', 'train')
        self.assertIsNone(value['memory_mode'])
        self.assertIsNone(value['memory_capacity'])
        self.assertEqual(value['selected_memory_count'], 0)
        self.assertIn('旧任务', value['memory_status'])
        state = self.api.state()
        self.assertFalse(state['memory_conditions']['enabled'])
        self.assertEqual(state['memory_conditions']['baseline'], {})

    def test_hif_empty_selection_and_disabled_environment_remain_distinct(self):
        for mode, capacity in [('none', 0), ('hif', 4)]:
            row = {'seed': 1, 'memory_mode': mode, 'memory_capacity': capacity,
                   'selected_memories': [], 'entry': {'cards': [], 'memory_abilities': [],
                       'context': {}, 'resources': {}}}
            (self.folder / 'train-episodes.jsonl').write_text(json.dumps(row) + '\n')
            value = self.api.episode('train', 'train-episodes.jsonl', 1, replay=False)
            self.assertEqual(value['memory_mode'], mode)
            self.assertEqual(value['memory_capacity'], capacity)
            self.assertEqual(value['initial_memories'], [])
            self.assertEqual(value['selected_memory_count'], 0)
            self.assertIn('禁用' if mode == 'none' else '可选', value['memory_effects_note'])

    def test_memory_conditions_and_cross_cells_preserve_fixed_baseline(self):
        initial = {'mean': 100, 'normalized_mean': 1.0,
            'memory_modes': {'none': {'count': 90, 'mean': 80, 'normalized_mean': .8}},
            'condition_cells': {'none|drinks=0': {'memory_mode': 'none', 'drink_capacity': 0,
                'count': 30, 'mean': 50, 'normalized_mean': .5}}}
        latest = {'batch': 4, 'decisions': 8192, 'mean': 110, 'normalized_mean': 1.1,
            'memory_modes': {'none': {'count': 90, 'mean': 88, 'normalized_mean': .88}},
            'condition_cells': {'none|drinks=0': {'memory_mode': 'none', 'drink_capacity': 0,
                'count': 30, 'mean': 60, 'normalized_mean': .6}}}
        self.write(self.folder / 'validation-initial.json', initial)
        (self.folder / 'validation-history.jsonl').write_text(json.dumps(latest) + '\n')
        (self.folder / 'metrics.jsonl').write_text(json.dumps({'memory_mode_counts': {'none': 15, 'hif': 15},
            'condition_counts': {'none|drinks=0': 5}}) + '\n')
        value = self.api.state()
        self.assertTrue(value['memory_conditions']['enabled'])
        self.assertEqual(value['memory_conditions']['baseline'], initial['memory_modes'])
        self.assertEqual(value['memory_conditions']['validation'], latest['memory_modes'])
        self.assertEqual(value['memory_conditions']['condition_validation'], latest['condition_cells'])
        self.assertEqual(value['series']['validation'][0]['memory_modes'], initial['memory_modes'])
        self.assertEqual(value['series']['validation'][1]['condition_cells'], latest['condition_cells'])
        self.assertEqual(value['distributions']['memory_mode_counts'], {'none': 15, 'hif': 15})

    def test_replay_only_accepts_named_workspace_revisions(self):
        for revision in ('generalist', 'generalist-memory', 'generalist-support'):
            allowed = self.root / 'rl' / revision / 'runtime/arena'
            self.assertEqual(replay_runtime(self.root, allowed), allowed.resolve())
        for invalid in (self.root / 'other/arena', self.root / 'rl/other/runtime/arena',
                        self.root.parent / 'outside/runtime/arena'):
            with self.assertRaises(ValueError):
                replay_runtime(self.root, invalid)

    def test_new_support_rule_is_not_added_to_old_tasks(self):
        old = pool_rules({'profiles': [{'id': 'hiro', 'spec': {}}]})
        self.assertFalse(old['exclude_prima_stella'])
        self.assertIsNone(old['support_card_limit'])
        self.assertNotIn('不含一番星', old['description'])
        self.assertNotIn('支援专属卡', old['description'])
        new = pool_rules({'profiles': [{'id': 'hiro', 'spec': {
            'exclude_prima_stella': True, 'support_card_limit': 3, 'support_card_ids': [11, 12]}}]})
        self.assertTrue(new['exclude_prima_stella'])
        self.assertEqual(new['support_card_limit'], 3)
        self.assertEqual(new['description'], '不含一番星 · 支援专属卡最多 3 张')
        self.assertIn('支援专属卡占其中槽位', new['count_note'])

    def test_support_count_counts_copies_and_profile_scoped_ids(self):
        manifest = {'profiles': [
            {'id': 'hiro', 'spec': {'support_card_limit': 3, 'support_card_ids': [11, 12]}},
            {'id': 'saki', 'spec': {'support_card_limit': 3, 'support_card_ids': [31]}}]}
        cards = [{'instance_id': str(i), 'definition_id': d} for i, d in enumerate([11, 11, 12, 31])]
        row = {'seed': 1, 'profile': 'hiro', 'entry': {'cards': cards, 'context': {}, 'resources': {}}}
        self.write(self.folder / 'manifest.json', manifest)
        (self.folder / 'train-episodes.jsonl').write_text(json.dumps(row) + '\n')
        summary = self.api.episodes('train')[0]
        self.assertEqual(summary['support_card_count'], 3)
        self.assertEqual(summary['support_card_limit'], 3)
        detail = self.api.episode('train', 'train-episodes.jsonl', 1, replay=False)
        self.assertEqual([c.get('source_type') for c in detail['initial_cards']],
                         ['support', 'support', 'support', None])
        old = self.api.summary(row, 'train-episodes.jsonl', 'train', {})
        self.assertIsNone(old['support_card_count'])
        self.assertIsNone(old['support_card_limit'])

    def test_live_exam_progress_does_not_become_a_committed_update(self):
        log=self.folder/'stdout.log'
        self.write(self.base/'active.json',{'output':str(self.folder),'stdout':str(log)})
        self.write(self.folder/'manifest.json',{'config':{'search':{'enabled':True}}})
        self.write(self.folder/'progress.json',{'event':'search_progress','batches':0})
        rows=[{'event':'bank_rollout_begin','count':160},
              {'event':'bank_rollout','completed':160,'active':0},
              {'event':'rollout_begin','training':True,'target_decisions':4096},
              {'event':'bank_rollout_begin','count':72},
              {'event':'bank_rollout','completed':19,'active':22}]
        log.write_text(''.join(json.dumps(r)+'\n' for r in rows)+'{"incomplete":',encoding='utf8')
        result=self.api.state()['search']
        self.assertIsNone(result['batch'])
        self.assertEqual(result['current_rollout']['completed'],19)
        self.assertEqual(result['current_rollout']['total_games'],72)
        self.assertFalse(result['current_rollout']['committed'])
        self.assertEqual(self.api.current_rollout({'stdout':str(log)}, {'event':'evaluating'}),{})

    def test_support_source_type_from_candidate_is_recognized(self):
        manifest = {'profiles': [{'id': 'hiro', 'spec': {'support_card_limit': 3,
            'candidates': [{'source_type': 'support', 'card': {'definition_id': 11}},
                           {'source_type': 'regular', 'card': {'definition_id': 12}}]}}]}
        row = {'seed': 1, 'profile': 'hiro', 'entry': {'cards': [{'definition_id': 11}, {'definition_id': 12}]}}
        summary = self.api.summary(row, 'train-episodes.jsonl', 'train', manifest)
        self.assertEqual(summary['support_card_count'], 1)


if __name__ == '__main__':
    unittest.main()
