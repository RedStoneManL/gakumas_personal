"""Small entity networks with independent policy/value parameters."""
from __future__ import annotations

import torch
from torch import nn
from .encoding import MAX_DEPTH

MODEL_SCHEMA = "round2-entity-policy-value/1"


def mlp(a, b, c):
    return nn.Sequential(nn.Linear(a, b), nn.SiLU(), nn.Linear(b, c), nn.LayerNorm(c))


def pool(x, group, size):
    total = x.new_zeros(size, x.shape[-1]).index_add_(0, group, x)
    count = x.new_zeros(size).index_add_(0, group, x.new_ones(len(group)))
    maximum = x.new_full((size, x.shape[-1]), -torch.inf)
    maximum.scatter_reduce_(0, group[:, None].expand_as(x), x, reduce="amax", include_self=True)
    maximum = torch.where(torch.isfinite(maximum), maximum, torch.zeros_like(maximum))
    return torch.cat([total / count[:, None].clamp_min(1), maximum, count.log1p()[:, None]], -1)


class EntityEncoder(nn.Module):
    def __init__(self, width=96, lexical=16):
        super().__init__()
        self.byte = nn.Embedding(257, lexical, padding_idx=0)
        self.text = nn.GRU(lexical, lexical, batch_first=True)
        self.kind = nn.Embedding(6, 8)
        self.atom = mlp(MAX_DEPTH * lexical + lexical + 8 + 4, width, width)
        self.node = mlp(width * 2 + 1, width, width)
        self.edge = mlp(width + lexical, width, width)
        self.update = nn.ModuleList([mlp(width * 4 + 1, width * 2, width) for _ in range(2)])
        self.global_head = mlp(width * 2 + 1, width * 2, width)

    def forward(self, b):
        packed = nn.utils.rnn.pack_padded_sequence(self.byte(b["bytes"]), b["lengths"], batch_first=True, enforce_sorted=False)
        _, h = self.text(packed)
        lex = h[0]
        lex = lex * (torch.arange(len(lex), device=lex.device) != 0)[:, None]
        atoms = self.atom(torch.cat([torch.nn.functional.embedding(b["paths"], lex, padding_idx=0).flatten(1), torch.nn.functional.embedding(b["values"], lex, padding_idx=0),
                                    self.kind(b["kinds"]), b["numbers"]], -1))
        nodes = self.node(pool(atoms, b["entities"], b["entity_count"]))
        for update in self.update:
            aggregate = pool(nodes, b["batches"], b["batch_size"])[b["batches"]]
            neighbors = torch.zeros_like(nodes)
            if len(b["edge_src"]):
                messages = self.edge(torch.cat([nodes[b["edge_src"]], lex[b["edge_word"]]], -1))
                neighbors.index_add_(0, b["edge_dst"], messages)
                degree = nodes.new_zeros(len(nodes)).index_add_(0, b["edge_dst"], nodes.new_ones(len(messages)))
                neighbors = neighbors / degree[:, None].clamp_min(1)
            nodes = nodes + update(torch.cat([nodes, neighbors, aggregate], -1))
        global_state = self.global_head(pool(nodes, b["batches"], b["batch_size"]))
        return nodes, global_state


class PolicyValue(nn.Module):
    def __init__(self, width=96, lexical=16):
        super().__init__()
        self.config = {"width": width, "lexical": lexical}
        self.actor = EntityEncoder(width, lexical)
        self.critic = EntityEncoder(width, lexical)
        self.policy_head = nn.Sequential(nn.Linear(width * 2, width), nn.Tanh(), nn.Linear(width, 1))
        self.value_head = nn.Linear(width, 1)
        nn.init.orthogonal_(self.policy_head[-1].weight, 0.01)
        nn.init.zeros_(self.policy_head[-1].bias)

    def forward(self, b):
        nodes, state = self.actor(b)
        selected = nodes[b["action_index"]]
        context = state[:, None].expand(-1, selected.shape[1], -1)
        logits = self.policy_head(torch.cat([selected, context], -1)).squeeze(-1)
        logits = logits.masked_fill(~b["mask"], -torch.inf)
        _, critic_state = self.critic(b)
        value = self.value_head(critic_state).squeeze(-1)
        return logits, value

    def policy(self, b):
        nodes, state = self.actor(b)
        selected = nodes[b["action_index"]]
        logits = self.policy_head(torch.cat([selected, state[:, None].expand(-1, selected.shape[1], -1)], -1)).squeeze(-1)
        return logits.masked_fill(~b["mask"], -torch.inf)
