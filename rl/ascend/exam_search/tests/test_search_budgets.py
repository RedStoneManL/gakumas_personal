import copy
import importlib.util
from pathlib import Path
import unittest
from test_joint_search import config
from draftrl.search_budgets import validate_timeout_change


class SearchBudgetTests(unittest.TestCase):
    def setUp(self):
        self.source=config()
        self.source['search'].update(sampling_ms=2000,seconds=60,simulations=32,particles=8)
        self.target=copy.deepcopy(self.source)
        self.target['search'].update(sampling_ms=10000,native_action_budget=60000)

    def test_only_time_and_work_budget_can_change(self):
        self.assertEqual(validate_timeout_change(self.source['search'],self.source['search']),{})
        self.assertEqual(validate_timeout_change(self.source['search'],self.target['search'])['sampling_ms']['new'],10000)
        for key,value in [('particles',4),('simulations',64),('loss_coefficient',.3),('seconds',120),('sampling_ms',60000),('native_action_budget',200000)]:
            with self.subTest(key=key):
                changed=copy.deepcopy(self.target['search']);changed[key]=value
                with self.assertRaises(ValueError):validate_timeout_change(self.source['search'],changed)

    @unittest.skip('Historical Windows supervisor; Ascend uses its own new-run/resume entry')
    def test_supervisor_preserves_all_other_parameters(self):
        spec=importlib.util.spec_from_file_location('timeout_supervisor',Path(__file__).resolve().parents[1]/'continue_run.py')
        supervisor=importlib.util.module_from_spec(spec);spec.loader.exec_module(supervisor)
        supervisor.validate_config(self.source,self.target)
        for key,value in [('learning_rate',.01),('absolute_deadline','later'),('effective_minibatch',2048)]:
            changed=copy.deepcopy(self.target);changed[key]=value
            with self.assertRaises(ValueError):supervisor.validate_config(self.source,changed)


if __name__=='__main__':unittest.main()
