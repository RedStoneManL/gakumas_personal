import copy
import unittest

from draftrl.continuation import same_signed_contract, split_training_log
from draftrl.learning_settings import SIGNED, SEARCH
from draftrl.search_supervision import DEFAULT_AUXILIARY_CREDIT


class AuxiliaryContinuationTests(unittest.TestCase):
    def config(self):
        return {'signed_exam_credit': copy.deepcopy(SIGNED), 'gamma': 1,
                'search': {'enabled': True, 'require_terminal': True, 'execution_mode': 'auxiliary',
                           'learning_target': None, 'auxiliary_credit': copy.deepcopy(DEFAULT_AUXILIARY_CREDIT)},
                'practice': {'forks': {'enabled': True, 'replicas': 4, 'objective': 'best_of_k',
                                       'exam_credit': 'leave_one_out_max'}}}

    def test_unchanged_v6_and_legacy_contracts_are_not_migrations(self):
        config = self.config()
        self.assertTrue(same_signed_contract(config, copy.deepcopy(config)))
        legacy = {'signed_exam_credit': SIGNED, 'search': {'learning_target': SEARCH}}
        self.assertTrue(same_signed_contract(legacy, copy.deepcopy(legacy)))

    def test_new_signed_settings_and_search_contract_changes_still_require_migration(self):
        source = self.config()
        target = copy.deepcopy(source)
        target['search']['auxiliary_credit']['max_logit_change'] *= 2
        self.assertFalse(same_signed_contract(source, target))
        target = copy.deepcopy(source)
        target['signed_exam_credit']['rms_floor'] *= 2
        self.assertFalse(same_signed_contract(source, target))
        target = copy.deepcopy(source)
        target['search']['learning_target'] = SEARCH
        self.assertFalse(same_signed_contract(source, target))
        source.pop('signed_exam_credit')
        self.assertFalse(same_signed_contract(source, target))

    def test_unchanged_invalid_auxiliary_contract_is_rejected(self):
        source = self.config()
        source['search']['require_terminal'] = False
        with self.assertRaises(ValueError):
            same_signed_contract(source, copy.deepcopy(source))
        source = self.config()
        target = copy.deepcopy(source)
        target['practice']['forks']['replicas'] = 2
        with self.assertRaises(ValueError):
            same_signed_contract(source, target)

    def test_committed_bank_replicas_survive_large_seeds_and_only_tail_is_archived(self):
        committed = b'{"sampling_source":"bank_exam","seed":2000000100}\n'
        tail = b'{"sampling_source":"joint","seed":5}\npartial'
        info = {'sample_bank': {'replay_counter': 20}, 'next_episode_index': 100,
                'committed_log_offsets': {'train-episodes.jsonl': len(committed)}}
        kept, archived = split_training_log(committed + tail, info)
        self.assertEqual(b''.join(kept), committed)
        self.assertEqual(b''.join(archived), tail)

    def test_invalid_log_boundary_fails_instead_of_discarding_committed_rows(self):
        for offset in (-1, 5, 99, True):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                split_training_log(b'{"seed":1}\n', {'committed_log_offsets': {'train-episodes.jsonl': offset}})
