from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from .checkpoint import load, save, json_write, source_version, digest
from .encoding import encode, collate
from .environment import Workers
from .ppo import update
from .report import write_report


def append(path, row):
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def entry_hash(entry):
    return hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_config(c):
    if c["gamma"] != 1 or c["score_scale"] <= 0:
        raise ValueError("pilot uses gamma=1 and a fixed positive score scale")
    for key in ("workers", "target_decisions", "batch_decisions", "max_episode_decisions", "minibatch", "epochs", "eval_episodes", "eval_every_batches"):
        if not isinstance(c[key], int) or c[key] < 1:
            raise ValueError(f"invalid positive integer {key}")
    if c["eval_seed_base"] < 1000000 or not c["card_counts"]:
        raise ValueError("invalid evaluation split or empty curriculum")
    if c["eval_seed_base"] + c["eval_episodes"] > 3000000:
        raise ValueError("validation seeds overlap the final test namespace")
    if c["max_minutes"] <= 0 or c["learning_rate"] <= 0 or c["target_kl"] <= 0:
        raise ValueError("time, learning rate and target KL must be positive")


def learning_config(config):
    # Stop budgets can be extended for overnight continuation without resetting Adam.
    return {k: v for k, v in config.items() if k not in {'name', 'max_minutes', 'target_decisions'}}


def choose(model, examples, device, values=True, greedy=False):
    b = collate(examples, device)
    with torch.no_grad():
        if values:
            logits, v = model(b)
        else:
            logits, v = model.policy(b), torch.zeros(len(examples), device=device)
        d = torch.distributions.Categorical(logits=logits)
        action = logits.argmax(-1) if greedy else d.sample()
        if not torch.isfinite(d.log_prob(action)).all() or not torch.isfinite(v).all():
            raise FloatingPointError("invalid policy output")
        return action.tolist(), d.log_prob(action).tolist(), v.tolist()


def collect(pool, model, config, device, episode_index, output):
    active, records, finished = {}, [], []
    meaningful = raw = 0
    last_progress = time.monotonic()

    def reset(i):
        nonlocal episode_index
        if episode_index >= 1000000:
            raise ValueError("training seed namespace exhausted")
        seed = episode_index
        count = config["card_counts"][episode_index % len(config["card_counts"]) ]
        episode_index += 1
        pool.send(i, "reset", (count, seed))
        row = pool.receive(i)
        if row['observation']['result']['truncated'] or row['observation']['result']['terminated']:
            raise RuntimeError("reset did not provide a live decision state")
        active[i] = {"obs": row["observation"], "records": [], "submissions": [],
                     "seed": seed, "entry": row["entry"], "entry_sha256": entry_hash(row["entry"])}

    for i in range(config["workers"]):
        reset(i)
    while active:
        worker_ids = list(active)
        encoded = [encode(active[i]["obs"]) for i in worker_ids]
        selected, old_logp, old_value = choose(model, encoded, device)
        for n, i in enumerate(worker_ids):
            e = encoded[n]
            row = active[i]
            command = e.submissions[selected[n]]
            row["records"].append({"encoded": e, "action": selected[n],
                                   "old_logp": old_logp[n], "old_value": old_value[n]})
            row["submissions"].append(command)
            pool.send(i, "step", command)
            meaningful += len(e.submissions) > 1
            raw += 1
        for i in worker_ids:
            row = active[i]
            obs = pool.receive(i)["observation"]
            row["obs"] = obs
            result = obs["result"]
            if result["truncated"]:
                raise RuntimeError("unexpected truncation; no terminal return fabricated")
            if result["terminated"]:
                score = result["final_score"]
                if score is None or not math.isfinite(score):
                    raise ValueError("invalid authoritative terminal score")
                for r in row["records"]:
                    r["return"] = score / config["score_scale"]
                records.extend(row["records"])
                summary = {k: row[k] for k in ("seed", "entry", "entry_sha256", "submissions")}
                summary.update(score=score, decisions=len(row["records"]))
                append(output / "episodes.jsonl", summary)
                finished.append({"score": score, "decisions": len(row["records"])})
                del active[i]
            elif len(row["records"]) >= config["max_episode_decisions"]:
                raise RuntimeError("episode decision guard reached; this is not a game terminal")
        # Freeze the actor until every started episode has completed.
        if meaningful < config["batch_decisions"] and raw < config["batch_decisions"] * 20:
            for i in range(config["workers"]):
                if i not in active:
                    reset(i)
        if time.monotonic() - last_progress >= 30:
            print(json.dumps({"event": "collecting", "meaningful_decisions": meaningful,
                              "completed_episodes": len(finished), "active_episodes": len(active)}), flush=True)
            last_progress = time.monotonic()
    if meaningful == 0:
        raise RuntimeError("no meaningful decisions in the collected batch")
    return records, finished, meaningful, episode_index


