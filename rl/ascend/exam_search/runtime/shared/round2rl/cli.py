from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
import torch

from .checkpoint import digest, json_write, load, save, source_version
from .encoding import ENCODING, encode, collate
from .model import PolicyValue, MODEL_SCHEMA
from .runner import train, evaluate, validate_config

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARENA = ROOT.parents[1] / "third_party/gakumas_arena"
INITIAL = ROOT / "artifacts/initial/seed42.pt"
BINDING = ROOT / "artifacts/arena_binding.json"


def runtime():
    data = {"torch": torch.__version__, "cuda_build": torch.version.cuda,
            "cuda_available": torch.cuda.is_available()}
    if torch.cuda.is_available():
        data.update(gpu=torch.cuda.get_device_name(0), capability=list(torch.cuda.get_device_capability(0)))
    return data


def initialize():
    torch.manual_seed(42)
    random.seed(42)
    model = PolicyValue()
    if INITIAL.exists():
        old = torch.load(INITIAL, map_location="cpu", weights_only=True)
        if old.get("kind") != "initialized" or old.get("decisions") != 0:
            raise ValueError("refusing to overwrite a trained initial-weight file")
    save(INITIAL, model, kind="initialized", decisions=0, seed=42, arena_binding=None)
    meta = {"kind": "initialized_not_trained", "path": str(INITIAL), "sha256": digest(INITIAL),
            "model_schema": MODEL_SCHEMA, "encoding": ENCODING, "config": model.config,
            "parameters": sum(p.numel() for p in model.parameters()),
            "bytes": INITIAL.stat().st_size, "rl_source_sha256": source_version(),
            "arena_bound": False, "runtime": runtime()}
    json_write(INITIAL.with_suffix(".json"), meta)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


