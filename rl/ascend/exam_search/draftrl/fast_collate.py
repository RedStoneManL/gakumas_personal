"""Exact input assembly without per-atom padded-list tensor construction.

This module is outside the frozen training source. It caches only structural
paths and numeric transforms within one call, never learned embeddings or game
state. Lexeme order, atom order, dtype and masking match the current collator.
"""
import math
import numpy as np
from round2rl.encoding import MAX_DEPTH, MAX_TEXT_BYTES
# torch is imported inside the functions that build tensors. precollate() runs in
# every search worker process and must not pull torch into 1500+ processes.


def collate(examples, device='cpu'):
    import torch
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


# ---------------------------------------------------------------------------
# Worker-side pre-collation.
#
# py-spy on a collector thread serving 192 search processes: 37.6% of its time
# unpickling `Encoded` objects off the request queue, 28.7% in collate(), 17% in
# the NPU forward. The first two are pure Python per-atom work that the search
# process already has everything to do itself, on one of the 184 idle cores.
#
# precollate() turns one Encoded into compact numpy arrays with example-LOCAL
# lexeme ids. merge() interns each example's lexeme list in order and remaps the
# arrays with one fancy index each. The result is bit-identical to collate() on
# the same examples: collate's global lexeme order is exactly "example 0's
# first-seen order, then each later example's unseen words in its own first-seen
# order", which is what merge reproduces; and its paths/numbers tensors are
# per-atom rows, so the batch-wide dedup collate does is an optimisation of the
# Python loop, not part of the output.
# ---------------------------------------------------------------------------

def precollate(e):
    """One example -> numpy arrays with example-local lexeme ids. Runs in the worker."""
    lexemes, lookup = [''], {'': 0}

    def word(text):
        if text not in lookup:
            if len(text.encode('utf-8')) > MAX_TEXT_BYTES:
                raise ValueError('lexical token exceeds explicit byte capacity')
            lookup[text] = len(lexemes)
            lexemes.append(text)
        return lookup[text]

    n = len(e.atoms)
    path_rows = np.zeros((n, MAX_DEPTH), dtype=np.int64)
    kinds = np.empty(n, dtype=np.int64)
    values = np.empty(n, dtype=np.int64)
    entities = np.empty(n, dtype=np.int64)
    number_rows = []
    for i, (ent, path, kind, text, number) in enumerate(e.atoms):
        # Same interning order as collate: path components, then the value text.
        ids = [word(p) for p in path]
        if len(ids) > MAX_DEPTH:
            raise ValueError('structural depth exceeds explicit capacity')
        path_rows[i, :len(ids)] = ids
        kinds[i] = kind
        values[i] = word(text)
        entities[i] = ent
        number_rows.append([math.copysign(math.log1p(abs(number)), number),
                            number / (1 + abs(number)), number / 10000,
                            float(number != 0)])
    m = len(e.edges)
    edge_src = np.empty(m, dtype=np.int64)
    edge_dst = np.empty(m, dtype=np.int64)
    edge_word = np.empty(m, dtype=np.int64)
    for j, (src, dst, text) in enumerate(e.edges):
        edge_src[j], edge_dst[j], edge_word[j] = src, dst, word(text)
    phase = e.phase
    if phase not in range(5):
        raise ValueError('Unknown phase')
    return {'lexemes': lexemes, 'paths': path_rows, 'kinds': kinds, 'values': values,
            'numbers': np.asarray(number_rows, dtype=np.float32).reshape(n, 4),
            'entities': entities, 'edge_src': edge_src, 'edge_dst': edge_dst,
            'edge_word': edge_word, 'entity_count': int(e.entity_count),
            'action_entities': list(e.action_entities), 'phase': int(phase),
            'n_submissions': len(e.submissions)}


def merge(pres, device='cpu'):
    """Pre-collated examples -> the same batch dict collate() builds. Runs on the collector."""
    import torch
    lexemes, lookup = [''], {'': 0}
    paths, kinds, values, numbers, entities = [], [], [], [], []
    edge_src, edge_dst, edge_word, batches, actions = [], [], [], [], []
    phase_values = []
    offset = 0
    for batch, p in enumerate(pres):
        # Intern this example's words in its own first-seen order; new words append.
        remap = np.empty(len(p['lexemes']), dtype=np.int64)
        for local, text in enumerate(p['lexemes']):
            g = lookup.get(text)
            if g is None:
                g = len(lexemes)
                lexemes.append(text)
                lookup[text] = g
            remap[local] = g
        paths.append(remap[p['paths']])          # padding 0 -> '' -> global 0
        kinds.append(p['kinds'])
        values.append(remap[p['values']])
        numbers.append(p['numbers'])
        entities.append(p['entities'] + offset)
        edge_src.append(p['edge_src'] + offset)
        edge_dst.append(p['edge_dst'] + offset)
        edge_word.append(remap[p['edge_word']])
        batches.append(np.full(p['entity_count'], batch, dtype=np.int64))
        actions.append([offset + i for i in p['action_entities']])
        phase_values.append(p['phase'])
        offset += p['entity_count']

    byte_rows = [np.frombuffer(t.encode('utf-8'), dtype=np.uint8).astype(np.int64) + 1
                 if t else np.zeros(1, dtype=np.int64) for t in lexemes]
    lengths_np = np.asarray([len(row) for row in byte_rows], dtype=np.int64)
    byte_np = np.zeros((len(byte_rows), int(lengths_np.max())), dtype=np.int64)
    for i, row in enumerate(byte_rows):
        byte_np[i, :len(row)] = row
    action_np = np.zeros((len(pres), max(map(len, actions))), dtype=np.int64)
    mask_np = np.zeros_like(action_np, dtype=np.bool_)
    for i, row in enumerate(actions):
        action_np[i, :len(row)] = row
        mask_np[i, :len(row)] = True

    def cat(parts, dtype, width=None):
        if not parts or sum(len(x) for x in parts) == 0:
            shape = (0,) if width is None else (0, 0)
            return torch.from_numpy(np.zeros(shape, dtype=dtype)).to(device)
        return torch.from_numpy(np.concatenate(parts).astype(dtype, copy=False)).to(device)

    def tensor(value, dtype=np.int64):
        return torch.from_numpy(np.asarray(value, dtype=dtype)).to(device)

    phase = tensor(phase_values)
    return {'bytes': tensor(byte_np), 'lengths': torch.from_numpy(lengths_np),
            'paths': cat(paths, np.int64, width=MAX_DEPTH),
            'kinds': cat(kinds, np.int64), 'values': cat(values, np.int64),
            'numbers': cat(numbers, np.float32, width=4),
            'entities': cat(entities, np.int64),
            'edge_src': cat(edge_src, np.int64), 'edge_dst': cat(edge_dst, np.int64),
            'edge_word': cat(edge_word, np.int64), 'batches': cat(batches, np.int64),
            'action_index': tensor(action_np), 'mask': tensor(mask_np, np.bool_),
            'entity_count': offset, 'batch_size': len(pres),
            'phase': phase, 'drink_phase': phase == 1,
            'uniform_phase': phase_values[0] if len(set(phase_values)) == 1 else None,
            'lexemes': tuple(lexemes)}
