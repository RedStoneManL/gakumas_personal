"""Read-only reporting must distinguish actions, raw roots and CE labels."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ASCEND = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load('aux_reporting_auditor', HERE/'verify_update.py')
dashboard = load('aux_reporting_dashboard', ASCEND/'dashboard/generalist_data.py')


def metric():
    return {'search_records': 0, 'ppo_records': 10, 'auxiliary_search_roots': 5,
            'auxiliary_search_records': 2, 'search_batch': {'counts': {'accepted_targets': 5}},
            'auxiliary_search': {'mode': 'peer_marginal', 'roots': 5, 'accepted_roots': 2,
                                 'weighted_roots': 1, 'rejected_roots': 3,
                                 'rejected_reasons': {'insufficient_distinct_root_particles': 3},
                                 'independent_heldout_validation': False},
            'search_learning': {'roots': 2, 'weighted_roots': 1, 'mean_weight': .5,
                                'mean_target_entropy': .4, 'mean_prior_entropy': .5,
                                'mean_behavior_entropy': .6},
            'phase_decisions': {'0': 10},
            'signed_credit': {'mode': 'best_of_k_state_contribution',
                              'groups': {'all_exam': {'records': 10, 'positive': 5, 'negative': 5, 'zero': 0}},
                              'frozen_pre_action_baselines': True, 'own_terminal_targets_preserved': True,
                              'records_sha256': '0'*64}}


CONFIG = {'search': {'execution_mode': 'auxiliary'}, 'signed_exam_credit': {'enabled': True}}


class AuxiliaryReportingTests(unittest.TestCase):
    def test_quality_rejection_is_not_a_missing_actor_search_error(self):
        value = metric()
        self.assertEqual(audit.search_record_problems(value, CONFIG), [])
        self.assertEqual(audit.learning_problems(value, CONFIG), [])

    def test_invalid_auxiliary_counts_are_detected(self):
        changes = [('search_records', 1), ('auxiliary_search_records', 6), ('auxiliary_search_roots', 4)]
        for key, value in changes:
            current = metric(); current[key] = value
            self.assertTrue(audit.search_record_problems(current, CONFIG))
        current = metric(); current['search_learning']['roots'] = 0
        self.assertTrue(audit.learning_problems(current, CONFIG))
        current = metric(); current['auxiliary_search']['weighted_roots'] = 3
        self.assertTrue(audit.search_record_problems(current, CONFIG))

    def test_old_actor_search_count_semantics_still_supported(self):
        current = {'search_records': 3, 'ppo_records': 7,
                   'search_batch': {'counts': {'accepted_targets': 3}}}
        self.assertEqual(audit.search_record_problems(current, {}), [])
        current['search_records'] = 2
        self.assertTrue(audit.search_record_problems(current, {}))

    def test_rank_local_router_counts_not_multiplied_or_equated_to_global(self):
        current = metric(); current['learner_world_size'] = 8
        current['search_batch']['counts']['accepted_targets'] = 1
        self.assertEqual(audit.search_record_problems(current, CONFIG), [])
        current['search_batch']['counts']['accepted_targets'] = 6
        self.assertTrue(audit.search_record_problems(current, CONFIG))

    def test_dashboard_exposes_all_count_stages_without_relabelling(self):
        current = metric(); before = copy.deepcopy(current)
        shown = dashboard.search_supervision_summary(current, CONFIG)
        self.assertEqual((shown['actor_search_records'], shown['real_ppo_records'],
                          shown['auxiliary_raw_roots'], shown['auxiliary_labels'],
                          shown['auxiliary_weighted_labels']), (0, 10, 5, 2, 1))
        self.assertEqual(shown['router_counter_scope'], 'main_router')
        self.assertEqual(shown['learning_counter_scope'], 'learner_global')
        self.assertEqual(current, before)
        legacy = dashboard.search_supervision_summary({'search_records': 3, 'ppo_records': 4}, {})
        self.assertEqual(legacy['execution_mode'], 'act')
        self.assertEqual(legacy['auxiliary_labels'], 0)

    def test_batch_report_does_not_count_aux_ce_as_additional_actions(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            value = {'batch': 1, **metric()}
            (folder/'metrics.jsonl').write_text(json.dumps(value)+'\n', encoding='utf8')
            (folder/'progress.log').write_text('', encoding='utf8')
            result = subprocess.run([sys.executable, str(ASCEND/'ops/batch_report.py'), str(folder),
                                     str(folder/'progress.log')], capture_output=True, text=True, check=True)
            self.assertIn('ppo=10 actor_search=0', result.stdout)
            self.assertIn('global_raw_roots=5 quality_labels=2 positive_weight_labels=1', result.stdout)
            self.assertNotIn('x8 for the batch', result.stdout)
            self.assertNotIn('should FALL', result.stdout)


if __name__ == '__main__':
    unittest.main()
