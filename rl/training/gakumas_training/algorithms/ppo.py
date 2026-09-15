"""On-policy PPO-Clip with undiscounted, whole-episode Monte Carlo targets.

There is no GAE, reward shaping, replay, score clipping, or log-score transform.
The value target of every decision is the authoritative final raw score / C.
"""
from __future__ import annotations

from dataclasses import dataclass
import gc
import json
import math
import random
from typing import Any, Sequence

import torch
from torch.nn import functional as F

from ..contracts import Episode, TASK_NAMES
from ..device import (capture_retry_rng, restore_retry_rng, empty_accelerator_cache,
                      is_accelerator_oom, model_device, optimizer_options)


def _rng_state():
    return capture_retry_rng()


def _restore_rng(state):
    restore_retry_rng(state)


def _release_oom_memory():
    gc.collect()
    empty_accelerator_cache()


@dataclass(frozen=True)
class PPOConfig:
    learning_rate: float = 3e-5
    adam_eps: float = 1e-5
    epochs: int = 2
    minibatch_size: int = 64
    microbatch_size: int = 4
    clip: float = 0.2
    target_kl: float = 0.015
    max_grad_norm: float = 0.5
    value_coefficient: float = 0.5
    entropy_coefficient: float = 0.01
    # Setup choices use the same sampled policy and raw terminal return. Only
    # their entropy bonus is stronger; likelihoods are never replaced by an
    # unrecorded random-action mixture.
    setup_entropy_coefficient: float = 0.05
    normalize_advantage: bool = True
    behavior_tolerance: float = 2e-5
    gamma: float = 1.0

    def __post_init__(self):
        for name in ("learning_rate", "adam_eps", "target_kl", "max_grad_norm", "behavior_tolerance"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.gamma != 1:
            raise ValueError("Only undiscounted gamma=1 is supported")
        if not 0 < self.clip < 1:
            raise ValueError("PPO clip must lie in (0, 1)")
        if any(getattr(self, k) <= 0 for k in ("epochs", "minibatch_size", "microbatch_size")):
            raise ValueError("Epoch and batch sizes must be positive")
        if any(not math.isfinite(getattr(self, k)) or getattr(self, k) < 0
               for k in ("value_coefficient", "entropy_coefficient", "setup_entropy_coefficient")):
            raise ValueError("Loss coefficients must be finite and nonnegative")


def validate_rollout(episodes: Sequence[Episode], *, task: str, policy_version: int,
                     score_scale: float) -> None:
    if task not in TASK_NAMES or not episodes:
        raise ValueError("A nonempty rollout from one supported task is required")
    if not math.isfinite(score_scale) or score_scale <= 0:
        raise ValueError("The fixed score scale must be finite and positive")
    for episode in episodes:
        if episode.task != task:
            raise ValueError("Cannot train on another task's trajectory")
        if not math.isfinite(episode.raw_score) or not episode.termination:
            raise ValueError("Every episode must have a finite raw score and actual termination")
        for transition in episode.transitions:
            d, s = transition.decision, transition.selection
            if d.task != task or s.policy_version != policy_version:
                raise ValueError("Rollout task/policy version does not match the learner")
            if not 0 <= s.action_index < len(d.candidates):
                raise ValueError("Stored action is not in the legal candidate list")
            if s.encoded is None or not math.isfinite(s.log_prob) or not math.isfinite(s.value):
                raise ValueError("Missing encoded state or nonfinite behavior likelihood/value")
    if not any(e.transitions for e in episodes):
        raise ValueError("No decisions in the rollout")


class PPOUpdater:
    def __init__(self, model: Any, config: PPOConfig | None = None, optimizer=None):
        self.model = model
        self.config = config or PPOConfig()
        self.optimizer = optimizer if optimizer is not None else torch.optim.Adam(
            model.parameters(), lr=self.config.learning_rate, eps=self.config.adam_eps,
            **optimizer_options(model))
        self.effective_microbatch_size = self.config.microbatch_size
        self.last_oom_fallbacks = []

    def _fallback(self, attempted, *, stage, **position):
        self.effective_microbatch_size = max(1, attempted // 2)
        kind = "npu" if model_device(self.model).type == "npu" else "cuda"
        event = {"event": f"{kind}_oom_retry", "component": "ppo", "stage": stage,
                 "attempted_microbatch_size": attempted,
                 "effective_microbatch_size": self.effective_microbatch_size, **position}
        self.last_oom_fallbacks.append(event)
        print(json.dumps(event, sort_keys=True), flush=True)

    def _parity_block(self, block):
        ev = self.model.evaluate([t.selection.encoded for t, _ in block],
                                 action_indices=[t.selection.action_index for t, _ in block])
        old = ev.log_probs.new_tensor([t.selection.log_prob for t, _ in block])
        error = (ev.log_probs - old).abs()
        if not torch.isfinite(error).all():
            raise FloatingPointError("Nonfinite behavior likelihood parity")
        return float(error.max()), ev.entropy.detach().cpu().tolist()

    def _accumulate_minibatch(self, rows, indices, active, setup, advantages, has_setup, denominator=None):
        """No optimizer mutation here; a failed attempt can be discarded whole."""
        cfg = self.config
        denominator = denominator if denominator is not None else len(indices)
        totals = dict(loss=0., policy_loss=0., value_loss=0., entropy=0., kl_sum=0., kl_count=0, clipped=0)
        kind_updates = []
        for offset in range(0, len(indices), self.effective_microbatch_size):
            ii = indices[offset:offset + self.effective_microbatch_size]
            block = [rows[i] for i in ii]
            ev = self.model.evaluate([t.selection.encoded for t, _ in block],
                                     action_indices=[t.selection.action_index for t, _ in block])
            old = ev.log_probs.new_tensor([t.selection.log_prob for t, _ in block])
            target = ev.values.new_tensor([ret for _, ret in block])
            mask = active[ii].to(ev.log_probs.device)
            adv = advantages[ii].to(ev.log_probs.device)
            log_ratio = ev.log_probs - old
            ratio = log_ratio.exp()
            clipped = ratio.clamp(1 - cfg.clip, 1 + cfg.clip)
            policy = -(torch.minimum(ratio * adv, clipped * adv) * mask).sum() / denominator
            value = F.smooth_l1_loss(ev.values, target, reduction="sum") / denominator
            entropy = (ev.entropy * mask).sum() / denominator
            loss = policy + cfg.value_coefficient * value - cfg.entropy_coefficient * entropy
            if has_setup:
                setup_mask = setup[ii].to(ev.log_probs.device) & mask
                setup_entropy = (ev.entropy * setup_mask).sum() / denominator
                loss = loss - (cfg.setup_entropy_coefficient - cfg.entropy_coefficient) * setup_entropy
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite PPO loss")
            loss.backward()
            for name, val in (("loss", loss), ("policy_loss", policy), ("value_loss", value), ("entropy", entropy)):
                totals[name] += float(val.detach())
            all_kvals = ((ratio - 1) - log_ratio).detach()
            kvals = all_kvals[mask]
            totals["kl_sum"] += float(kvals.sum())
            totals["kl_count"] += len(kvals)
            totals["clipped"] += int(((ratio - 1).abs() > cfg.clip)[mask].sum())
            for (transition, _), entropy_value, kl_value in zip(
                    block, ev.entropy.detach().cpu().tolist(), all_kvals.cpu().tolist()):
                count = len(transition.decision.candidates)
                if count > 1:
                    kind_updates.append((transition.decision.kind, entropy_value, kl_value, count))
        return totals, kind_updates

    def update(self, episodes: Sequence[Episode], *, task: str, policy_version: int,
               score_scale: float, mesh=None) -> dict[str, Any]:
        from .. import distributed
        if mesh is None and distributed.ACTIVE is not None and distributed.ACTIVE.size > 1:
            return distributed.ACTIVE.update(self, episodes,
                dict(task=task, policy_version=policy_version, score_scale=score_scale))
        validate_rollout(episodes, task=task, policy_version=policy_version, score_scale=score_scale)
        rows = [(t, e.raw_score / score_scale) for e in episodes for t in e.transitions]
        cfg, n = self.config, len(rows)
        self.effective_microbatch_size = cfg.microbatch_size
        self.last_oom_fallbacks = []
        active = torch.tensor([len(t.decision.candidates) > 1 for t, _ in rows])
        setup = torch.tensor([t.decision.kind.startswith("setup_") for t, _ in rows])
        has_setup = bool(setup.any())
        kind_metrics = {}
        for transition, _ in rows:
            kind, count = transition.decision.kind, len(transition.decision.candidates)
            values = kind_metrics.setdefault(kind, {"rollout_samples": 0, "meaningful_samples": 0,
                "candidate_count_sum": 0, "candidate_count_min": count, "candidate_count_max": count,
                "behavior_normalized_entropy_sum": 0., "optimization_samples": 0,
                "optimization_normalized_entropy_sum": 0., "optimization_approx_kl_sum": 0.})
            values["rollout_samples"] += 1
            values["meaningful_samples"] += int(count > 1)
            values["candidate_count_sum"] += count
            values["candidate_count_min"] = min(values["candidate_count_min"], count)
            values["candidate_count_max"] = max(values["candidate_count_max"], count)
        advantages = torch.tensor([ret - t.selection.value for t, ret in rows], dtype=torch.float32)
        if cfg.normalize_advantage and int(active.sum()) > 1:
            a = advantages[active]
            # A zero-variance batch still has a useful unnormalized gradient.
            if float(a.std(unbiased=False)) > 1e-8:
                advantages = (advantages - a.mean()) / a.std(unbiased=False)
        self.model.train()
        # Check the complete frozen behavior before the first optimizer mutation.
        # This catches wrong sampling distributions and stale/mixed weights.
        max_parity_error = 0.0
        with torch.no_grad():
            start = 0
            while start < n:
                block = rows[start:start + self.effective_microbatch_size]
                state = _rng_state()
                try:
                    error, entropies = self._parity_block(block)
                except RuntimeError as error:
                    if not is_accelerator_oom(error, model_device(self.model)) or len(block) <= 1:
                        raise
                    error.__traceback__ = None
                    _restore_rng(state)
                    _release_oom_memory()
                    self._fallback(len(block), stage="behavior_parity", rollout_start=start)
                    continue
                max_parity_error = max(max_parity_error, error)
                for (transition, _), entropy in zip(block, entropies):
                    count = len(transition.decision.candidates)
                    kind_metrics[transition.decision.kind]["behavior_normalized_entropy_sum"] += (
                        entropy / math.log(count) if count > 1 else 0.)
                start += len(block)
        if max_parity_error > cfg.behavior_tolerance:
            raise ValueError(f"Frozen behavior likelihood mismatch: {max_parity_error:.6g}")

        order = list(range(n))
        logs, stop_reason = [], None
        for epoch in range(cfg.epochs):
            if mesh is None:
                random.shuffle(order)
            else:
                mesh.shuffle(order)
            epoch_kl_sum = epoch_kl_count = 0
            for start in range(0, n, cfg.minibatch_size):
                indices = order[start:start + cfg.minibatch_size]
                state = _rng_state()
                while True:
                    self.optimizer.zero_grad(set_to_none=True)
                    try:
                        if mesh is None:
                            totals, kind_updates = self._accumulate_minibatch(
                                rows, indices, active, setup, advantages, has_setup)
                        else:
                            totals, kind_updates = self._accumulate_minibatch(
                                rows, indices[mesh.rank::mesh.size], active, setup, advantages,
                                has_setup, denominator=len(indices))
                        break
                    except RuntimeError as error:
                        if not is_accelerator_oom(error, model_device(self.model)):
                            raise
                        self.optimizer.zero_grad(set_to_none=True)
                        attempted = min(self.effective_microbatch_size, len(indices))
                        if attempted <= 1:
                            raise
                        # Drop the failed helper frame/activations before asking
                        # The accelerator releases cached blocks before retry.
                        # No optimizer step ran.
                        error.__traceback__ = None
                        _restore_rng(state)
                        _release_oom_memory()
                        self._fallback(attempted, stage="gradient_accumulation", epoch=epoch, minibatch_start=start)
                if mesh is not None:
                    totals = mesh.sum_values(totals)
                    kind_updates = mesh.gather_lists(kind_updates)
                for kind, entropy_value, kl_value, count in kind_updates:
                    metric = kind_metrics[kind]
                    metric["optimization_samples"] += 1
                    metric["optimization_normalized_entropy_sum"] += entropy_value / math.log(count)
                    metric["optimization_approx_kl_sum"] += kl_value
                kl = totals["kl_sum"] / max(1, totals["kl_count"])
                epoch_kl_sum += totals["kl_sum"]
                epoch_kl_count += totals["kl_count"]
                if kl > 2 * cfg.target_kl:
                    self.optimizer.zero_grad(set_to_none=True)
                    stop_reason = "minibatch_kl"
                    break
                if mesh is not None:
                    mesh.gradients(self.model)
                grad = torch.nn.utils.clip_grad_norm_(self.model.parameters(), cfg.max_grad_norm,
                    error_if_nonfinite=True, **optimizer_options(self.model))
                self.optimizer.step()
                logs.append({k: totals[k] for k in ("loss", "policy_loss", "value_loss", "entropy")} |
                            {"kl": kl, "grad_norm_before_clip": float(grad),
                             "clip_fraction": totals["clipped"] / max(1, totals["kl_count"])})
            if stop_reason:
                break
            if epoch_kl_sum / max(1, epoch_kl_count) > cfg.target_kl:
                stop_reason = "epoch_kl"
                break
        if not logs:
            raise RuntimeError("PPO made no optimizer update")
        for kind, metric in kind_metrics.items():
            metric["candidate_count_mean"] = metric.pop("candidate_count_sum") / metric["rollout_samples"]
            metric["behavior_normalized_entropy"] = metric.pop("behavior_normalized_entropy_sum") / max(1, metric["meaningful_samples"])
            metric["normalized_entropy"] = metric.pop("optimization_normalized_entropy_sum") / max(1, metric["optimization_samples"])
            metric["approx_kl"] = metric.pop("optimization_approx_kl_sum") / max(1, metric["optimization_samples"])
            metric["entropy_coefficient"] = (cfg.setup_entropy_coefficient if kind.startswith("setup_")
                                             else cfg.entropy_coefficient)
        return {k: sum(row[k] for row in logs) / len(logs) for k in logs[0]} | {
            "optimizer_steps": len(logs), "epochs_started": epoch + 1,
            "learner_world_size": mesh.size if mesh is not None else 1,
            "transitions": n, "meaningful_decisions": int(active.sum()),
            "behavior_parity_max_error": max_parity_error,
            "effective_microbatch_size": self.effective_microbatch_size,
            "oom_fallback_count": len(self.last_oom_fallbacks),
            "oom_fallbacks": list(self.last_oom_fallbacks),
            "kl_stop_reason": stop_reason,
            "score_scale": score_scale, "gamma": 1.0,
            "decision_kinds": kind_metrics,
            "decision_kind_metric_scope": "pre-step optimization observations, including a KL-rejected minibatch; rollout_samples count unique stored decisions",
        }
