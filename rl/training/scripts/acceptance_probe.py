"""Exercise real Arena episodes, PPO, and exact CPU continuation after restore.

Run in an environment containing this training package and Arena. This is a
bounded implementation acceptance probe, not a policy-quality benchmark.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import random
import time

import numpy as np
import torch

from gakumas_training.algorithms import PPOConfig
from gakumas_training.encoding import DecisionEncoder
from gakumas_training.models import ModelConfig, PolicyRunner, PolicyValueNet
from gakumas_training.runtime.config import RunConfig
from gakumas_training.runtime.trainer import Trainer
from gakumas_training.tasks import ExamScoreTask, FullProduceTask


def states(model):
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


def fingerprint():
    package = Path(__file__).resolve().parents[1] / 'gakumas_training'
    files = {p.relative_to(package).as_posix(): sha256(p.read_bytes()).hexdigest()
             for p in sorted(package.rglob('*')) if p.suffix in {'.py', '.json'}}
    return sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def assert_state_equal(left, right):
    if isinstance(left, torch.Tensor):
        if not torch.equal(left.cpu(), right.cpu()):
            raise AssertionError('Optimizer tensor differs after restore')
    elif isinstance(left, dict):
        if left.keys() != right.keys():
            raise AssertionError('Optimizer keys differ after restore')
        for key in left:
            assert_state_equal(left[key], right[key])
    elif isinstance(left, (tuple, list)):
        if len(left) != len(right):
            raise AssertionError('Optimizer sequence differs after restore')
        for a, b in zip(left, right, strict=True):
            assert_state_equal(a, b)
    elif left != right:
        raise AssertionError('Optimizer scalar differs after restore')


def probe(name, output, arena_root=None):
    started = time.perf_counter()
    source_hash = fingerprint()
    random.seed(431)
    np.random.seed(431)
    torch.manual_seed(431)
    task = (FullProduceTask if name == 'full_produce' else ExamScoreTask)(arena_root=arena_root)
    model_config = ModelConfig(width=32, token_dim=8)
    config = RunConfig(task=name, seed=91030000, episodes_per_update=1,
                       score_scale=50000. if name == 'full_produce' else 150000.,
                       eval_every_updates=0, model=asdict(model_config),
                       ppo=PPOConfig(epochs=1, minibatch_size=16, microbatch_size=2))

    def make():
        encoder = DecisionEncoder(max_nodes=model_config.max_nodes)
        model = PolicyValueNet(model_config)
        return Trainer(task=task, encoder=encoder, model=model,
                       policy_runner=PolicyRunner(encoder, model), config=config,
                       output=output / name, arena_version=task.arena_version)

    try:
        trainer = make()
        initial = states(trainer.model)
        print(f'{name}: collecting and updating real Arena episode', flush=True)
        metrics = trainer.train(1)[0]
        updated = states(trainer.model)
        changed = [key for key in initial if not torch.equal(initial[key], updated[key])]
        if not changed:
            raise AssertionError('No model parameters changed')
        expected_episodes = trainer.collect()
        max_nodes = max(t.selection.encoded.node_count for e in expected_episodes for t in e.transitions)
        trainer.updater.update(expected_episodes, task=name, policy_version=trainer.policy_version,
                               score_scale=config.score_scale)
        expected_model = states(trainer.model)
        expected_optimizer = deepcopy(trainer.updater.optimizer.state_dict())
        print(f'{name}: restoring and reproducing next episode and update', flush=True)
        restored = make().resume(trainer.checkpoint_path)
        actual_episodes = restored.collect()
        if len(actual_episodes) != len(expected_episodes):
            raise AssertionError('Restored episode count differs')
        for left, right in zip(expected_episodes, actual_episodes, strict=True):
            if (left.seed, left.raw_score, left.termination) != (right.seed, right.raw_score, right.termination):
                raise AssertionError('Restored game result differs')
            if len(left.transitions) != len(right.transitions):
                raise AssertionError('Restored decision count differs')
            for a, b in zip(left.transitions, right.transitions, strict=True):
                if a != b:
                    raise AssertionError('Restored public state, action, encoding or probability differs')
        restored.updater.update(actual_episodes, task=name, policy_version=restored.policy_version,
                                score_scale=config.score_scale)
        actual_model = states(restored.model)
        if any(not torch.equal(expected_model[k], actual_model[k]) for k in expected_model):
            raise AssertionError('Restored next optimizer update differs')
        assert_state_equal(expected_optimizer, restored.updater.optimizer.state_dict())
        if source_hash != fingerprint():
            raise AssertionError('Training source changed during acceptance; rerun against frozen source')
        return {'task': name, 'passed': True, 'seconds': time.perf_counter() - started,
                'first_update': metrics, 'parameter_tensors_changed': len(changed),
                'parameter_count': sum(p.numel() for p in trainer.model.parameters()),
                'training_source_sha256': source_hash,
                'next_episode_exact': True, 'next_update_parameters_exact': True,
                'next_optimizer_state_exact': True,
                'next_episode_scores': [e.raw_score for e in actual_episodes],
                'next_episode_terminations': [e.termination for e in actual_episodes],
                'next_episode_max_nodes': max_nodes, 'arena_version': task.arena_version,
                'checkpoint': str(trainer.checkpoint_path.resolve()),
                'scope': 'real configured Arena episodes; no synthetic score or course override; CPU only',
                'policy_quality_improvement_proven': False}
    finally:
        task.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', choices=['full_produce', 'exam_score', 'both'], default='both')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arena-root', type=Path)
    args = parser.parse_args()
    torch.set_num_threads(1)
    args.output.mkdir(parents=True, exist_ok=True)
    tasks = ['exam_score', 'full_produce'] if args.task == 'both' else [args.task]
    report = {'schema': 'gakumas-training-acceptance/1', 'tasks': []}
    for name in tasks:
        report['tasks'].append(probe(name, args.output, args.arena_root))
        (args.output / 'acceptance.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
