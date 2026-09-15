"""Versioned split build/exam architecture for joint public-MCTS training.

Import after the selected frozen draftrl/runtime paths have been configured.
Only the semantic stem is shared across build/exam tasks. Actor and critic
remain independent. Extra residual blocks start as identity transformations.
"""
import copy

import torch
from torch import nn
from .legacy_model import DraftPolicy as LegacyPolicy
from round2rl.model import pool

MODEL_SCHEMA = "arena-joint-public-mcts-split/1"


class TaskTower(nn.Module):
    def __init__(self, original, depth):
        super().__init__()
        if depth < len(original.update):
            raise ValueError("Cannot preserve the old function by removing blocks")
        self.edge = copy.deepcopy(original.edge)
        self.update = copy.deepcopy(original.update)
        for _ in range(depth - len(original.update)):
            block = copy.deepcopy(original.update[-1])
            # Zero affine output, not random extra residual changes. Gradients
            # initially learn the final norm's affine parameters, then the block.
            nn.init.zeros_(block[-1].weight)
            nn.init.zeros_(block[-1].bias)
            self.update.append(block)
        self.global_head = copy.deepcopy(original.global_head)

    def forward(self, nodes, groups, batch_size, lex, src, dst, words):
        for update in self.update:
            aggregate = pool(nodes, groups, batch_size)[groups]
            neighbors = torch.zeros_like(nodes)
            if len(src):
                messages = self.edge(torch.cat([nodes[src], lex[words]], -1))
                neighbors.index_add_(0, dst, messages)
                degree = nodes.new_zeros(len(nodes)).index_add_(
                    0, dst, nodes.new_ones(len(messages)))
                neighbors = neighbors / degree[:, None].clamp_min(1)
            nodes = nodes + update(torch.cat([nodes, neighbors, aggregate], -1))
        return nodes, self.global_head(pool(nodes, groups, batch_size))


class SplitEncoder(nn.Module):
    def __init__(self, original, depth):
        super().__init__()
        for name in ("byte", "text", "kind", "atom", "node"):
            setattr(self, name, copy.deepcopy(getattr(original, name)))
        self.towers = nn.ModuleDict({
            name: TaskTower(original, depth) for name in ("exam", "build")})

    def word_vectors(self, tokens, lengths):
        if tokens.device.type == 'npu':
            from .portable_gru import final_hidden
            # Keep inherited GRU parameters and full autograd; no CPU fallback.
            return final_hidden(self.text, self.byte(tokens), lengths)
        packed = nn.utils.rnn.pack_padded_sequence(
            self.byte(tokens), lengths, batch_first=True, enforce_sorted=False)
        return self.text(packed)[1][0]

    def lexical(self, b):
        cache = getattr(self, '_search_lex_cache', None)
        if cache is None or torch.is_grad_enabled():
            return self.word_vectors(b['bytes'], b['lengths'])
        words = b['lexemes']
        missing = [i for i, word in enumerate(words) if word not in cache]
        if len(cache)+len(missing)>16384:
            cache.clear()
            missing=list(range(len(words)))
        if missing:
            indices=torch.tensor(missing,device=b['bytes'].device)
            lengths=b['lengths'][missing]
            vectors=self.word_vectors(b['bytes'][indices,:int(lengths.max())],lengths)
            for row,index in enumerate(missing):cache[words[index]]=vectors[row].detach()
        return torch.stack([cache[word] for word in words])

    def forward(self, b):
        uniform = b.get('uniform_phase')
        if uniform is None and not torch.all((b["phase"] >= 0) & (b["phase"] <= 4)):
            raise ValueError("Unknown phase must not silently route to build")
        lex = self.lexical(b)
        lex = lex * (torch.arange(len(lex), device=lex.device) != 0)[:, None]
        atoms = self.atom(torch.cat([
            nn.functional.embedding(b["paths"], lex, padding_idx=0).flatten(1),
            nn.functional.embedding(b["values"], lex, padding_idx=0),
            self.kind(b["kinds"]), b["numbers"]], -1))
        nodes = self.node(pool(atoms, b["entities"], b["entity_count"]))
        if uniform is not None:
            # Search batches are all exam states. Avoid GPU synchronizations,
            # masking and graph remapping for a branch that uses every node.
            return self.towers['exam' if uniform == 0 else 'build'](
                nodes, b['batches'], b['batch_size'], lex,
                b['edge_src'], b['edge_dst'], b['edge_word'])
        output_nodes = torch.zeros_like(nodes)
        output_states = nodes.new_zeros(b["batch_size"], nodes.shape[-1])
        for name, tower in self.towers.items():
            samples = (b["phase"] == 0) if name == "exam" else (b["phase"] != 0)
            if not samples.any():
                continue
            entity_mask = samples[b["batches"]]
            indices = entity_mask.nonzero(as_tuple=True)[0]
            lookup = torch.full((len(nodes),), -1, device=nodes.device, dtype=torch.long)
            lookup[indices] = torch.arange(len(indices), device=nodes.device)
            edge_mask = entity_mask[b["edge_src"]] & entity_mask[b["edge_dst"]]
            updated, states = tower(
                nodes[indices], b["batches"][indices], b["batch_size"], lex,
                lookup[b["edge_src"][edge_mask]], lookup[b["edge_dst"][edge_mask]],
                b["edge_word"][edge_mask])
            output_nodes = output_nodes.index_copy(0, indices, updated)
            sample_indices = samples.nonzero(as_tuple=True)[0]
            output_states = output_states.index_copy(0, sample_indices, states[samples])
        return output_nodes, output_states


