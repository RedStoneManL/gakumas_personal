import json
from pathlib import Path
import unittest
from unittest.mock import patch

from gakumas_training.cli import default_config, entrypoint
from gakumas_training.runtime.config import RunConfig


class CLITests(unittest.TestCase):
    def test_console_entrypoint_returns_success_code_not_training_result(self):
        with patch("gakumas_training.cli.main", return_value=[{"iteration": 1}]):
            self.assertEqual(entrypoint(), 0)

    def test_packaged_defaults_match_reviewable_configs(self):
        root = Path(__file__).resolve().parents[1]
        for task, scale in (("full_produce", 50000), ("exam_score", 150000)):
            packaged = default_config(task)
            self.assertEqual(packaged, json.loads((root / "configs" / f"{task}.json").read_text()))
            self.assertEqual(RunConfig.from_dict(packaged).score_scale, scale)

    def test_overlapping_train_evaluation_seed_ranges_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            RunConfig(task="exam_score", seed=100, episodes_per_update=10, eval_seed=105)


if __name__ == "__main__":
    unittest.main()
