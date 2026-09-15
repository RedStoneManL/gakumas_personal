"""Real Arena + encoder + model device probe before a persistent Colab run.

Creates no training checkpoint. The full-produce game uses first-legal decisions
and can normally fail; this is an execution probe, not a quality benchmark.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def runtime_probe(device, allow_cpu=False):
    if sys.version_info < (3, 11):
        raise RuntimeError("Python >= 3.11 is required")
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js >= 20 is required")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    if match is None or int(match[1]) < 20:
        raise RuntimeError(f"Node.js >= 20 is required, found {version}")
    import torch
    from gakumas_training.device import resolve_device, device_report
    torch_version = re.match(r"(\d+)\.(\d+)", torch.__version__)
    if torch_version is None or tuple(map(int, torch_version.groups())) < (2, 5):
        raise RuntimeError("The inherited PyTorch must be >= 2.5; this notebook never replaces CUDA/PyTorch")
    if device == "cpu" and not allow_cpu:
        raise RuntimeError("CPU probes require explicit --allow-cpu-smoke")
    # Resolve also registers torch_npu before any torch.device('npu') call.
    resolved = resolve_device(device)
    if resolved.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable; select a GPU runtime in Colab")
    report = {"python": sys.version, "node": version, **device_report(device),
              "cuda_runtime": torch.version.cuda, "device": device,
              "cuda_available": torch.cuda.is_available()}
    if torch.device(device).type == "cuda":
        report["gpu"] = torch.cuda.get_device_name(device)
        report["gpu_total_bytes"] = torch.cuda.get_device_properties(device).total_memory
        torch.cuda.reset_peak_memory_stats(device)
    elif resolved.type == "npu":
        torch.npu.reset_peak_memory_stats(device)
    return report


def probe_batch_capacity(model, encoded, requested, device):
    """Bound startup probing; CUDA activation OOM reduces only the probe batch."""
    import gc
    import torch
    from gakumas_training.device import is_accelerator_oom, empty_accelerator_cache
    count = min(requested, 32)
    attempts = []

    def forward_backward(size):
        model.zero_grad(set_to_none=True)
        result = model.evaluate([encoded] * size, [0] * size)
        loss = -result.log_probs.mean() + result.values.square().mean() - .01 * result.entropy.mean()
        loss.backward()
        if (not torch.isfinite(loss) or any(not torch.isfinite(p.grad).all()
                for p in model.parameters() if p.grad is not None)):
            raise RuntimeError('Batch forward/backward produced non-finite values')

    while True:
        try:
            forward_backward(count)
            break
        except RuntimeError as error:
            if not is_accelerator_oom(error, device) or count <= 1:
                raise
            attempts.append(count)
        model.zero_grad(set_to_none=True)
        gc.collect()
        empty_accelerator_cache()
        count = max(1, count // 2)
        print(json.dumps({'event': 'preflight_batch_reduced', 'graphs': count}), flush=True)
    return {'requested_graphs': requested, 'graphs': count, 'probe_cap': 32,
            'nodes_per_graph': encoded.node_count, 'oom_attempts': attempts,
            'forward_backward_finite': True,
            'scope': 'Bounded startup probe; learner separately adapts CUDA OOM at runtime'}


def probe_task(task_name, config_data, *, arena_root, device):
    import torch
    from gakumas_training.contracts import PolicySelection
    from gakumas_training.encoding import DecisionEncoder, Vocabulary
    from gakumas_training.models import ModelConfig, PolicyValueNet
    from gakumas_training.tasks import ExamScoreConfig, ExamScoreTask, FullProduceConfig, FullProduceTask
    configuration = ModelConfig(**config_data.get("model", {}))
    encoder = DecisionEncoder(Vocabulary(capacity=configuration.vocab_capacity), max_nodes=configuration.max_nodes)
    task_cls, task_config = ((FullProduceTask, FullProduceConfig) if task_name == "full_produce"
                            else (ExamScoreTask, ExamScoreConfig))
    task = task_cls(task_config(**config_data.get("task_config", {})), arena_root=arena_root)
    kinds = Counter()
    by_kind = {}
    first = last = largest = None
    peak = edges = candidates = projected = 0
    encode_seconds = 0.
    started = time.perf_counter()

    def policy(context):
        nonlocal first, last, largest, peak, edges, candidates, projected, encode_seconds
        start = time.perf_counter()
        encoded = encoder.encode(context)
        encode_seconds += time.perf_counter() - start
        kinds[context.kind] += 1
        if first is None:
            first = (context.kind, encoded)
        last = (context.kind, encoded)
        if largest is None or encoded.node_count > largest[1].node_count:
            largest = (context.kind, encoded)
        if context.kind not in by_kind or encoded.node_count > by_kind[context.kind].node_count:
            by_kind[context.kind] = encoded
        peak = max(peak, encoded.node_count)
        edges = max(edges, len(encoded.edges))
        candidates = max(candidates, len(context.candidates))
        projected = max(projected, encoder.last_report.get("buff_projection", {}).get("projected_sources", 0))
        index = next((i for i, candidate in enumerate(context.candidates)
                      if context.kind == "exam_action" and candidate.get("type") == "play"), 0)
        # This is an engine/encoding probe, not a behavior-policy PPO trajectory.
        return PolicySelection(index, 0., 0., 0)

    try:
        episode = task.run_episode(policy, seed=791031, policy_version=0)
        if first is None or not math.isfinite(episode.raw_score):
            raise RuntimeError("Probe did not produce a finite real episode with decisions")
        model = PolicyValueNet(configuration).to(device)
        model.train()
        # Cover every observed decision interface, including each setup component.
        # Cover semantic interfaces singly, then the actual configured batch size.
        selected = {id(encoded): (kind, encoded) for kind, encoded in
                    [first, largest, last, *sorted(by_kind.items())]}
        forward_start = time.perf_counter()
        model_probes = []
        for kind, encoded in selected.values():
            model.zero_grad(set_to_none=True)
            result = model.evaluate([encoded], [0])
            if not torch.isfinite(result.values).all() or not torch.isfinite(result.log_probs).all():
                raise RuntimeError(f"Non-finite policy/value forward result: {kind}")
            loss = -result.log_probs.mean() + result.values.square().mean() - .01 * result.entropy.mean()
            loss.backward()
            gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
            if not gradients or not all(torch.isfinite(gradient).all() for gradient in gradients):
                raise RuntimeError(f"Non-finite or missing model gradients: {kind}")
            magnitude = sum(float(gradient.detach().abs().sum()) for gradient in gradients)
            if magnitude <= 0:
                raise RuntimeError(f"The probe produced no model gradient: {kind}")
            model_probes.append({"decision_kind": kind, "nodes": encoded.node_count,
                                 "candidates": len(encoded.action_nodes), "gradient_abs_sum": magnitude})
        batch_size = max(config_data.get('workers', 1),
                         config_data.get('ppo', {}).get('microbatch_size', 2))
        batch_probe = probe_batch_capacity(model, largest[1], batch_size, device)
        gradient_sum = sum(probe["gradient_abs_sum"] for probe in model_probes)
        from gakumas_training.device import synchronize
        synchronize(device)
        return {"task": task_name, "real_episode_raw_score": episode.raw_score,
                "termination": episode.termination, "decision_kinds": dict(kinds),
                "decisions": sum(kinds.values()), "peak_nodes": peak, "peak_edges": edges,
                "peak_candidates": candidates, "max_projected_support_sources": projected,
                "vocabulary_size": len(encoder.vocabulary.tokens), "model": asdict(configuration),
                "setup_mode": episode.metadata.get("setup_mode"),
                "model_checked_decision_kinds": sorted({probe["decision_kind"] for probe in model_probes}),
                "model_probes": model_probes,
                "configured_batch_probe": batch_probe,
                "gradient_abs_sum": gradient_sum, "forward_backward_seconds": time.perf_counter()-forward_start,
                "encode_seconds": encode_seconds, "elapsed_seconds": time.perf_counter()-started,
                "full_success_route_proven": False, "policy_quality_proven": False,
                "arena_version": task.arena_version}
    finally:
        task.close()


def profile_probe_configs(config_data):
    """Cover all profiles × setup modes, independently of the probe seed."""
    pool = config_data.get("task_config", {}).get("loadout_pool")
    if pool is None:
        profiles = [(None, deepcopy(config_data))]
    elif not isinstance(pool, list) or not pool:
        raise ValueError("loadout_pool must be a nonempty profile list")
    else:
        profiles = []
        for profile in pool:
            data = deepcopy(config_data)
            data["task_config"].update(loadout_pool=None, loadout=deepcopy(profile["loadout"]),
                                       research_config=deepcopy(profile.get("research_config", {})))
            profiles.append((profile["name"], data))
    result = []
    for name, data in profiles:
        mode = data.get("task_config", {}).get("setup_mode", "given")
        for setup_mode in (("given", "select") if mode == "mixed" else (mode,)):
            explicit = deepcopy(data)
            explicit.setdefault("task_config", {})["setup_mode"] = setup_mode
            result.append((name, explicit))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, help="The exact selected training configuration")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--allow-cpu-smoke", action="store_true")
    args = parser.parse_args(argv)
    root = args.bundle_root.resolve()
    sys.path.insert(0, str(root / "training"))
    report = {"schema": "hif-colab-preflight/1", "passed": False,
              "scope": "Executed on this runtime; no policy-quality or full-game coverage claim"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        manifest = root / "manifest.json"
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        if metadata.get("schema") != "hif-colab-training/1":
            raise ValueError("Preflight requires the new training bundle")
        report["manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
        report["runtime"] = runtime_probe(args.device, args.allow_cpu_smoke)
        selected_config = args.config or root / "configs" / "full_produce.json"
        selected_data = json.loads(selected_config.read_text(encoding="utf-8"))
        report["selected_config_sha256"] = hashlib.sha256(selected_config.read_bytes()).hexdigest()
        import torch
        torch.set_num_threads(2)
        report["tasks"] = []
        for task in ("exam_score", "full_produce"):
            config = (selected_data if selected_data.get("task") == task else
                      json.loads((root / "configs" / f"{task}.json").read_text(encoding="utf-8")))
            if config.get("task") != task:
                raise ValueError("Bundle task and config disagree")
            profiles = profile_probe_configs(config) if task == "full_produce" else [(None, config)]
            for profile, profile_config in profiles:
                mode = profile_config.get("task_config", {}).get("setup_mode", "n/a")
                print(f"Preflight: {task} profile={profile or 'fixed'} setup={mode} real Arena episode + encoder + forward/backward ({args.device})", flush=True)
                result = probe_task(task, profile_config, arena_root=root/"arena", device=args.device)
                result["loadout_profile"] = profile
                report["tasks"].append(result)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if torch.device(args.device).type == "cuda":
            report["peak_gpu_allocated_bytes"] = torch.cuda.max_memory_allocated(args.device)
        elif torch.device(args.device).type == "npu":
            report["peak_npu_allocated_bytes"] = torch.npu.max_memory_allocated(args.device)
        report["passed"] = True
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
