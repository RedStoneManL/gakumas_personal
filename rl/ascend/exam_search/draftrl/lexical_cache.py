"""Bounded lexical reuse within one frozen search policy version."""
import torch

def lexical(encoder, batch):
    cache = getattr(encoder, '_search_lex_cache', None)
    if cache is None or torch.is_grad_enabled():
        return encoder.word_vectors(batch['bytes'], batch['lengths'])
    words = batch['lexemes']
    missing = [i for i, word in enumerate(words) if word not in cache]
    if len(cache) + len(missing) > 16384:
        cache.clear()
        missing = list(range(len(words)))
    if missing:
        indices = torch.tensor(missing, device=batch['bytes'].device)
        lengths = batch['lengths'][missing]
        vectors = encoder.word_vectors(batch['bytes'][indices, :int(lengths.max())], lengths)
        for row, index in enumerate(missing):
            cache[words[index]] = vectors[row].detach()
    return torch.stack([cache[word] for word in words])

def search_encoders(model):
    encoders = [model.actor, model.critic]
    for role in ('actor_relational', 'critic_relational'):
        branch = getattr(model, role, None)
        if branch is not None:
            encoders.append(branch.encoder.stem)
    return tuple(encoders)
