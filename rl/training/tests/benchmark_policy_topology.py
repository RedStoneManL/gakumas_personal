"""Short real-Arena GPU parity/latency probe; no episodes or optimizer updates.

Run with the training/Arena packages and GPU PyTorch installed:
  python tests/benchmark_policy_topology.py --output topology-probe.json
The legacy branch uses the same weights/operators with dynamic topology indexing.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch
from torch.distributions import Categorical

from gakumas_training.arena_adapter.environment import ensure_arena, close_arena
from gakumas_training.arena_adapter.setup_observation import prepare_setup_observation
from gakumas_training.contracts import DecisionContext
from gakumas_training.encoding import DecisionEncoder, collate
from gakumas_training.models import ModelConfig, PolicyValueNet


def real_examples():
    ensure_arena()
    from gakumas_arena.env import get_repository
    from gakumas_arena.engine.training import TrainingExam, hif_round2_entry
    repository = get_repository()
    root = Path(__file__).parents[1]
    base = json.loads((root / "colab/configs/full_produce.json").read_text())["task_config"]["loadout"]
    levels = {"SupportCardRarity_Ssr": 60, "SupportCardRarity_Sr": 50, "SupportCardRarity_R": 40}
    supports = [{"id": "setup:support:" + row["id"], "support_card_id": row["id"], "level": levels[row["rarity"]]}
                for row in repository.support_cards.rows if row["planType"] in ("ProducePlanType_Plan1", "ProducePlanType_Common")]
    setup = prepare_setup_observation(repository, base_loadout=base, support_options=supports,
        memory_options=[], selected_supports=[], selected_memories=[], phase="support", slot=0, rules={})
    encoder = DecisionEncoder()
    large = encoder.encode(DecisionContext("full_produce", "setup_support", setup,
        tuple({"type": "select_support", "support_ref": row["id"]} for row in supports)))
    exam = TrainingExam(hif_round2_entry(), seed=719)
    public = exam.observe()
    small = encoder.encode(DecisionContext("exam_score", "exam_action", {"exam": public}, tuple(public["actions"])))
    return large, small


def run_case(model, examples, iterations):
    fast = collate(examples, device="cuda")
    old = {key: value for key, value in fast.items() if key not in ("tree_levels", "node_slices")}
    stats = {"nodes": [e.node_count for e in examples], "tree_depth": fast["max_depth"], "paths": {}}
    chosen = torch.zeros(len(examples), dtype=torch.long, device="cuda")
    results, gradients = {}, {}
    for name, batch in (("legacy", old), ("precomputed", fast)):
        with torch.no_grad():
            for _ in range(3):
                model(batch)
            torch.cuda.synchronize()
            times = []
            for _ in range(iterations):
                start = time.perf_counter()
                model(batch)
                torch.cuda.synchronize()
                times.append(time.perf_counter() - start)
            with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]) as profiler:
                model(batch)
                torch.cuda.synchronize()
        events = {event.key: event.count for event in profiler.key_averages()
                  if "nonzero" in event.key or "unique" in event.key or "Synchronize" in event.key}
        model.zero_grad(set_to_none=True)
        logits, values = model(batch)
        dist = Categorical(logits=logits)
        logp = dist.log_prob(chosen)
        loss = -logp.mean() + .01 * values.square().mean() - .001 * dist.entropy().mean()
        loss.backward()
        torch.cuda.synchronize()
        results[name] = (logits.detach(), values.detach(), logp.detach())
        gradients[name] = {key: p.grad.detach().cpu().clone() for key, p in model.named_parameters() if p.grad is not None}
        stats["paths"][name] = {"median_forward_ms": statistics.median(times) * 1000, "profile_events": events}
    for current, legacy in zip(results["precomputed"], results["legacy"]):
        torch.testing.assert_close(current, legacy, atol=2e-5, rtol=2e-5)
    gap = float((results["precomputed"][2] - results["legacy"][2]).abs().max())
    if gap > 2e-5:
        raise AssertionError(f"Behavior log-probability changed by {gap}")
    for key, current in gradients["precomputed"].items():
        torch.testing.assert_close(current, gradients["legacy"][key], atol=2e-6, rtol=3e-5)
    stats["max_log_prob_difference"] = gap
    stats["max_gradient_difference"] = max(float((g - gradients["legacy"][key]).abs().max())
                                           for key, g in gradients["precomputed"].items())
    stats["parameter_gradient_count"] = len(gradients["precomputed"])
    stats["forward_speedup"] = stats["paths"]["legacy"]["median_forward_ms"] / stats["paths"]["precomputed"]["median_forward_ms"]
    stats["passed"] = True
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--iterations", type=int, default=8)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("This short probe requires an actual GPU")
    torch.set_num_threads(1)
    torch.manual_seed(81102)
    try:
        large, small = real_examples()
        model = PolicyValueNet(ModelConfig()).cuda()
        initial = deepcopy(model.state_dict())
        report = {"scope": "Local short model forward/backward only; not Colab or end-to-end training",
            "gpu": torch.cuda.get_device_name(), "torch": torch.__version__,
            "tf32_matmul": torch.backends.cuda.matmul.allow_tf32,
            "tf32_cudnn": torch.backends.cudnn.allow_tf32, "amp": False,
            "iterations": args.iterations, "cases": {}}
        for name, examples in (("exam_batch2", [small, small]), ("mixed_batch4", [large, small, large, small])):
            report["cases"][name] = run_case(model, examples, args.iterations)
        model.load_state_dict(initial, strict=True)
        report["checkpoint_strict_load_passed"] = True
        root = Path(__file__).parents[1]
        report["source_sha256"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in (
            "gakumas_training/models/policy.py", "gakumas_training/encoding/graph.py")}
        report["passed"] = True
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2), flush=True)
    finally:
        close_arena()


if __name__ == "__main__":
    main()