def evaluate(pool, model, config, device, driver="policy", seed_base=None):
    pending = list(range(config["eval_episodes"]))
    active, results = {}, []
    base = config["eval_seed_base"] if seed_base is None else seed_base
    while pending or active:
        for i in range(config["workers"]):
            if i not in active and pending:
                index = pending.pop(0)
                seed = base + index
                count = config["card_counts"][index % len(config["card_counts"]) ]
                pool.send(i, "reset", (count, seed))
                row = pool.receive(i)
                active[i] = {"obs": row["observation"], "seed": seed,
                             "entry_sha256": entry_hash(row["entry"]), "steps": 0,
                             "rng": random.Random(seed + 5000000)}
        ids = list(active)
        examples = [encode(active[i]["obs"]) for i in ids]
        if driver == "policy":
            selected, _, _ = choose(model, examples, device, values=False, greedy=True)
        elif driver == "random":
            selected = [active[i]["rng"].randrange(len(e.submissions)) for i, e in zip(ids, examples)]
        elif driver == "first_legal":
            selected = [0] * len(ids)
        else:
            raise ValueError(driver)
        for i, e, a in zip(ids, examples, selected):
            pool.send(i, "step", e.submissions[a])
        for i in ids:
            row = active[i]
            row["obs"] = pool.receive(i)["observation"]
            row["steps"] += 1
            r = row["obs"]["result"]
            if r["truncated"]:
                raise RuntimeError("evaluation was truncated")
            if r["terminated"]:
                if r["final_score"] is None or not math.isfinite(r["final_score"]):
                    raise ValueError("invalid evaluation terminal score")
                results.append({"seed": row["seed"], "entry_sha256": row["entry_sha256"],
                                "score": r["final_score"], "decisions": row["steps"]})
                del active[i]
            elif row["steps"] >= config["max_episode_decisions"]:
                raise RuntimeError("evaluation episode guard reached")
    scores = sorted(r["score"] for r in results)
    sd = statistics.stdev(scores) if len(scores) > 1 else 0.0
    return {"driver": driver, "mean": statistics.mean(scores), "std": sd,
            "mean_se": sd / math.sqrt(len(scores)), "minimum": scores[0],
            "p10_empirical": scores[int((len(scores) - 1) * .1)],
            "episodes": sorted(results, key=lambda r: r["seed"])}


def paired_gain(candidate, baseline):
    left, right = candidate["episodes"], baseline["episodes"]
    if [(r["seed"], r["entry_sha256"]) for r in left] != [(r["seed"], r["entry_sha256"]) for r in right]:
        raise ValueError("paired comparison requires matching seeds and entries")
    gains = [a["score"] - b["score"] for a, b in zip(left, right)]
    se = statistics.stdev(gains) / math.sqrt(len(gains)) if len(gains) > 1 else 0.0
    return {"mean": statistics.mean(gains), "mean_se": se, "episodes": len(gains),
            "positive_pairs": sum(g > 0 for g in gains)}


