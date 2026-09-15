"""Exact input assembly without per-atom padded-list tensor construction.

This module is outside the frozen training source. It caches only structural
paths and numeric transforms within one call, never learned embeddings or game
state. Lexeme order, atom order, dtype and masking match the current collator.
"""
import math
import numpy as np
import torch
from round2rl.encoding import MAX_DEPTH, MAX_TEXT_BYTES


def collate(examples, device='cpu'):
    lexemes, lookup = [''], {'': 0}

    def word(text):
        if text not in lookup:
            if len(text.encode('utf-8')) > MAX_TEXT_BYTES:
                raise ValueError('lexical token exceeds explicit byte capacity')
            lookup[text] = len(lexemes)
            lexemes.append(text)
        return lookup[text]

    paths, kinds, values, numbers, entities = [], [], [], [], []
    edge_src, edge_dst, edge_word, batches, actions = [], [], [], [], []
    path_cache, number_cache = {}, {}
    # `paths`/`numbers` were lists of N references into a small deduplicated set of
    # row-lists. np.asarray over a list-of-lists costs ~16ms/11ms per call at N=20k
    # (measured on this box) because it walks Python objects. Instead intern the rows,
    # collect flat int indices, and fancy-index the small unique table once in C.
    # Output is bit-identical: same rows, same order, same dtype.
    unique_paths, unique_numbers = [], []
    offset = 0
    for batch, e in enumerate(examples):
        batches.extend([batch] * e.entity_count)
        actions.append([offset + i for i in e.action_entities])
        for ent, path, kind, text, number in e.atoms:
            path = tuple(path)
            row = path_cache.get(path)
            if row is None:
                row = len(unique_paths)
                unique_paths.append([word(p) for p in path] + [0] * (MAX_DEPTH - len(path)))
                path_cache[path] = row
            paths.append(row)
            kinds.append(kind)
            values.append(word(text))
            entities.append(ent + offset)
            # Preserve negative zero, too: dict equality alone conflates +/-0.
            key = (number, math.copysign(1.0, number))
            numeric = number_cache.get(key)
            if numeric is None:
                numeric = len(unique_numbers)
                unique_numbers.append([math.copysign(math.log1p(abs(number)), number),
                                       number / (1 + abs(number)), number / 10000,
                                       float(number != 0)])
                number_cache[key] = numeric
            numbers.append(numeric)
        for src, dst, text in e.edges:
            edge_src.append(src + offset)
            edge_dst.append(dst + offset)
            edge_word.append(word(text))
        offset += e.entity_count

    byte_rows = [np.frombuffer(t.encode('utf-8'), dtype=np.uint8).astype(np.int64) + 1
                 if t else np.zeros(1, dtype=np.int64) for t in lexemes]
    lengths_np = np.asarray([len(row) for row in byte_rows], dtype=np.int64)
    byte_np = np.zeros((len(byte_rows), int(lengths_np.max())), dtype=np.int64)
    for i, row in enumerate(byte_rows):
        byte_np[i, :len(row)] = row
    action_np = np.zeros((len(examples), max(map(len, actions))), dtype=np.int64)
    mask_np = np.zeros_like(action_np, dtype=np.bool_)
    for i, row in enumerate(actions):
        action_np[i, :len(row)] = row
        mask_np[i, :len(row)] = True

    def tensor(value, dtype=np.int64):
        return torch.from_numpy(np.asarray(value, dtype=dtype)).to(device)

    def flat(value, dtype=np.int64):
        # np.fromiter avoids the generic object walk np.asarray does on a Python list.
        return torch.from_numpy(np.fromiter(value, dtype=dtype, count=len(value))).to(device)

    def gathered(index, table, dtype):
        # index rows out of the deduplicated table in C rather than converting N lists.
        if not index:
            return torch.from_numpy(np.zeros((0, 0), dtype=dtype)).to(device)
        tab = np.asarray(table, dtype=dtype)
        idx = np.fromiter(index, dtype=np.int64, count=len(index))
        return torch.from_numpy(tab[idx]).to(device)

    phase_values = [e.phase for e in examples]
    if any(p not in range(5) for p in phase_values):
        raise ValueError('Unknown phase')
    phase = tensor(phase_values)
    return {'bytes': tensor(byte_np), 'lengths': torch.from_numpy(lengths_np),
            'paths': gathered(paths, unique_paths, np.int64),
            'kinds': flat(kinds), 'values': flat(values),
            'numbers': gathered(numbers, unique_numbers, np.float32),
            'entities': flat(entities),
            'edge_src': flat(edge_src), 'edge_dst': flat(edge_dst),
            'edge_word': flat(edge_word), 'batches': flat(batches),
            'action_index': tensor(action_np), 'mask': tensor(mask_np, np.bool_),
            'entity_count': offset, 'batch_size': len(examples),
            'phase': phase, 'drink_phase': phase == 1,
            'uniform_phase': phase_values[0] if len(set(phase_values)) == 1 else None,
            'lexemes': tuple(lexemes)}
