from __future__ import annotations

from collections import Counter
import copy
from dataclasses import replace
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any

import torch

from ..algorithms import PPOUpdater, validate_rollout
from ..contracts import CONTRACT_VERSION
from .checkpoint import (CHECKPOINT_SCHEMA, atomic_json, capture_rng, load_checkpoint,
                         restore_rng, save_checkpoint)
from .config import RunConfig, initial_execution_settings, validate_execution_settings


def append_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


def episode_summary(episodes):
    scores = [float(e.raw_score) for e in episodes]
    if not scores or not all(math.isfinite(s) for s in scores):
        raise ValueError("No finite completed episode scores")
    result = {"episodes": len(scores), "raw_score_mean": statistics.mean(scores),
            "raw_score_min": min(scores), "raw_score_max": max(scores),
            "raw_score_std": statistics.stdev(scores) if len(scores) > 1 else 0.,
            "terminations": dict(Counter(e.termination for e in episodes)),
            "decisions": sum(len(e.transitions) for e in episodes)}

    def grouped_summary(subset):
        return {'episodes': len(subset),
                'raw_score_mean': statistics.mean(float(e.raw_score) for e in subset),
                'terminations': dict(Counter(e.termination for e in subset)),
                'decisions': sum(len(e.transitions) for e in subset)}

    def mode_summaries(subset):
        modes = sorted({e.metadata['setup_mode'] for e in subset if e.metadata.get('setup_mode') is not None})
        return {mode: grouped_summary([e for e in subset if e.metadata.get('setup_mode') == mode])
                for mode in modes}

    modes = mode_summaries(episodes)
    if modes:
        result['setup_modes'] = modes
    names = sorted({e.metadata['loadout_profile'] for e in episodes
                    if e.metadata.get('loadout_profile') is not None})
    if names:
        result['loadout_profiles'] = {}
        for name in names:
            subset = [e for e in episodes if e.metadata.get('loadout_profile') == name]
            result['loadout_profiles'][name] = grouped_summary(subset)
            modes = mode_summaries(subset)
            if modes:
                result['loadout_profiles'][name]['setup_modes'] = modes
    # Count the committed setup selections by candidate identity. Given kits
    # have no setup actions and therefore never masquerade as policy choices.
    choices = {}
    for episode in episodes:
        for transition in episode.transitions:
            if not transition.decision.kind.startswith('setup_'):
                continue
            candidate = transition.decision.candidates[transition.selection.action_index]
            identity = next((candidate[key] for key in ('support_card_id', 'memory_id', 'support_ref', 'memory_ref', 'candidate_id', 'id')
                             if isinstance(candidate.get(key), str)), None)
            if identity is None:
                # This also represents an explicit finish/empty-slot candidate
                # without assuming its numeric candidate index is a global ID.
                identity = '<' + str(candidate.get('action_type', candidate.get('type', 'unidentified'))) + '>'
            choices.setdefault(transition.decision.kind, Counter())[identity] += 1
    if choices:
        result['setup_selection_counts'] = {kind: dict(counts) for kind, counts in choices.items()}
    equipped = {}
    for episode in episodes:
        if not any(key in episode.metadata for key in ('selected_support_ids', 'selected_memory_ids')):
            continue
        mode = episode.metadata.get('setup_mode', 'unspecified')
        values = equipped.setdefault(mode, {'episodes': 0, 'support_ids': Counter(), 'memory_ids': Counter()})
        values['episodes'] += 1
        for field, destination in (('selected_support_ids', 'support_ids'), ('selected_memory_ids', 'memory_ids')):
            values[destination].update(episode.metadata.get(field, []))
    if equipped:
        result['equipped_inventory_counts'] = {mode: {'episodes': values['episodes'],
            'support_ids': dict(values['support_ids']), 'memory_ids': dict(values['memory_ids'])}
            for mode, values in equipped.items()}
    return result


