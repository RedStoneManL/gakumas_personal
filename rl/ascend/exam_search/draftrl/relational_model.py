"""Independent typed relational side path; zero output projections preserve v5.

The legacy encoder never sees these nodes or edges.  All projections before the
residual output are normally initialized: zeroing both a gate and an output
projection would prevent this branch from learning.
"""
from __future__ import annotations

import math

import torch
from torch import nn

from round2rl.encoding import MAX_DEPTH
from round2rl.model import mlp, pool


NODE_TYPES = (
    'global', 'card', 'p_item', 'drink', 'memory', 'program', 'state',
    'event', 'time', 'zone', 'constraint', 'candidate', 'counter',
)
PHASE_NAMES = ('exam', 'drink', 'draft', 'guidance', 'memory')


class RelationalStem(nn.Module):
    """Learn program tokens from the side view, never from legacy embeddings."""
    def __init__(self, width=96, lexical=16):
        super().__init__()
        self.byte = nn.Embedding(257, lexical, padding_idx=0)
        self.text = nn.GRU(lexical, lexical, batch_first=True)
        self.kind = nn.Embedding(6, 8)
        self.atom = mlp(MAX_DEPTH * lexical + lexical + 8 + 4, width, width)
        self.node = mlp(width * 2 + 1, width, width)
        self.type_adapters = nn.ModuleDict({name: mlp(width, width, width)
                                           for name in NODE_TYPES})
        # These modules have a fixed semantic scope, shared across source idols.
        self.program_encoder = mlp(width, width * 2, width)
        self.state_encoder = mlp(width, width * 2, width)
        self.event_encoder = mlp(width, width * 2, width)
        self.time_encoder = mlp(width, width * 2, width)
        self.zone_encoder = mlp(width, width * 2, width)
        self.constraint_encoder = mlp(width, width * 2, width)

    def word_vectors(self, tokens, lengths):
        if tokens.device.type == 'npu':
            from .portable_gru import final_hidden
            return final_hidden(self.text, self.byte(tokens), lengths)
        packed = nn.utils.rnn.pack_padded_sequence(
            self.byte(tokens), lengths, batch_first=True, enforce_sorted=False)
        return self.text(packed)[1][0]

    def forward(self, b):
        lex = self.word_vectors(b['bytes'], b['lengths'])
        lex = lex * (torch.arange(len(lex), device=lex.device) != 0)[:, None]
        atoms = self.atom(torch.cat([
            nn.functional.embedding(b['paths'], lex, padding_idx=0).flatten(1),
            nn.functional.embedding(b['values'], lex, padding_idx=0),
            self.kind(b['kinds']), b['numbers']], -1))
        nodes = self.node(pool(atoms, b['entities'], b['entity_count']))
        types = b['node_types']
        if types.shape != (b['entity_count'],):
            raise ValueError('Relational node_types must align with every side entity')
        if bool(((types < 0) | (types >= len(NODE_TYPES))).any()):
            raise ValueError('Unknown relational node type')
        adapted = torch.zeros_like(nodes)
        for index, name in enumerate(NODE_TYPES):
            selected = (types == index).nonzero(as_tuple=True)[0]
            if selected.numel():
                adapted = adapted.index_copy(
                    0, selected, nodes[selected] + self.type_adapters[name](nodes[selected]))
        scopes = {
            'program_encoder': (1, 2, 3, 4, 5),
            'state_encoder': (0, 6), 'event_encoder': (7, 12),
            'time_encoder': (8,), 'zone_encoder': (9,),
            'constraint_encoder': (10,),
        }
        result = adapted
        for module, type_ids in scopes.items():
            mask = torch.zeros_like(types, dtype=torch.bool)
            for type_id in type_ids:
                mask = mask | (types == type_id)
            selected = mask.nonzero(as_tuple=True)[0]
            if selected.numel():
                result = result.index_copy(
                    0, selected, adapted[selected] + getattr(self, module)(adapted[selected]))
        return result, lex


class ReceiverBlock(nn.Module):
    """Sparse messages select information before mixing it at the receiver."""
    def __init__(self, width=96, lexical=16):
        super().__init__()
        self.message = mlp(width * 2 + lexical, width, width)
        self.gate = nn.Linear(width * 2 + lexical, 1)
        self.update = mlp(width * 4 + 1, width * 2, width)

    def forward(self, nodes, groups, batch_size, lex, src, dst, words):
        aggregate = pool(nodes, groups, batch_size)[groups]
        neighbors = torch.zeros_like(nodes)
        if src.numel():
            pairs = torch.cat([nodes[src], nodes[dst], lex[words]], -1)
            messages = self.message(pairs) * self.gate(pairs).sigmoid()
            neighbors = neighbors.index_add(0, dst, messages)
            degree = nodes.new_zeros(len(nodes)).index_add(
                0, dst, nodes.new_ones(len(messages)))
            neighbors = neighbors / degree[:, None].clamp_min(1)
        return nodes + self.update(torch.cat([nodes, neighbors, aggregate], -1))


class RelationTower(nn.Module):
    def __init__(self, width=96, lexical=16, depth=2):
        super().__init__()
        self.blocks = nn.ModuleList([ReceiverBlock(width, lexical) for _ in range(depth)])
        self.global_head = mlp(width * 2 + 1, width * 2, width)

    def forward(self, nodes, groups, batch_size, lex, src, dst, words):
        for block in self.blocks:
            nodes = block(nodes, groups, batch_size, lex, src, dst, words)
        return nodes, self.global_head(pool(nodes, groups, batch_size))