def train(arena, binding, config, initial, output, resume=None, warm_start=None):
    if resume and warm_start:
        raise ValueError('choose resume or warm_start, not both')
    validate_config(config)
    device = config["device"]
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA required by config; CPU fallback is not automatic")
    torch.set_num_threads(2)
    random.seed(config["seed"]); torch.manual_seed(config["seed"])
    model, ckpt = load(resume or warm_start or initial, device)
    expected_source = source_version()
    if binding["rl_source_sha256"] != expected_source or (not warm_start and ckpt.get("rl_source_sha256") != expected_source):
        raise ValueError("weights/binding use different RL code; prepare and verify again")
    if warm_start and (ckpt.get('kind') != 'trained' or ckpt.get('arena_sha256') != binding['effective_sha256']):
        raise ValueError('warm start requires trained weights from the same Arena version')
    reference_path = Path(warm_start or initial).resolve()
    initial_reference = ckpt.get('initial_reference') if resume else None
    if initial_reference is None:
        initial_reference = {'path': str(reference_path), 'sha256': digest(reference_path),
                             'kind': 'transferred_trained_weights' if warm_start else 'untrained'}
    if digest(initial_reference['path']) != initial_reference['sha256']:
        raise ValueError('starting policy reference changed')
    transfer = ({'path': str(reference_path), 'sha256': digest(reference_path),
                 'rl_source_sha256': ckpt['rl_source_sha256'],
                 'training_config': ckpt.get('training_config'),
                 'optimizer_reset': True, 'statistics_reset': True}
                if warm_start else ckpt.get('warm_start_from'))
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"], eps=config["adam_eps"])
    steps, batches, episode_index, best = 0, 0, 0, -math.inf
    if resume:
        if ckpt.get("arena_sha256") != binding["effective_sha256"]:
            raise ValueError("resume requires the same Arena version")
        if ckpt.get("rl_source_sha256") != source_version() or learning_config(ckpt.get("training_config", {})) != learning_config(config):
            raise ValueError("resume requires unchanged trainer/encoding/config")
        optimizer.load_state_dict(ckpt["optimizer_state"])
        steps, batches, episode_index = ckpt["decisions"], ckpt["batches"], ckpt["next_episode_index"]
        best = ckpt["best_validation_mean"]
        torch.set_rng_state(ckpt["torch_rng"]); random.setstate(ckpt["python_rng"])
        if ckpt["cuda_rng"] and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(ckpt["cuda_rng"])
    elif not warm_start and (ckpt.get("kind") != "initialized" or ckpt.get("decisions", 0) != 0):
        raise ValueError("use --resume or --warm-start for trained weights")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"arena": str(Path(arena).resolve()), "binding": binding, "config": config,
                "initial": str(Path(initial).resolve()), "resume_from": str(resume) if resume else None,
                "initial_reference": initial_reference, "warm_start_from": transfer,
                "rl_source_sha256": expected_source,
                "torch": torch.__version__, "cuda": torch.version.cuda,
                "objective": "expected authoritative final score; gamma=1; no resource rewards",
                "scope": "bounded Arena course; no claim of full real-game HIF calibration"}
    json_write(output / "manifest.json", manifest)
    if resume:
        previous_baseline = Path(resume).parent / 'baseline.json'
        if previous_baseline.is_file():
            shutil.copy2(previous_baseline, output / 'baseline.json')
        previous_best = Path(resume).parent / "best.pt"
        if previous_best.is_file():
            _, best_info = load(previous_best, "cpu")
            if best_info.get("arena_sha256") != binding["effective_sha256"] or best_info.get("rl_source_sha256") != expected_source:
                raise ValueError("resume best checkpoint has incompatible provenance")
            shutil.copy2(previous_best, output / "best.pt")
        else:
            best = -math.inf  # This new run has no preserved selection checkpoint.
    pool = Workers(config["workers"], arena, binding["effective_sha256"])
    started = time.monotonic()
    progress_state = {'run': config.get('name', ''), 'status': 'running',
                      'started_at': datetime.now(timezone.utc).isoformat(),
                      'max_minutes': config['max_minutes'], 'target_decisions': config['target_decisions']}

    def publish(event, **details):
        progress_state.update(event=event, updated_at=datetime.now(timezone.utc).isoformat(),
                              elapsed_minutes=(time.monotonic() - started) / 60,
                              batches=batches, decisions=steps, **details)
        json_write(output / 'progress.json', progress_state)
        line = (f"[{datetime.now().strftime('%H:%M:%S')}] {event} | batch={batches} decisions={steps} "
                f"elapsed={progress_state['elapsed_minutes']:.1f}m")
        if event == 'update':
            line += f" | train_mean={details['train_mean']:.0f}"
        if 'validation_mean' in details:
            line += f" | validation={details['validation_mean']:.0f} best={best:.0f}"
        if 'gain_vs_start' in details:
            gain = details['gain_vs_start']
            line += f" | vs_start={gain['mean']:+.0f} SE={gain['mean_se']:.0f} better={gain['positive_pairs']}/{gain['episodes']}"
        with (output / 'progress.log').open('a', encoding='utf-8') as f:
            f.write(line + '\n')
        print(line, flush=True)

    def checkpoint(name):
        if source_version() != expected_source:
            raise ValueError("RL source changed; refusing to stamp new source onto an old in-memory model")
        save(output / name, model, optimizer, kind="trained" if steps else ("warm_started" if transfer else "initialized"),
             decisions=steps, batches=batches, next_episode_index=episode_index,
             arena_sha256=binding["effective_sha256"], training_config=config,
             best_validation_mean=best, initial_reference=initial_reference, warm_start_from=transfer)

    checkpoint("latest.pt")
    try:
        publish('starting')
        if not resume:
            initial_eval = evaluate(pool, model, config, device)
            random_eval = evaluate(pool, model, config, device, "random")
            json_write(output / "baseline.json", {"initialized": initial_eval, "random": random_eval,
                                                  "initialization": initial_reference})
            best = initial_eval["mean"]
            checkpoint("best.pt")
            publish('baseline', validation_mean=best, baseline_mean=best, random_mean=random_eval['mean'])
            print(json.dumps({"event": "baseline", "initial_mean": best, "random_mean": random_eval["mean"]}), flush=True)
        elif not (output / "best.pt").exists():
            best = evaluate(pool, model, config, device)["mean"]
            checkpoint("best.pt")
        if not (output / 'baseline.json').exists():
            reference_model, _ = load(initial_reference['path'], device)
            baseline_eval = evaluate(pool, reference_model, config, device)
            del reference_model
            json_write(output / 'baseline.json', {'initialized': baseline_eval,
                       'random': evaluate(pool, model, config, device, 'random'), 'initialization': initial_reference})
        baseline = json.loads((output / 'baseline.json').read_text(encoding='utf-8'))
        checkpoint("latest.pt")
        while steps < config["target_decisions"] and time.monotonic() - started < config["max_minutes"] * 60:
            before = time.monotonic()
            records, episodes, added, episode_index = collect(pool, model, config, device, episode_index, output)
            collection_seconds = time.monotonic() - before
            if source_version() != expected_source:
                raise ValueError("RL source changed mid-run; last completed checkpoint preserved")
            before = time.monotonic()
            losses = update(model, optimizer, records, config, device)
            steps += added; batches += 1
            row = {"event": "update", "batch": batches, "decisions": steps,
                   "episodes": len(episodes), "train_mean": statistics.mean(r["score"] for r in episodes),
                   "collection_seconds": collection_seconds, "update_seconds": time.monotonic() - before,
                   **losses}
            append(output / "metrics.jsonl", row)
            checkpoint("latest.pt")
            publish('update', train_mean=row['train_mean'], losses=losses,
                    collection_seconds=collection_seconds, update_seconds=row['update_seconds'])
            print(json.dumps(row), flush=True)
            if batches % config["eval_every_batches"] == 0 or steps >= config["target_decisions"]:
                evaluation = evaluate(pool, model, config, device)
                evaluation['gain_vs_start'] = paired_gain(evaluation, baseline['initialized'])
                evaluation['gain_vs_random'] = paired_gain(evaluation, baseline['random'])
                json_write(output / f"validation-{batches:04}.json", evaluation)
                if evaluation["mean"] > best:
                    best = evaluation["mean"]; checkpoint("best.pt")
                checkpoint("latest.pt")
                publish('validation', validation_mean=evaluation['mean'], validation_mean_se=evaluation['mean_se'],
                        best_validation_mean=best, baseline_mean=baseline['initialized']['mean'],
                        gain_vs_start=evaluation['gain_vs_start'], gain_vs_random=evaluation['gain_vs_random'],
                        validation_p10=evaluation['p10_empirical'], validation_minimum=evaluation['minimum'])
                print(json.dumps({"event": "validation", "batch": batches, "mean": evaluation["mean"], "best": best}), flush=True)
        # Separate final test seeds; repeated validation was used for selection.
        final_eval = evaluate(pool, model, config, device, seed_base=3000000)
        if digest(initial_reference['path']) != initial_reference['sha256']:
            raise ValueError('starting policy reference changed during training')
        initial_model, _ = load(initial_reference['path'], device)
        initial_test = evaluate(pool, initial_model, config, device, seed_base=3000000)
        del initial_model
        random_test = evaluate(pool, model, config, device, "random", seed_base=3000000)
        best_model, _ = load(output / "best.pt", device)
        best_test = evaluate(pool, best_model, config, device, seed_base=3000000)
        del best_model
        json_write(output / "final_test.json", {"latest": final_eval, "initialized": initial_test,
                   "initialization": initial_reference,
                   "random": random_test, "best_validation": best_test,
                   "gain_vs_initialized": paired_gain(final_eval, initial_test),
                   "gain_vs_random": paired_gain(final_eval, random_test),
                   "selection": "best chosen on validation; final test is held out from selection"})
        checkpoint("latest.pt")
        json_write(output / "status.json", {"status": "complete", "decisions": steps,
                   "batches": batches, "elapsed_seconds": time.monotonic() - started,
                   "stop_reason": "decision_target" if steps >= config["target_decisions"] else "time_budget_at_batch_boundary"})
        write_report(output)
        publish('complete', status='complete', final_test_mean=final_eval['mean'],
                final_gain_vs_start=paired_gain(final_eval, initial_test),
                final_gain_vs_random=paired_gain(final_eval, random_test))
        print(json.dumps({"event": "complete", "report": str(output / "REPORT.md"),
                          "latest_test_mean": final_eval["mean"], "random_test_mean": random_test["mean"]}), flush=True)
    except BaseException as error:
        # Keep the last fully completed update. Never overwrite it with partial work.
        json_write(output / "status.json", {"status": "interrupted_or_failed", "error": repr(error),
                   "latest_complete_batch": batches, "resume": str(output / "latest.pt")})
        publish('failed', status='interrupted_or_failed', error=repr(error))
        raise
    finally:
        pool.close()
