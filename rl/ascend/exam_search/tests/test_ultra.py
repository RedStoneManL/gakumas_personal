import copy
import unittest
from test_decision_exploration import source_config
from draftrl.distribution import schedule
from draftrl.ultra_migration import make_config,validate_config
from draftrl.resource_modes import PRESETS,validate_request,SCHEMA


class UltraTests(unittest.TestCase):
    def test_lightweight_fingerprint_matches_checkpoint_fingerprint(self):
        from draftrl.source_identity import source_version as light
        from draftrl.checkpoint import source_version as full
        self.assertEqual(light(),full())

    def test_preset_doubles_sampling_preserves_training_block(self):
        extra,ultra=PRESETS['extra'],PRESETS['ultra']
        self.assertEqual(ultra['workers'],2*extra['workers'])
        for key in ('parallel_roots','inference_batch'):
            self.assertEqual(ultra[key],4*extra[key])
        self.assertLessEqual(ultra['cuda_memory_fraction'],.85)
        self.assertEqual(ultra['microbatch'],extra['microbatch'])
        self.assertEqual(ultra['priority'],'normal')
        validate_request({'schema':SCHEMA,'mode':'ultra','request_id':'test',
                          'requested_at':'2026-09-15T03:00:00+08:00'})

    def test_pending_decision_change_is_continuous_with_ultra(self):
        old=source_config();old['resource_mode']='extra'
        snapshot=schedule(old,67203,elapsed_minutes=1300)
        new=make_config(old,82000,snapshot,200000)
        self.assertEqual(new['resource_mode'],'ultra')
        self.assertEqual(schedule(new,82000),snapshot)
        self.assertTrue(validate_config(old,new,decisions=82000,snapshot=snapshot)['exploration_change']['continuous_at_boundary'])
        wrong=copy.deepcopy(new);wrong['search']['simulations']=64
        with self.assertRaises(ValueError):validate_config(old,wrong)

    def test_existing_decision_schedule_does_not_reset_on_ultra_migration(self):
        old=source_config();snapshot=schedule(old,10,elapsed_minutes=1300)
        new=make_config(old,10,snapshot,200000)
        new['resource_mode']='extra'
        later=make_config(new,100010,schedule(new,100010),200000)
        self.assertEqual(later['exploration_schedule'],new['exploration_schedule'])
        self.assertEqual(later['exploration'],new['exploration'])


if __name__=='__main__':unittest.main()