def offline_check(device):
    from .ppo import update
    torch.set_num_threads(2)
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable in the selected runtime")
    before = digest(INITIAL)
    model, info = load(INITIAL, device)
    examples = json.loads((ROOT / "fixtures/public_probe.json").read_text(encoding="utf-8"))["observations"]
    encoded = [encode(o) for o in examples]
    start = time.perf_counter()
    batch = collate(encoded, device)
    logits, values = model(batch)
    d = torch.distributions.Categorical(logits=logits)
    actions = logits.argmax(-1)
    old = d.log_prob(actions).detach()
    ratio = (torch.distributions.Categorical(logits=model(batch)[0]).log_prob(actions) - old).exp()
    assert torch.allclose(ratio, torch.ones_like(ratio), atol=1e-5)
    assert torch.isfinite(values).all()
    assert torch.equal(d.probs[~batch["mask"]], torch.zeros_like(d.probs[~batch["mask"]]))
    records = [{"encoded": e, "action": a, "old_logp": float(lp), "old_value": float(v),
                "return": 0.25 + 0.25 * i} for i, (e, a, lp, v) in enumerate(zip(encoded, actions.tolist(), old.tolist(), values.detach().tolist()))]
    config = json.loads((ROOT / "configs/trial.json").read_text(encoding="utf-8"))
    # Exercise the configured minibatch size, not just a single observation.
    records = [dict(records[i % len(records)]) for i in range(config["minibatch"])]
    del logits, values, d, ratio, batch
    config.update(epochs=1)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"], eps=config["adam_eps"])
    losses = update(model, optimizer, records, config, device)
    if device == "cuda":
        torch.cuda.synchronize()
    assert digest(INITIAL) == before
    report = {"status": "passed", "scope": "archived public observations and synthetic returns only; no Arena calls or RL rollout training",
              "initial_weights_unchanged": True, "fixture_sha256": digest(ROOT / "fixtures/public_probe.json"),
              "fixture_engine_version": examples[0]["version"], "runtime": runtime(),
              "elapsed_seconds": time.perf_counter() - start,
              "entities": [e.entity_count for e in encoded], "atoms": [len(e.atoms) for e in encoded],
              "legal_actions": [len(e.submissions) for e in encoded], "optimizer_test": losses,
              "synthetic_minibatch": len(records),
              "parameters": sum(p.numel() for p in model.parameters()),
              "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None}
    json_write(ROOT / "artifacts/offline_check.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def bind(arena):
    """Run only when the updated Arena has been handed over. No model training."""
    from .environment import arena_module, submit
    from .course import entry_for
    api = arena_module(arena)
    version = api.content_version()
    config = json.loads((ROOT / "configs/trial.json").read_text(encoding="utf-8"))
    rows = []
    try:
        for i, count in enumerate(config["card_counts"]):
            entry = entry_for(api, count, 4000000+i)
            exam = api.create_training_exam(entry, seed=4000000+i)
            if count == 22:
                json_write(ROOT / 'artifacts/course_reference_entry.json', entry)
            driver = random.Random(5000000+i)
            for step in range(config["max_episode_decisions"]):
                obs = exam.observe()
                if obs["version"]["effective_sha256"] != version["effective_sha256"]:
                    raise ValueError("Arena changed during verification")
                if obs["result"]["truncated"]:
                    raise ValueError("verification truncated")
                if obs["result"]["terminated"]:
                    rows.append({"card_count": count, "decisions": step, "entry": entry,
                                 "result": obs["result"], "context": obs["context"],
                                 "entry_source": entry["source"], "preset": entry["preset"]})
                    break
                encoded = encode(obs)
                submit(exam, driver.choice(encoded.submissions))
            else:
                raise ValueError("Arena verification exceeded decision guard")
        binding = {"effective_sha256": version["effective_sha256"], "version": version,
                   "arena": str(Path(arena).resolve()), "rl_source_sha256": source_version(),
                   "scope": "public software contract and bounded v2 course episodes using the pinned golden",
                   "rows": rows, "created_at_unix": time.time()}
        json_write(BINDING, binding)
        print(json.dumps({"status": "bound", "path": str(BINDING), "episodes": len(rows), "effective_sha256": version["effective_sha256"]}, indent=2))
    finally:
        api.close_training_worker()


def evaluate_checkpoint(arena, binding, config, path, output):
    from .environment import Workers
    validate_config(config)
    torch.set_num_threads(2)
    model, info = load(path, config["device"])
    if info["rl_source_sha256"] != source_version():
        raise ValueError("evaluation checkpoint uses different RL code")
    if info.get("arena_sha256", binding["effective_sha256"]) != binding["effective_sha256"]:
        raise ValueError("evaluation checkpoint was trained on a different Arena version")
    output.mkdir(parents=True, exist_ok=False)
    pool = Workers(config["workers"], arena, binding["effective_sha256"])
    try:
        result = evaluate(pool, model, config, config["device"], seed_base=3000000)
        json_write(output / "evaluation.json", {"checkpoint": str(path.resolve()), "binding": binding,
                   "config": config, "results": result})
        print(json.dumps({"mean": result["mean"], "mean_se": result["mean_se"], "output": str(output)}, indent=2))
    finally:
        pool.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "check", "bind", "train", "evaluate"])
    parser.add_argument("--arena", type=Path, default=DEFAULT_ARENA)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/trial.json")
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--output", type=Path)
    starts = parser.add_mutually_exclusive_group()
    starts.add_argument("--resume", type=Path)
    starts.add_argument("--warm-start", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()
    if args.command == "init":
        initialize()
    elif args.command == "check":
        offline_check(args.device)
    elif args.command == "bind":
        bind(args.arena)
    else:
        if not BINDING.exists():
            raise RuntimeError("New Arena is not bound. Run VerifyArena after its handoff.")
        binding = json.loads(BINDING.read_text(encoding="utf-8"))
        if binding["rl_source_sha256"] != source_version():
            raise ValueError("RL code changed after binding; run VerifyArena again")
        config = json.loads(args.config.read_text(encoding="utf-8"))
        output = args.output or ROOT / "runs" / time.strftime("%Y%m%d-%H%M%S")
        if args.command == "evaluate":
            if args.checkpoint is None:
                raise ValueError("evaluate requires --checkpoint")
            evaluate_checkpoint(args.arena, binding, config, args.checkpoint, output)
        else:
            train(args.arena, binding, config, INITIAL, output, args.resume, args.warm_start)


if __name__ == "__main__":
    main()