class DraftPolicy(LegacyPolicy):
    def __init__(self, width=96, lexical=16, depth=4, original=None, quantiles=0):
        if original is None:
            original = LegacyPolicy(width=width, lexical=lexical)
        super().__init__(width=width, lexical=lexical)
        self.actor = SplitEncoder(original.actor, depth)
        self.critic = SplitEncoder(original.critic, depth)
        for name, module in original.named_children():
            if name not in ("actor", "critic"):
                setattr(self, name, copy.deepcopy(module))
        self.config = {'width': width, 'lexical': lexical, 'depth': depth}
        if quantiles:
            self.enable_quantiles(quantiles)

    def enable_quantiles(self, count=32, optimizer=None):
        if hasattr(self, 'exam_quantile_head'):
            if self.config['quantiles'] != count:
                raise ValueError('Quantile resolution changed')
            return False
        if count != 32:
            raise ValueError('Only the audited 32-quantile head is supported')
        # Retain the scalar behavioral critic; add a distribution, not an
        # arbitrary multiplier applied to its score. No actor parameter changes.
        with torch.random.fork_rng(devices=[]):
            head = nn.Linear(self.config['width'], count)
        head = head.to(device=self.value_head.weight.device, dtype=self.value_head.weight.dtype)
        with torch.no_grad():
            head.weight.copy_(self.value_head.weight.expand(count, -1))
            head.bias.copy_(self.value_head.bias.expand(count))
        self.exam_quantile_head = head
        self.config['quantiles'] = count
        if optimizer is not None:
            optimizer.param_groups[0]['params'].extend(head.parameters())
        return True

    def value_outputs(self, b):
        _, state = self.critic(b)
        heads = ('value_head','drink_value_head','draft_value_head','guidance_value_head','memory_value_head')
        phase = b.get('uniform_phase')
        if phase is not None:
            values = getattr(self,heads[phase])(state).squeeze(-1)
        else:
            values = self.value_head(state).squeeze(-1)
            for i,name in enumerate(heads[1:],1):
                values = torch.where(b['phase']==i,getattr(self,name)(state).squeeze(-1),values)
        atoms = self.exam_quantile_head(state) if hasattr(self,'exam_quantile_head') else None
        return values, atoms

    def search_forward(self, b):
        values, atoms = self.value_outputs(b)
        return self.policy(b), values, atoms.sort(-1).values if atoms is not None else None

    def learning_forward(self, b):
        values, atoms = self.value_outputs(b)
        return self.policy(b), values, atoms

    def policy(self, b):
        phase = b.get('uniform_phase')
        if phase is None or torch.is_grad_enabled():
            return super().policy(b)
        nodes, state = self.actor(b)
        selected = nodes[b['action_index']]
        features = torch.cat([selected, state[:, None].expand(-1, selected.shape[1], -1)], -1)
        name = ('policy_head', 'drink_policy_head', 'draft_policy_head',
                'guidance_policy_head', 'memory_policy_head')[phase]
        return getattr(self, name)(features).squeeze(-1).masked_fill(~b['mask'], -torch.inf)

    def forward(self, b):
        logits, values, _ = self.learning_forward(b)
        return logits, values

    def legacy_parameter_name(self, name):
        fields = name.split('.')
        if len(fields) > 3 and fields[0] in ('actor', 'critic') and fields[1] == 'towers':
            fields = [fields[0]] + fields[3:]
            if fields[1] == 'update' and int(fields[2]) >= 2:
                return None
        return '.'.join(fields)
