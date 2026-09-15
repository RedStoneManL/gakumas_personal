import contextlib
import copy
from dataclasses import replace
import io
import json
from pathlib import Path
import random
import tempfile
import unittest

import torch

from gakumas_training.algorithms import PPOConfig
from gakumas_training.contracts import DecisionContext, Episode, PolicySelection, Transition
from gakumas_training.runtime import RunConfig, Trainer
from gakumas_training.runtime.trainer import episode_summary
from gakumas_training.runtime.checkpoint import capture_rng
from test_ppo import TinyPolicy


class TinyEncoder:
    def __init__(self):
        self.seen = []

    def state_dict(self):
        return {"seen": list(self.seen)}

    def load_state_dict(self, value):
        self.seen = list(value["seen"])


class TinyRunner:
    def __init__(self, encoder, model):
        self.encoder, self.model = encoder, model

    def act(self, context, policy_version=0, deterministic=False):
        self.encoder.seen.append(context.observation["public"])
        encoded = [1., float(context.observation["public"])]
        with torch.no_grad():
            ev = self.model.evaluate([encoded])
            dist = torch.distributions.Categorical(logits=ev.logits)
            action = ev.logits.argmax(-1) if deterministic else dist.sample()
            return PolicySelection(int(action), float(dist.log_prob(action)), float(ev.values[0]),
                                   policy_version, encoded)


class TinyTask:
    def __init__(self, name="exam_score", fail=False):
        self.name, self.fail = name, fail

    def run_episode(self, policy, *, seed, policy_version):
        if self.fail:
            raise RuntimeError("authoritative engine failure")
        d = DecisionContext(self.name, "exam", {"public": seed % 3}, ({"a": 0}, {"a": 1}))
        selection = policy(d)
        score = 20. + 10 * selection.action_index + seed % 5
        return Episode(self.name, seed, [Transition(d, selection)], score,
                       "failed" if seed % 2 else "passed", {"native_score": score})


def make_trainer(output, *, config=None, arena_version="arena-test-v1", fail=False):
    config = config or RunConfig(task="exam_score", seed=101, eval_seed=10001, episodes_per_update=4,
        eval_every_updates=1, eval_episodes=2, score_scale=10,
        ppo=PPOConfig(epochs=1, minibatch_size=4, microbatch_size=2))
    random.seed(config.seed)
    torch.manual_seed(config.seed)
    encoder, model = TinyEncoder(), TinyPolicy()
    return Trainer(task=TinyTask(config.task, fail), encoder=encoder, model=model,
        policy_runner=TinyRunner(encoder, model), config=config, output=output, arena_version=arena_version)


