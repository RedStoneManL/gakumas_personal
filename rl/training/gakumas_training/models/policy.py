from __future__ import annotations

from dataclasses import asdict, dataclass
import gc
import json
from time import perf_counter
import torch
from torch import nn
from torch.distributions import Categorical

from ..contracts import PolicySelection
from ..encoding import collate
from ..device import (capture_retry_rng, restore_retry_rng, empty_accelerator_cache,
                      is_accelerator_oom, model_device)


@dataclass(frozen=True)
class ModelConfig:
    width: int = 64
    layers: int = 2
    token_dim: int = 16
    vocab_capacity: int = 65536
    max_nodes: int = 32768

    def __post_init__(self):
        if min(self.width, self.layers, self.token_dim, self.vocab_capacity, self.max_nodes) < 1:
            raise ValueError("Model dimensions must be positive")


@dataclass
class PolicyEvaluation:
    logits: torch.Tensor
    values: torch.Tensor
    log_probs: torch.Tensor | None
    entropy: torch.Tensor


def _mean(features, groups, size):
    sums = features.new_zeros((size, features.shape[-1])).index_add_(0, groups, features)
    counts = features.new_zeros(size).index_add_(0, groups, features.new_ones(len(groups)))
    return sums / counts.clamp_min(1).unsqueeze(-1), counts


def _tree_groups(batch):
    if "tree_levels" in batch:
        yield from batch["tree_levels"]
        return
    # Compatibility for callers with the original packed-batch contract. The
    # normal collate path performs this structural work once on CPU instead.
    for depth in range(batch["max_depth"], 0, -1):
        selected = batch["tree_depths"] == depth
        children = batch["tree_src"][selected]
        parents, inverse = torch.unique(batch["tree_dst"][selected], return_inverse=True)
        yield selected, children, parents, inverse


class PolicyValueNet(nn.Module):
    """Linear-in-edges shared trunk with candidate-conditioned global attention.

    Field/value pairs are coupled before pooling. Edge roles and ordered argument
    positions survive message passing. Cross attention is only candidates × nodes,
    never a full quadratic attention matrix over every program node.
    """
    def __init__(self, config=None):
        super().__init__()
        self.config = config or ModelConfig()
        c = self.config
        self.tokens = nn.Embedding(c.vocab_capacity, c.token_dim, padding_idx=0)
        self.feature = nn.Sequential(nn.Linear(c.token_dim + 5, c.width), nn.SiLU(), nn.Linear(c.width, c.width))
        self.node = nn.Sequential(nn.Linear(c.width + 1, c.width), nn.LayerNorm(c.width), nn.SiLU())
        self.edge = nn.Sequential(nn.Linear(c.token_dim + 2, c.width), nn.SiLU())
        self.tree_message = nn.Linear(c.width, c.width)
        self.tree_update = nn.Sequential(nn.Linear(c.width * 2 + 1, c.width), nn.SiLU(), nn.LayerNorm(c.width))
        self.messages = nn.ModuleList(nn.Linear(c.width, c.width) for _ in range(c.layers))
        self.updates = nn.ModuleList(nn.Sequential(nn.Linear(c.width * 2, c.width), nn.SiLU(), nn.LayerNorm(c.width))
                                     for _ in range(c.layers))
        self.query = nn.Linear(c.width, c.width, bias=False)
        self.key = nn.Linear(c.width, c.width, bias=False)
        self.policy_head = nn.Sequential(nn.Linear(c.width * 3, c.width), nn.SiLU(), nn.Linear(c.width, 1))
        self.value_head = nn.Sequential(nn.Linear(c.width + 1, c.width), nn.SiLU(), nn.Linear(c.width, 1))
        nn.init.orthogonal_(self.policy_head[-1].weight, gain=0.01)
        nn.init.zeros_(self.policy_head[-1].bias)

    def forward(self, batch):
        b = batch
        max_token = b.get("max_feature_token")
        if max_token is None:
            max_token = int(b["feature_tokens"].max()) if len(b["feature_tokens"]) else 0
        if max_token >= self.config.vocab_capacity:
            raise ValueError("Encoded vocabulary exceeds model capacity")
        values = self.feature(torch.cat([self.tokens(b["feature_tokens"]), b["feature_numbers"]], -1))
        pooled, counts = _mean(values, b["feature_nodes"], b["node_count"])
        nodes = self.node(torch.cat([pooled, counts.log1p().unsqueeze(-1)], -1))
        tree_pos = b["tree_positions"]
        tree_edge = self.edge(torch.cat([self.tokens(b["tree_roles"]),
                             torch.stack([tree_pos / 100., (tree_pos >= 0).float()], -1)], -1))
        # Compile complete nested programs into their owning roots before relation
        # propagation. No fixed message-passing depth can replace this tree pass.
        for selected, children, parents, inverse in _tree_groups(b):
            messages = nodes[children] + self.tree_message(nodes[children]) * torch.sigmoid(tree_edge[selected])
            child_state, child_count = _mean(messages, inverse, len(parents))
            updated = self.tree_update(torch.cat([nodes[parents], child_state,
                                                 child_count.log1p().unsqueeze(-1)], -1))
            nodes = nodes.index_copy(0, parents, nodes[parents] + child_state + updated)
        pos = b["edge_positions"]
        edge_state = self.edge(torch.cat([self.tokens(b["edge_roles"]),
                              torch.stack([pos / 100., (pos >= 0).float()], -1)], -1))
        for message, update in zip(self.messages, self.updates):
            transmitted = message(nodes[b["edge_src"]]) * torch.sigmoid(edge_state)
            neighbors, _ = _mean(transmitted, b["edge_dst"], b["node_count"])
            nodes = nodes + update(torch.cat([nodes, neighbors], -1))
        global_state, node_counts = _mean(nodes, b["node_batches"], b["batch_size"])
        chosen = nodes[b["action_indices"]]
        query = self.query(chosen)
        keys = self.key(nodes)
        # Different graph sizes are handled without padding graph nodes.
        contexts = []
        for i in range(b["batch_size"]):
            if "node_slices" in b:
                start, end = b["node_slices"][i]
                graph_keys, graph_nodes = keys[start:end], nodes[start:end]
            else:
                membership = b["node_batches"] == i
                graph_keys, graph_nodes = keys[membership], nodes[membership]
            weights = torch.softmax(query[i] @ graph_keys.T / self.config.width ** 0.5, dim=-1)
            contexts.append(weights @ graph_nodes)
        context = torch.stack(contexts)
        global_expanded = global_state[:, None].expand(-1, chosen.shape[1], -1)
        logits = self.policy_head(torch.cat([chosen, context, global_expanded], -1)).squeeze(-1)
        logits = logits.masked_fill(~b["mask"], -torch.inf)
        values = self.value_head(torch.cat([global_state, node_counts.log1p().unsqueeze(-1)], -1)).squeeze(-1)
        return logits, values

    def evaluate(self, encoded_list, action_indices=None):
        device = next(self.parameters()).device
        logits, values = self(collate(encoded_list, device=device))
        distribution = Categorical(logits=logits)
        selected = None
        if action_indices is not None:
            indices = torch.as_tensor(action_indices, dtype=torch.long, device=device)
            if indices.shape != values.shape:
                raise ValueError("One selected action is required for every graph")
            if ((indices < 0) | (indices >= logits.shape[1])).any():
                raise ValueError("Selected action index outside candidate range")
            selected = distribution.log_prob(indices)
            if not torch.isfinite(selected).all():
                raise ValueError("Selected action refers to candidate padding")
        return PolicyEvaluation(logits, values, selected, distribution.entropy())