class Trainer:
    """One task, one model, one optimizer, one independent seed stream.

    ``output`` is the task-specific directory; the CLI adds the task name to the
    user-selected output root. A callback owns all Arena interaction.
    """

    def __init__(self, *, task, encoder, model, policy_runner, config: RunConfig,
                 output, arena_version: Any, model_schema="entity-policy-value-v1",
                 encoding_schema="public-decision-entities-v1"):
        self.task, self.encoder, self.model, self.policy_runner = task, encoder, model, policy_runner
        self.config, self.output = config, Path(output)
        self.arena_version = arena_version
        self.model_schema, self.encoding_schema = model_schema, encoding_schema
        self.updater = PPOUpdater(model, config.ppo)
        self._execution_settings = initial_execution_settings(config)
        self._pending_execution_settings = {}
        self.execution_control = None
        self.execution_control_state = {}
        self.last_batch_execution_settings = None
        self.iteration = self.policy_version = 0
        self.seed_cursor = config.seed
        self.decisions = self.episodes_seen = 0
        self.elapsed_seconds = 0.0
        self.output.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = self.output / "checkpoints" / "latest.pt"

    @property
    def execution_settings(self):
        return dict(self._execution_settings)

    @property
    def pending_execution_settings(self):
        return dict(self._pending_execution_settings)

    def apply_execution_settings(self, settings, *, stage="collection"):
        """Apply at a safe boundary without replacing model or optimizer state.

        At an update boundary only minibatch/microbatch sizes take effect;
        worker/episode changes are retained for the next collection boundary.
        The callback ``execution_control(stage, trainer)`` may call this method.
        """
        if stage not in ("collection", "update"):
            raise ValueError("Execution control stage must be collection or update")
        proposed = validate_execution_settings(settings, base={
            **self._execution_settings, **self._pending_execution_settings})
        if stage == "collection":
            actual, pending = proposed, {}
        else:
            actual = {**self._execution_settings,
                **{k: proposed[k] for k in ("minibatch_size", "microbatch_size")}}
            pending = {k: proposed[k] for k in ("workers", "episodes_per_update")
                       if proposed[k] != actual[k]}
        # Replace only the immutable updater configuration. Adam moments,
        # optimizer parameter references, model parameters and RNG are intact.
        updater_config = replace(self.config.ppo, minibatch_size=actual["minibatch_size"],
                                 microbatch_size=actual["microbatch_size"])
        self.updater.config = updater_config
        self._execution_settings, self._pending_execution_settings = actual, pending
        return self.execution_settings

    def _execution_boundary(self, stage):
        if stage == "collection":
            self.apply_execution_settings({}, stage=stage)
        if self.execution_control is not None:
            self.execution_control(stage, self)

    def resume(self, path=None):
        value = load_checkpoint(path or self.checkpoint_path, task=self.config.task,
            config=self.config.to_dict(), arena_version=self.arena_version,
            model_schema=self.model_schema, encoding_schema=self.encoding_schema)
        # Restore vocab before use of any encoded state. Never carry a rollout
        # across the checkpoint boundary; all subsequent episodes are fresh.
        self.encoder.load_state_dict(value["encoder_state"])
        self.model.load_state_dict(value["model_state"], strict=True)
        from ..device import load_optimizer_state
        load_optimizer_state(self.updater.optimizer, value["optimizer_state"], next(self.model.parameters()).device)
        self.apply_execution_settings(value["execution_settings"])
        self._pending_execution_settings = value["pending_execution_settings"]
        self.execution_control_state = copy.deepcopy(value["execution_control_state"])
        self.last_batch_execution_settings = value.get("last_batch_execution_settings")
        for name in ("iteration", "policy_version", "seed_cursor", "decisions", "episodes_seen", "elapsed_seconds"):
            setattr(self, name, value[name])
        restore_rng(value["rng"])
        return self

    def checkpoint(self):
        value = {"checkpoint_schema": CHECKPOINT_SCHEMA, "contract_schema": CONTRACT_VERSION,
            "task": self.config.task, "config": self.config.to_dict(),
            "arena_version": self.arena_version, "model_schema": self.model_schema,
            "encoding_schema": self.encoding_schema, "boundary": "after_complete_update",
            "iteration": self.iteration, "policy_version": self.policy_version,
            "seed_cursor": self.seed_cursor, "decisions": self.decisions,
            "episodes_seen": self.episodes_seen, "elapsed_seconds": self.elapsed_seconds,
            "execution_settings": self.execution_settings,
            "pending_execution_settings": self.pending_execution_settings,
            "execution_control_state": copy.deepcopy(self.execution_control_state),
            "last_batch_execution_settings": self.last_batch_execution_settings,
            "model_state": self.model.state_dict(), "optimizer_state": self.updater.optimizer.state_dict(),
            "encoder_state": self.encoder.state_dict(), "rng": capture_rng(),
            "torch_version": str(torch.__version__)}
        from ..distributed import world_size
        value['learner_world_size'] = world_size()
        save_checkpoint(self.checkpoint_path, value)
        save_checkpoint(self.checkpoint_path.with_name(f"update-{self.iteration:08d}.pt"), value)
        snapshots = sorted(self.checkpoint_path.parent.glob("update-????????.pt"))
        for obsolete in snapshots[:-3]:
            if obsolete.resolve().parent != self.checkpoint_path.parent.resolve():
                raise ValueError("Checkpoint retention path escaped its directory")
            obsolete.unlink()

    def collect(self):
        self._execution_boundary("collection")
        self.model.eval()
        version = self.policy_version
        count = self._execution_settings["episodes_per_update"]
        if (self.seed_cursor < self.config.eval_seed + self.config.eval_episodes and
                self.seed_cursor + count > self.config.eval_seed):
            raise ValueError("Training seed interval would overlap held-out evaluation seeds")
        episodes = self._collect_episodes(range(self.seed_cursor, self.seed_cursor + count),
                                           deterministic=False, namespace='training')
        validate_rollout(episodes, task=self.config.task, policy_version=version,
                         score_scale=self.config.score_scale)
        return episodes

    def _collect_episodes(self, seeds, *, deterministic, namespace):
        seeds = list(seeds)
        completed = 0
        settings = self.execution_settings
        workers = settings["workers"]

        def report(episode, seconds):
            nonlocal completed
            completed += 1
            print(json.dumps({'event': 'episode_collected' if namespace == 'training' else 'episode_evaluated',
                'task': self.config.task, 'namespace': namespace,
                'iteration': self.iteration, 'policy_version': self.policy_version,
                'completed': completed, 'target': len(seeds), 'workers': workers,
                'execution_settings': settings,
                'seed': episode.seed, 'loadout_profile': episode.metadata.get('loadout_profile'),
                'setup_mode': episode.metadata.get('setup_mode'),
                'raw_score': episode.raw_score, 'termination': episode.termination,
                'completed_scenarios': episode.metadata.get('completed_scenarios'),
                'accepted_exam_count': episode.metadata.get('accepted_exam_count'),
                'decisions': len(episode.transitions), 'seconds': seconds},
                ensure_ascii=False, allow_nan=False), flush=True)

        if workers > 1:
            from .parallel import SynchronousCollector
            collector = SynchronousCollector(self.task, self.policy_runner, workers=workers)
            return collector.collect(seeds, policy_version=self.policy_version,
                                     deterministic=deterministic, on_episode=report)
        episodes = []
        for seed in seeds:
            episode_started = time.perf_counter()
            if deterministic:
                policy = lambda context: self.policy_runner.act(
                    context, policy_version=self.policy_version, deterministic=True)
            else:
                policy = lambda context: self.policy_runner.act(context, policy_version=self.policy_version)
            episode = self.task.run_episode(policy, seed=seed, policy_version=self.policy_version)
            if episode.seed != seed:
                raise ValueError("Task returned an episode with the wrong seed")
            episodes.append(episode)
            report(episode, time.perf_counter() - episode_started)
        return episodes

    def evaluate(self):
        # Evaluation must not consume the training RNG sequence or alter the
        # training vocabulary: independent encoder snapshot, same trained model.
        rng, vocab = capture_rng(), copy.deepcopy(self.encoder.state_dict())
        controls_before = copy.deepcopy((self.execution_settings, self.pending_execution_settings,
                                         self.execution_control_state))
        was_training = self.model.training
        self.model.eval()
        started = time.perf_counter()
        timing_before = dict(getattr(self.policy_runner, "timing_counters", {}))
        try:
            self._execution_boundary("collection")
            if (self.config.seed < self.config.eval_seed + self.config.eval_episodes and
                    self.seed_cursor > self.config.eval_seed):
                raise ValueError("Evaluation seeds overlap already collected training episodes")
            episodes = self._collect_episodes(range(self.config.eval_seed, self.config.eval_seed + self.config.eval_episodes),
                                               deterministic=True, namespace='evaluation')
            result = {"task": self.config.task, "iteration": self.iteration,
                      "policy_version": self.policy_version, "namespace": "evaluation",
                      "execution_settings": self.execution_settings,
                      "seconds": time.perf_counter() - started,
                      "policy_timings": {key: value - timing_before.get(key, 0)
                                         for key, value in getattr(self.policy_runner, "timing_counters", {}).items()},
                      **episode_summary(episodes)}
            for episode in episodes:
                if episode.task != self.config.task:
                    raise ValueError("Evaluation returned a different task")
                self._episode_log(episode, namespace="evaluation")
            append_json(self.output / "evaluation" / "metrics.jsonl", result)
        finally:
            self.encoder.load_state_dict(vocab)
            restore_rng(rng)
            self.model.train(was_training)
        # Only a successful evaluation reaches here. Its control changes are a
        # safe same-iteration boundary after restoring all training RNG/vocab.
        # Never serialize from finally: a failed evaluation must retain the old
        # safe file. A first baseline uses initial.pt so train's fresh-run guard
        # does not mistake it for an existing completed training update.
        controls_after = (self.execution_settings, self.pending_execution_settings,
                          self.execution_control_state)
        latest = self.checkpoint_path
        initial = latest.with_name("initial.pt")
        if controls_before != controls_after and (latest.exists() or initial.exists()):
            try:
                if self.iteration == 0:
                    self.checkpoint_path = initial
                self.checkpoint()
            finally:
                self.checkpoint_path = latest
        return result

    def _episode_log(self, episode, *, namespace):
        append_json(self.output / namespace / "episodes.jsonl", {
            "task": episode.task, "seed": episode.seed, "iteration": self.iteration,
            "policy_version": (episode.transitions[0].selection.policy_version
                               if episode.transitions else self.policy_version),
            "raw_score": episode.raw_score, "termination": episode.termination,
            "decisions": len(episode.transitions), "metadata": episode.metadata})

    def train(self, updates: int):
        if updates < 1:
            raise ValueError("updates must be positive")
        if self.iteration == 0 and self.checkpoint_path.exists():
            raise FileExistsError("Output already contains a checkpoint; explicitly resume or choose a new output")
        manifest = {"config": self.config.to_dict(),
            "arena_version": self.arena_version, "contract_schema": CONTRACT_VERSION,
            "model_schema": self.model_schema, "encoding_schema": self.encoding_schema,
            "collection": ("single_worker_frozen_policy_complete_episodes" if self._execution_settings["workers"] == 1 else
                           "spawned_synchronous_waves_parent_batched_policy_complete_episodes"),
            "workers": self._execution_settings["workers"],
            "execution_settings": self.execution_settings,
            "reward": "zero intermediate; raw terminal score / fixed score_scale",
            "checkpoint_boundary": "after_complete_update"}
        manifest_path = self.output / "manifest.json"
        if manifest_path.exists():
            previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if "migration" in previous_manifest:
                manifest["migration"] = previous_manifest["migration"]
        atomic_json(manifest_path, manifest)
        results = []
        for _ in range(updates):
            started = time.perf_counter()
            try:
                timing_before = dict(getattr(self.policy_runner, "timing_counters", {}))
                episodes = self.collect()
                collection_settings = self.execution_settings
                collection_seconds = time.perf_counter() - started
                timing_after = dict(getattr(self.policy_runner, "timing_counters", {}))
                policy_timings = {key: value - timing_before.get(key, 0)
                                  for key, value in timing_after.items()}
                update_started = time.perf_counter()
                self._execution_boundary("update")
                batch_settings = {**collection_settings, **{k: self._execution_settings[k]
                    for k in ("minibatch_size", "microbatch_size")}}
                print(json.dumps({'event': 'update_started', 'task': self.config.task,
                    'iteration': self.iteration + 1, 'episodes': len(episodes),
                    'execution_settings': batch_settings,
                    'decisions': sum(len(e.transitions) for e in episodes)}), flush=True)
                losses = self.updater.update(episodes, task=self.config.task,
                    policy_version=self.policy_version, score_scale=self.config.score_scale)
                effective_micro = losses.get("effective_microbatch_size", batch_settings["microbatch_size"])
                self.apply_execution_settings({"microbatch_size": effective_micro}, stage="update")
                batch_settings["microbatch_size"] = effective_micro
                update_seconds = time.perf_counter() - update_started
                self.seed_cursor += len(episodes)
                self.episodes_seen += len(episodes)
                self.decisions += sum(len(e.transitions) for e in episodes)
                self.iteration += 1
                self.policy_version += 1
                self.elapsed_seconds += time.perf_counter() - started
                self.last_batch_execution_settings = batch_settings
                self.checkpoint()
                for episode in episodes:
                    self._episode_log(episode, namespace="training")
                result = {"task": self.config.task, "iteration": self.iteration,
                    "policy_version": self.policy_version, "seed_cursor": self.seed_cursor,
                    "execution_settings": batch_settings,
                    "pending_execution_settings": self.pending_execution_settings,
                    "collection_seconds": collection_seconds, "update_seconds": update_seconds,
                    "policy_timings": policy_timings,
                    "elapsed_training_seconds": self.elapsed_seconds,
                    "total_decisions": self.decisions, "total_episodes": self.episodes_seen,
                    **episode_summary(episodes), "ppo": losses}
                append_json(self.output / "training" / "metrics.jsonl", result)
                if self.config.eval_every_updates and self.iteration % self.config.eval_every_updates == 0:
                    result["evaluation"] = self.evaluate()
                atomic_json(self.output / "progress.json", {"status": "ready", **result})
                print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
                results.append(result)
            except BaseException as error:
                atomic_json(self.output / "progress.json", {"status": "failed", "task": self.config.task,
                    "iteration": self.iteration, "error_type": type(error).__name__, "error": str(error),
                    "last_safe_checkpoint": str(self.checkpoint_path) if self.checkpoint_path.exists() else None})
                raise
        return results