class RuntimeTests(unittest.TestCase):
    def test_setup_modes_and_selection_counts_keep_failure_scores(self):
        episodes = []
        for i, (profile, mode, score) in enumerate((('a', 'given', 10.), ('a', 'select', 20.),
                                                   ('b', 'given', 30.), ('b', 'select', 0.))):
            decision = DecisionContext('full_produce', 'exam_action', {}, ({'a': 0}, {'a': 1}))
            selection = PolicySelection(0, -1., 0., 0, [1., 0.])
            episode = Episode('full_produce', 101 + i, [Transition(decision, selection)], score,
                'failed' if score == 0 else 'passed', {'loadout_profile': profile, 'setup_mode': mode,
                    'selected_support_ids': ['support-a'] if mode == 'given' else ['support-b'],
                    'selected_memory_ids': []})
            if mode == 'select':
                transition = episode.transitions[0]
                episode.transitions[0] = replace(transition, decision=replace(transition.decision,
                    kind='setup_support', candidates=({'support_ref': 'setup:support:support-a'}, {'support_ref': 'setup:support:support-b'})),
                    selection=replace(transition.selection, action_index=1))
            episodes.append(episode)
        metrics = episode_summary(episodes)
        self.assertEqual(metrics['setup_modes']['given']['raw_score_mean'], 20.)
        self.assertEqual(metrics['setup_modes']['select']['raw_score_mean'], 10.)
        self.assertEqual(metrics['loadout_profiles']['b']['setup_modes']['select']['raw_score_mean'], 0.)
        self.assertEqual(metrics['setup_selection_counts'], {'setup_support': {'setup:support:support-b': 2}})
        self.assertEqual(metrics['equipped_inventory_counts']['select'],
                         {'episodes': 2, 'support_ids': {'support-b': 2}, 'memory_ids': {}})
        self.assertEqual(metrics['equipped_inventory_counts']['given']['support_ids'], {'support-a': 2})

    def test_setup_entropy_resume_matches_next_update(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            def setup_trainer(path):
                trainer = make_trainer(path)
                run_episode = trainer.task.run_episode
                def mixed_episode(policy, *, seed, policy_version):
                    # Sample through the real runner with setup kind present in
                    # the recorded input, using the same frozen behavior model.
                    def setup_policy(decision):
                        return policy(replace(decision, kind='setup_memory' if seed % 2 else 'exam_action'))
                    episode = run_episode(setup_policy, seed=seed, policy_version=policy_version)
                    transition = episode.transitions[0]
                    episode.transitions[0] = replace(transition, decision=replace(transition.decision,
                        kind='setup_memory' if seed % 2 else 'exam_action'))
                    return episode
                trainer.task.run_episode = mixed_episode
                return trainer
            original = setup_trainer(Path(directory) / 'original')
            original.train(1)
            saved = Path(directory) / 'saved.pt'
            saved.write_bytes(original.checkpoint_path.read_bytes())
            original.train(1)
            resumed = setup_trainer(Path(directory) / 'resumed')
            resumed.resume(saved)
            metrics = resumed.train(1)[0]
            for key, value in original.model.state_dict().items():
                torch.testing.assert_close(value, resumed.model.state_dict()[key], rtol=0, atol=0)
            self.assertEqual(metrics['ppo']['decision_kinds']['setup_memory']['entropy_coefficient'], .05)
            self.assertLess(metrics['ppo']['behavior_parity_max_error'], resumed.config.ppo.behavior_tolerance)

    def test_safe_boundary_resume_matches_uninterrupted_next_update(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            original = make_trainer(Path(directory) / "full")
            original.train(1)
            saved = Path(directory) / "resume.pt"
            saved.write_bytes(original.checkpoint_path.read_bytes())
            original.train(1)
            expected = copy.deepcopy(original.model.state_dict())
            expected_optimizer = copy.deepcopy(original.updater.optimizer.state_dict())
            resumed = make_trainer(Path(directory) / "resumed")
            resumed.resume(saved)
            resumed.train(1)
            for key, value in expected.items():
                torch.testing.assert_close(value, resumed.model.state_dict()[key], rtol=0, atol=0)
            for index, state in expected_optimizer["state"].items():
                for key, value in state.items():
                    torch.testing.assert_close(value, resumed.updater.optimizer.state_dict()["state"][index][key], rtol=0, atol=0)
            self.assertEqual(resumed.encoder.state_dict(), original.encoder.state_dict())
            self.assertEqual(resumed.seed_cursor, 109)
            self.assertEqual(resumed.policy_version, 2)
            self.assertEqual(resumed.iteration, 2)

    def test_resume_rejects_task_schema_arena_and_config_mismatch(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            first = make_trainer(Path(directory) / "first")
            first.train(1)
            bad_task = make_trainer(Path(directory) / "task", config=replace(first.config, task="full_produce"))
            bad_arena = make_trainer(Path(directory) / "arena", arena_version="new-arena")
            bad_scale = make_trainer(Path(directory) / "scale", config=replace(first.config, score_scale=20))
            for candidate in (bad_task, bad_arena, bad_scale):
                with self.assertRaises(ValueError):
                    candidate.resume(first.checkpoint_path)
            value = torch.load(first.checkpoint_path, weights_only=True)
            value["checkpoint_schema"] = "unknown"
            malformed = Path(directory) / "bad.pt"
            torch.save(value, malformed)
            with self.assertRaises(ValueError):
                make_trainer(Path(directory) / "schema").resume(malformed)

    def test_evaluation_keeps_training_rng_vocab_and_reports_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            trainer = make_trainer(directory)
            rng, vocab = capture_rng(), trainer.encoder.state_dict()
            result = trainer.evaluate()
            after = capture_rng()
            self.assertEqual(after["python"], rng["python"])
            self.assertEqual(after["numpy"], rng["numpy"])
            self.assertTrue(torch.equal(after["torch"], rng["torch"]))
            self.assertEqual(trainer.encoder.state_dict(), vocab)
            self.assertEqual(result["episodes"], 2)
            self.assertEqual(result["terminations"], {"failed": 1, "passed": 1})
            rows = [json.loads(s) for s in (Path(directory) / "evaluation" / "episodes.jsonl").read_text().splitlines()]
            self.assertEqual(result["raw_score_mean"], sum(row["raw_score"] for row in rows) / 2)

    def test_engine_errors_raise_and_never_fabricate_zero_score(self):
        with tempfile.TemporaryDirectory() as directory:
            trainer = make_trainer(directory, fail=True)
            with self.assertRaisesRegex(RuntimeError, "authoritative engine failure"):
                trainer.train(1)
            progress = json.loads((Path(directory) / "progress.json").read_text())
            self.assertEqual(progress["status"], "failed")
            self.assertFalse((Path(directory) / "training" / "episodes.jsonl").exists())
            self.assertFalse(trainer.checkpoint_path.exists())


if __name__ == "__main__":
    unittest.main()
