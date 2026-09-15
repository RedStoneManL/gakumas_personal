import copy
import math
import unittest

from test_joint_search import torch
from draftrl.distribution import schedule, distributions
from draftrl.exploration_migration import make_decision_config, validate_change, PHASES, KEYS


def source_config():
    return {
        'exploration_schedule': {'basis':'elapsed_minutes', 'origin_elapsed_minutes':0,
                                 'hold_minutes':0, 'decay_minutes':2880},
        'exploration': {p:{'temperature':[1.6,1.1], 'uniform_mix':[.3,.06],
                           'entropy_coefficient':[.015,.006]} for p in PHASES},
        'learning_rate': .0005, 'search': {'simulations':32},
        'practice': {'forks': {'replicas':4,'objective':'best_of_k'}},
        'absolute_deadline':'2026-09-15T20:47:33.416779+00:00',
    }


class DecisionExplorationTests(unittest.TestCase):
    def setUp(self):
        self.source = source_config()
        self.snapshot = schedule(self.source, 67203, elapsed_minutes=1300)
        self.config = make_decision_config(self.source, 82000, self.snapshot, 200000)

    def test_no_jump_and_no_wall_clock_decay(self):
        for elapsed in (None, 0, 1300, 2880, 1000000):
            self.assertEqual(schedule(self.config,82000,elapsed_minutes=elapsed),self.snapshot)
        self.assertEqual(schedule(self.config,0),self.snapshot)
        self.assertEqual(self.source,source_config())

    def test_decision_progress_midpoint_and_floor(self):
        halfway=schedule(self.config,182000)
        terminal=schedule(self.config,282000)
        for phase in PHASES:
            for key in KEYS:
                floor=self.source['exploration'][phase][key][1]
                self.assertAlmostEqual(halfway[phase][key],(self.snapshot[phase][key]+floor)/2)
                self.assertAlmostEqual(terminal[phase][key],floor)
        self.assertEqual(schedule(self.config,10**9),terminal)

    def test_all_other_config_and_floors_are_preserved(self):
        audit=validate_change(self.source,self.config,decisions=82000,snapshot=self.snapshot)
        self.assertTrue(audit['continuous_at_boundary'])
        for field,value in [('learning_rate',.01),('absolute_deadline','later'),
                            ('search',{'simulations':64}),('practice',{})]:
            changed=copy.deepcopy(self.config);changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_change(self.source,changed)
        changed=copy.deepcopy(self.config)
        changed['exploration']['exam']['temperature'][1]=1.0
        with self.assertRaises(ValueError):validate_change(self.source,changed)

    def test_reject_wrong_checkpoint_origin_or_snapshot(self):
        with self.assertRaises(ValueError):
            validate_change(self.source,self.config,decisions=81999,snapshot=self.snapshot)
        wrong=copy.deepcopy(self.snapshot);wrong['exam']['temperature']+=.01
        with self.assertRaises(ValueError):
            validate_change(self.source,self.config,decisions=82000,snapshot=wrong)

    def test_bad_counters_and_unknown_basis_fail_closed(self):
        for bad in (-1,1.5,True,float('nan'),float('inf')):
            with self.subTest(counter=bad),self.assertRaises(ValueError):schedule(self.config,bad)
        for field,bad in [('decay_decisions',0),('origin_decisions',-1),('hold_decisions',1.5),
                          ('basis','meaningful_decisons')]:
            changed=copy.deepcopy(self.config);changed['exploration_schedule'][field]=bad
            with self.subTest(field=field),self.assertRaises(ValueError):schedule(changed,82000)

    def test_saved_behavior_likelihood_does_not_use_later_schedule(self):
        logits=torch.tensor([[.5,2.,99.]])
        mask=torch.tensor([[True,True,False]])
        frozen=[copy.deepcopy(self.snapshot['exam'])]
        before,_=distributions(logits,mask,frozen)
        later=schedule(self.config,282000)
        after,_=distributions(logits,mask,frozen)
        newer,_=distributions(logits,mask,[later['exam']])
        self.assertTrue(torch.equal(before.probs,after.probs))
        self.assertFalse(torch.equal(before.probs,newer.probs))
        self.assertEqual(float(after.probs[0,2]),0.)

    def test_legacy_decision_schedule_compatibility(self):
        old=source_config();old.pop('exploration_schedule');old['exploration_decay_decisions']=100
        self.assertAlmostEqual(schedule(old,50)['exam']['temperature'],1.35)


if __name__=='__main__':unittest.main()
