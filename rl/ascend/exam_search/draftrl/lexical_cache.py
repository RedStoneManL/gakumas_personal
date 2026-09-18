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
    if model is None:  # Pool-capacity probes do not construct a policy.
        return ()
    encoders = [getattr(model, role) for role in ('actor', 'critic')
                if getattr(model, role, None) is not None]
    for role in ('actor_relational', 'critic_relational'):
        branch = getattr(model, role, None)
        if branch is not None:
            encoders.append(branch.encoder.stem)
    return tuple(encoders)


def cached_rollout(function):
    """Reuse lexical vectors only inside one frozen-policy collection stage."""
    from functools import wraps
    @wraps(function)
    def wrapped(pool, model, *args, **kwargs):
        encoders = search_encoders(model)
        previous = [getattr(encoder, '_search_lex_cache', None) for encoder in encoders]
        try:
            for encoder in encoders:
                encoder._search_lex_cache = {}
            return function(pool, model, *args, **kwargs)
        finally:
            # PPO runs outside the scope; no embedding from an earlier policy survives.
            for encoder, cache in zip(encoders, previous):
                encoder._search_lex_cache = cache
    return wrapped
