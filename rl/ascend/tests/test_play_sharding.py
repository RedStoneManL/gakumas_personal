import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from draftrl.distributed import shard
from draftrl.play_evaluation import evaluate_play


class FixedPlayShardingTests(unittest.TestCase):
    def setUp(self):
        self.tasks = [{'metadata': {'play_loadout_id': group}, 'replay_seed': 100 + group*8 + seed}
                      for group in range(2) for seed in range(8)]
        self.suite = {'tasks': self.tasks, 'replicas': 8, 'loadout_count': 2}
        self.rows = [dict(play_loadout_id=t['metadata']['play_loadout_id'], seed=t['replay_seed'],
                          entry_sha256=str(t['metadata']['play_loadout_id']), score_scale=100,
                          score=t['replay_seed'], normalized_score=t['replay_seed']/100, profile='hiro')
                     for t in self.tasks]
        self.config = {'_setup': '/prepared/setup', '_policy_version': 'policy:1'}

    def evaluate(self, output):
        return evaluate_play(None, None, self.config, 'cpu', self.suite, None, output, 'fixed',
                             lambda rows: {'scores': sorted(r['score'] for r in rows)})

    def test_eight_shards_preserve_full_seed_groups_and_serial_result(self):
        # Two seeds per rank: best-of-four groups span multiple ranks and must
        # only be reduced after gathering, regardless of completion order.
        gathered = []
        for rank in reversed(range(8)):
            offset, count = shard(len(self.rows), 8, rank)
            gathered.extend(reversed(self.rows[offset:offset+count]))
        mesh = Mock()
        mesh.bank_rollout.return_value = ([], gathered)
        before = copy.deepcopy(self.suite)
        with tempfile.TemporaryDirectory() as folder:
            with patch('draftrl.distributed.ACTIVE', None), patch(
                    'draftrl.play_evaluation.rollout_bank', return_value=([], self.rows, 0)):
                serial = self.evaluate(folder)
            with patch('draftrl.distributed.ACTIVE', mesh), patch(
                    'draftrl.play_evaluation.rollout_bank', side_effect=AssertionError('Serial rollout used')):
                parallel = self.evaluate(folder)
            self.assertEqual(serial, parallel)
            self.assertEqual(before, self.suite)
            self.assertIs(mesh.bank_rollout.call_args.args[4], self.tasks)
            self.assertEqual(mesh.bank_rollout.call_args.args[2], self.config['_setup'])
            self.assertEqual(mesh.bank_rollout.call_args.kwargs['source'], 'validation_fixed')
            self.assertTrue((Path(folder)/'fixed.json').exists())

    def test_rejects_lost_whole_group_duplicate_seed_and_training_records(self):
        for records, rows in (([], self.rows[4:]), ([], self.rows[:-1]+self.rows[:1]), ([{}], self.rows)):
            with self.subTest(records=bool(records), count=len(rows)):
                mesh = Mock()
                mesh.bank_rollout.return_value = (records, rows)
                with tempfile.TemporaryDirectory() as folder, patch('draftrl.distributed.ACTIVE', mesh):
                    with self.assertRaises(ValueError):
                        self.evaluate(folder)
                    self.assertFalse((Path(folder)/'fixed.json').exists())