class RelationalEncoder(nn.Module):
    def __init__(self, width=96, lexical=16, depth=2):
        super().__init__()
        self.stem = RelationalStem(width, lexical)
        self.towers = nn.ModuleDict({name: RelationTower(width, lexical, depth)
                                     for name in ('exam', 'build')})

    def forward(self, b):
        nodes, lex = self.stem(b)
        uniform = b.get('uniform_phase')
        if uniform is not None:
            if not 0 <= uniform < len(PHASE_NAMES):
                raise ValueError('Unknown relational phase')
            return self.towers['exam' if uniform == 0 else 'build'](
                nodes, b['batches'], b['batch_size'], lex,
                b['edge_src'], b['edge_dst'], b['edge_word'])
        phase = b['phase']
        if bool(((phase < 0) | (phase >= len(PHASE_NAMES))).any()):
            raise ValueError('Unknown relational phase')
        output = torch.zeros_like(nodes)
        states = nodes.new_zeros(b['batch_size'], nodes.shape[-1])
        for name, tower in self.towers.items():
            samples = (phase == 0) if name == 'exam' else (phase != 0)
            if not bool(samples.any()):
                continue
            entity_mask = samples[b['batches']]
            indices = entity_mask.nonzero(as_tuple=True)[0]
            lookup = torch.full((len(nodes),), -1, dtype=torch.long, device=nodes.device)
            lookup[indices] = torch.arange(len(indices), device=nodes.device)
            edges = entity_mask[b['edge_src']] & entity_mask[b['edge_dst']]
            updated, state = tower(nodes[indices], b['batches'][indices], b['batch_size'], lex,
                                   lookup[b['edge_src'][edges]], lookup[b['edge_dst'][edges]],
                                   b['edge_word'][edges])
            output = output.index_copy(0, indices, updated)
            selected = samples.nonzero(as_tuple=True)[0]
            states = states.index_copy(0, selected, state[selected])
        return output, states


class CandidateQuery(nn.Module):
    """Each action reads the side entities of its own example (A x N, not N x N)."""
    def __init__(self, width=96):
        super().__init__()
        self.query = nn.Linear(width, width)
        self.key = nn.Linear(width, width)
        self.value = nn.Linear(width, width)
        self.width = width

    def forward(self, nodes, b):
        groups = b['batches']
        counts = torch.bincount(groups, minlength=b['batch_size'])
        widest = int(counts.max())
        starts = counts.cumsum(0) - counts
        positions = torch.arange(len(nodes), device=nodes.device) - starts[groups]
        padded = nodes.new_zeros(b['batch_size'], widest, self.width)
        padded[groups, positions] = nodes
        valid = torch.arange(widest, device=nodes.device)[None, :] < counts[:, None]
        selected = nodes[b['action_index']]
        scores = torch.matmul(self.query(selected), self.key(padded).transpose(-1, -2))
        scores = scores / math.sqrt(self.width)
        weights = scores.masked_fill(~valid[:, None, :], -torch.inf).softmax(-1)
        return selected, torch.matmul(weights, self.value(padded))


def zero_output_head(inputs, width, outputs):
    head = nn.Sequential(nn.Linear(inputs, width), nn.SiLU(), nn.Linear(width, outputs))
    # Only the final projection is zero; the upstream representation and gates
    # remain non-degenerate so the output learns first, then the whole branch.
    nn.init.zeros_(head[-1].weight)
    nn.init.zeros_(head[-1].bias)
    return head


def phase_output(heads, features, b):
    uniform = b.get('uniform_phase')
    if uniform is not None:
        return heads[PHASE_NAMES[uniform]](features)
    result = heads['exam'](features)
    phase = b['phase']
    for index, name in enumerate(PHASE_NAMES[1:], 1):
        shape = [len(phase)] + [1] * (result.ndim - 1)
        result = torch.where((phase == index).reshape(shape), heads[name](features), result)
    return result


class RelationalActor(nn.Module):
    def __init__(self, width=96, lexical=16, depth=2):
        super().__init__()
        self.encoder = RelationalEncoder(width, lexical, depth)
        self.candidate_query = CandidateQuery(width)
        self.policy_heads = nn.ModuleDict({name: zero_output_head(width * 3, width, 1)
                                           for name in PHASE_NAMES})

    def forward(self, b):
        nodes, state = self.encoder(b)
        selected, context = self.candidate_query(nodes, b)
        features = torch.cat([selected, context, state[:, None].expand_as(selected)], -1)
        return phase_output(self.policy_heads, features, b).squeeze(-1)


class RelationalCritic(nn.Module):
    def __init__(self, width=96, lexical=16, depth=2, quantiles=0):
        super().__init__()
        self.width = width
        self.encoder = RelationalEncoder(width, lexical, depth)
        self.value_heads = nn.ModuleDict({name: zero_output_head(width, width, 1)
                                         for name in PHASE_NAMES})
        if quantiles:
            self.quantile_head = zero_output_head(width, width, quantiles)

    def enable_quantiles(self, count):
        if not hasattr(self, 'quantile_head'):
            reference = next(self.parameters())
            self.quantile_head = zero_output_head(self.width, self.width, count).to(
                device=reference.device, dtype=reference.dtype)
            return True
        if self.quantile_head[-1].out_features != count:
            raise ValueError('Relational quantile resolution changed')
        return False

    def forward(self, b):
        _, state = self.encoder(b)
        scalar = phase_output(self.value_heads, state, b).squeeze(-1)
        quantiles = self.quantile_head(state) if hasattr(self, 'quantile_head') else None
        return scalar, quantiles
