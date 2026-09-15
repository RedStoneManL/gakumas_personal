"""Bounded training and held-out evaluation entry points for independent tasks."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import random

import numpy as np
import torch

from .contracts import TASK_NAMES
from .device import resolve_device, seed_device
from .runtime import RunConfig, Trainer


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True, choices=sorted(TASK_NAMES))
    p.add_argument("--config", type=Path, help="JSON config; unknown fields are rejected")
    p.add_argument("--updates", type=int, default=1, help="Additional complete PPO updates (default: 1)")
    p.add_argument("--episodes-per-update", type=int)
    p.add_argument("--seed", type=int, help="Training seed, or held-out seed with --evaluate")
    p.add_argument("--output", type=Path, required=True, help="Root; each task gets its own subdirectory")
    p.add_argument("--resume", nargs="?", const="latest", help="Resume latest, or a specific checkpoint path")
    p.add_argument("--device", help="cpu, cuda[:N], or npu[:N]; no silent CPU fallback")
    p.add_argument("--arena-root", type=Path, help="Independent Arena checkout root")
    p.add_argument("--evaluate", action="store_true", help="Greedy held-out evaluation without training")
    p.add_argument("--checkpoint", type=Path, help="Evaluation checkpoint (default: task latest)")
    p.add_argument("--episodes", type=int, help="Episode count for --evaluate")
    return p


def default_config(task):
    """Read package data so editable installs and wheels use identical defaults."""
    return json.loads((Path(__file__).with_name("configs") / f"{task}.json").read_text(encoding="utf-8"))


def main(argv=None):
    args = parser().parse_args(argv)
    if args.evaluate and args.resume:
        raise ValueError("Use --checkpoint with --evaluate, or --resume with training")
    if not args.evaluate and (args.checkpoint is not None or args.episodes is not None):
        raise ValueError("--checkpoint and --episodes require --evaluate")
    output = args.output.resolve() / args.task
    checkpoint = args.checkpoint or output / "checkpoints" / "latest.pt"
    resume_path = (output / "checkpoints" / "latest.pt" if args.resume == "latest"
                   else Path(args.resume) if args.resume else None)
    # Without an explicit config, a resume/evaluation reconstructs its exact
    # immutable training config from the checkpoint, then validates it on load.
    restore_path = checkpoint if args.evaluate else resume_path
    if args.config:
        data = json.loads(args.config.read_text(encoding="utf-8-sig"))
    elif restore_path:
        data = torch.load(restore_path, map_location="cpu", weights_only=True)["config"]
    else:
        data = default_config(args.task)
    if data.get("task", args.task) != args.task:
        raise ValueError("--task and config/checkpoint task disagree")
    data["task"] = args.task
    if args.device is not None:
        data["device"] = args.device
    if args.episodes_per_update is not None:
        if args.evaluate:
            raise ValueError("--episodes-per-update is a training option")
        data["episodes_per_update"] = args.episodes_per_update
    if args.seed is not None and not args.evaluate:
        data["seed"] = args.seed
    config = RunConfig.from_dict(data)
    resolve_device(config.device)
    torch.set_num_threads(config.torch_threads)
    random.seed(config.seed)
    np.random.seed(config.seed % 2**32)
    seed_device(config.seed, config.device)
    from .encoding import DecisionEncoder, Vocabulary
    from .encoding.graph import ENCODING_VERSION
    from .models import ModelConfig, PolicyRunner, PolicyValueNet
    from .tasks import ExamScoreConfig, ExamScoreTask, FullProduceConfig, FullProduceTask
    model_config = ModelConfig(**config.model)
    config = replace(config, model=asdict(model_config))
    task_cls, task_config_cls = ((FullProduceTask, FullProduceConfig) if args.task == "full_produce"
                                else (ExamScoreTask, ExamScoreConfig))
    task_config = task_config_cls(**config.task_config)
    config = replace(config, task_config=asdict(task_config))
    task = task_cls(task_config, arena_root=args.arena_root)
    try:
        encoder = DecisionEncoder(Vocabulary(capacity=model_config.vocab_capacity),
                                  max_nodes=model_config.max_nodes)
        model = PolicyValueNet(model_config).to(config.device)
        runner = PolicyRunner(encoder, model)
        trainer = Trainer(task=task, encoder=encoder, model=model, policy_runner=runner,
            config=config, output=output, arena_version=task.arena_version,
            model_schema="gakumas-candidate-graph-policy/1", encoding_schema=ENCODING_VERSION)
        if args.evaluate:
            trainer.resume(checkpoint)
            trainer.config = replace(config,
                eval_episodes=args.episodes if args.episodes is not None else config.eval_episodes,
                eval_seed=args.seed if args.seed is not None else config.eval_seed)
            result = trainer.evaluate()
            print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
            return result
        if resume_path:
            trainer.resume(resume_path)
        return trainer.train(args.updates)
    finally:
        task.close()


def entrypoint():
    # Console-script wrappers pass the return value to sys.exit().
    main()
    return 0


if __name__ == "__main__":
    raise SystemExit(entrypoint())
