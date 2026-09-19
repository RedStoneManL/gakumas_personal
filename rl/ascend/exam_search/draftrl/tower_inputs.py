"""Prepare immutable task subgraphs once, preserving accelerator pooling plans."""
import numpy as np
import torch
from round2rl.model import prepare_segment_plan


def prepare_tower_inputs(groups, phases, src, dst, words, device):
    groups, phases, src, dst, words = [np.asarray(x, dtype=np.int64)
                                      for x in (groups, phases, src, dst, words)]
    if np.any((phases < 0) | (phases > 4)):
        raise ValueError('Unknown phase must not silently route to build')
    result = {}
    for name in ('exam', 'build'):
        samples = phases == 0 if name == 'exam' else phases != 0
        entity_mask = samples[groups]
        indices = np.flatnonzero(entity_mask)
        lookup = np.full(len(groups), -1, dtype=np.int64)
        lookup[indices] = np.arange(len(indices))
        edges = entity_mask[src] & entity_mask[dst]
        subset = groups[indices]
        batches = torch.from_numpy(subset).to(device)
        batches._arena_segment_plan = prepare_segment_plan(subset, len(phases), device)
        tensors = dict(indices=indices, samples=np.flatnonzero(samples),
                       edge_src=lookup[src[edges]], edge_dst=lookup[dst[edges]],
                       edge_word=words[edges])
        result[name] = {key: torch.from_numpy(value).to(device) for key,value in tensors.items()}
        result[name]['batches'] = batches
    return result


def forward_towers(towers, nodes, batch, lex):
    """Use the original towers and original global sample ids without re-slicing metadata."""
    output = torch.zeros_like(nodes)
    states = nodes.new_zeros(batch['batch_size'], nodes.shape[-1])
    for name, tower in towers.items():
        part = batch['tower_inputs'][name]
        selected, indices = part['samples'], part['indices']
        if not selected.numel():
            continue
        updated, state = tower(nodes[indices], part['batches'], batch['batch_size'], lex,
                               part['edge_src'], part['edge_dst'], part['edge_word'])
        output = output.index_copy(0, indices, updated)
        states = states.index_copy(0, selected, state[selected])
    return output, states