class PolicyRunner:
    def __init__(self, encoder, model):
        self.encoder, self.model = encoder, model
        self.effective_inference_batch_size = None
        self.last_oom_fallbacks = []
        self.reset_timings()

    def reset_timings(self):
        self.timing_counters = {"encoding_seconds": 0., "inference_seconds": 0., "decisions": 0,
                                "inference_batches": 0, "inference_forward_calls": 0, "oom_fallbacks": 0}

    def act(self, context, policy_version=0, deterministic=False):
        return self.act_batch([context], policy_version, deterministic=deterministic)[0]

    def _act_encoded(self, encoded, policy_version, deterministic, chunk_size):
        logits, values = [], []
        width = max(len(state.action_nodes) for state in encoded)
        for start in range(0, len(encoded), chunk_size):
            self.timing_counters["inference_forward_calls"] += 1
            result = self.model.evaluate(encoded[start:start + chunk_size])
            logits.append(torch.nn.functional.pad(result.logits, (0, width - result.logits.shape[1]), value=-torch.inf)
                          if result.logits.shape[1] != width else result.logits)
            values.append(result.values)
        # Sampling occurs only once, after EVERY forward succeeds. Splitting an
        # oversized wave never makes separate per-chunk categorical RNG calls.
        all_logits = logits[0] if len(logits) == 1 else torch.cat(logits)
        all_values = values[0] if len(values) == 1 else torch.cat(values)
        distribution = Categorical(logits=all_logits)
        action = all_logits.argmax(-1) if deterministic else distribution.sample()
        indices = action.cpu().tolist()
        log_probs = distribution.log_prob(action).cpu().tolist()
        values = all_values.cpu().tolist()
        return [PolicySelection(int(index), float(log_prob), float(value), int(policy_version), state)
                for index, log_prob, value, state in zip(indices, log_probs, values, encoded, strict=True)]

    def act_batch(self, contexts, policy_version=0, deterministic=False):
        """Central inference for ordered public decisions from independent games.

        Only this runner owns the encoder/vocabulary. Every returned log-prob is
        from the exact masked distribution that sampled its action in this batch.
        Sampling a batch need not consume RNG identically to repeated single acts.
        """
        contexts = list(contexts)
        if not contexts:
            return []
        start = perf_counter()
        encoded = [self.encoder.encode(context) for context in contexts]
        self.timing_counters["encoding_seconds"] += perf_counter() - start
        start = perf_counter()
        self.last_oom_fallbacks = []
        chunk_size = min(len(encoded), self.effective_inference_batch_size or len(encoded))
        rng = capture_retry_rng()
        with torch.no_grad():
            while True:
                try:
                    selections = self._act_encoded(encoded, policy_version, deterministic, chunk_size)
                    break
                except RuntimeError as error:
                    if not is_accelerator_oom(error, model_device(self.model)) or chunk_size <= 1:
                        raise
                    error.__traceback__ = None
                    restore_retry_rng(rng)
                    gc.collect()
                    empty_accelerator_cache()
                    previous = chunk_size
                    chunk_size = max(1, chunk_size // 2)
                    self.effective_inference_batch_size = chunk_size
                    kind = "npu" if model_device(self.model).type == "npu" else "cuda"
                    event = {"event": f"{kind}_oom_retry", "component": "policy_inference",
                             "attempted_batch_size": previous, "effective_inference_batch_size": chunk_size}
                    self.last_oom_fallbacks.append(event)
                    self.timing_counters["oom_fallbacks"] += 1
                    print(json.dumps(event, sort_keys=True), flush=True)
        self.timing_counters["inference_seconds"] += perf_counter() - start
        self.timing_counters["decisions"] += len(contexts)
        self.timing_counters["inference_batches"] += 1
        return selections

    __call__ = act
