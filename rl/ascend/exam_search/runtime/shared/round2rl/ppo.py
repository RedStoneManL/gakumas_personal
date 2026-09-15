"""Complete-episode, undiscounted masked PPO. Search data never enters this buffer."""
from __future__ import annotations

import math
import random
import torch
from .encoding import collate


def update(model, optimizer, records, config, device):
    if not records:
        raise ValueError("empty rollout")
    advantages = torch.tensor([r["return"] - r["old_value"] for r in records])
    # Constant scale across decision types; forced decisions have no actor loss.
    meaningful = torch.tensor([len(r["encoded"].submissions) > 1 for r in records])
    if meaningful.any():
        chosen = advantages[meaningful]
        advantages = (advantages - chosen.mean()) / chosen.std(unbiased=False).clamp_min(1e-6)
    order = list(range(len(records)))
    logs = []
    for _ in range(config["epochs"]):
        random.shuffle(order)
        epoch_kls = []
        for start in range(0, len(order), config["minibatch"]):
            indices = order[start:start + config["minibatch"]]
            rows = [records[i] for i in indices]
            batch = collate([r["encoded"] for r in rows], device)
            logits, values = model(batch)
            distribution = torch.distributions.Categorical(logits=logits)
            actions = torch.tensor([r["action"] for r in rows], device=device)
            old = torch.tensor([r["old_logp"] for r in rows], device=device)
            target = torch.tensor([r["return"] for r in rows], device=device)
            advantage = advantages[indices].to(device)
            log_ratio = distribution.log_prob(actions) - old
            ratio = log_ratio.exp()
            selected = meaningful[indices].to(device)
            clipped = ratio.clamp(1 - config["clip"], 1 + config["clip"])
            surrogate = torch.minimum(ratio * advantage, clipped * advantage)
            # Denominator is all sampled decisions, not each episode's length.
            policy_loss = -(surrogate * selected).mean()
            entropy = (distribution.entropy() * selected).mean()
            value_loss = (values - target).square().mean()
            loss = policy_loss + config["value_coefficient"] * value_loss - config["entropy"] * entropy
            if not torch.isfinite(loss):
                raise FloatingPointError("non-finite PPO loss")
            kl = ((ratio - 1) - log_ratio)[selected].mean().item() if selected.any() else 0.0
            epoch_kls.append((kl, int(selected.sum())))
            if kl > config["target_kl"] * 2:
                break
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            grad = torch.nn.utils.clip_grad_norm_(model.parameters(), config["max_grad"], error_if_nonfinite=True)
            optimizer.step()
            logs.append({"loss": loss.item(), "policy_loss": policy_loss.item(),
                         "value_loss": value_loss.item(), "entropy": entropy.item(),
                         "kl": kl, "grad_norm": float(grad)})
        mean_kl = sum(k * n for k, n in epoch_kls) / max(1, sum(n for _, n in epoch_kls))
        if mean_kl > config["target_kl"] or (epoch_kls and epoch_kls[-1][0] > config["target_kl"] * 2):
            break
    if not logs:
        raise RuntimeError("PPO stopped before any update; inspect policy/mask parity")
    return {k: sum(r[k] for r in logs) / len(logs) for k in logs[0]} | {"optimizer_steps": len(logs)}
