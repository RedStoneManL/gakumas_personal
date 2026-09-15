"""Real-return quantiles and one (not nested) Best-of-K expectation."""
import math


def mixture_best_of(samples, k=4):
    """Each simulation has equal mass; its atoms share that simulation's mass."""
    if not samples or k < 1:
        raise ValueError('Nonempty distribution and positive K required')
    atoms = []
    for sample in samples:
        values = sample if isinstance(sample, (list, tuple)) else [sample]
        if not values or any(not math.isfinite(v) for v in values):
            raise ValueError('Invalid return distribution')
        mass = 1. / len(samples) / len(values)
        atoms.extend((float(v), mass) for v in values)
    atoms.sort()
    cumulative = 0.
    result = 0.
    for value, mass in atoms:
        following = min(1., cumulative + mass)
        result += value * (following**k - cumulative**k)
        cumulative = following
    return result


def sample_mean(value):
    return sum(value)/len(value) if isinstance(value, (list, tuple)) else value


def quantile_loss(predictions, targets):
    """Pinball loss on each state's OWN completed outcome; no sibling relabels."""
    import torch
    n = predictions.shape[-1]
    taus = (torch.arange(n, device=predictions.device, dtype=predictions.dtype)+.5)/n
    delta = targets[:, None]-predictions
    return torch.maximum(taus*delta, (taus-1)*delta).mean(-1)


def best_of_tensor(quantiles, k=4):
    import torch
    n = quantiles.shape[-1]
    edges = torch.arange(n+1,device=quantiles.device,dtype=quantiles.dtype)/n
    weights = edges[1:]**k - edges[:-1]**k
    return (quantiles.sort(-1).values*weights).sum(-1)
