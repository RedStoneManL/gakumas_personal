"""One masked behavior distribution for both collection and PPO likelihoods."""
import math
import torch


def schedule(config, decisions, *, elapsed_minutes=None):
    spec = config.get('exploration_schedule', {})
    basis = spec.get('basis')
    if basis == 'elapsed_minutes':
        if elapsed_minutes is None:
            raise ValueError('wall-clock exploration schedule requires elapsed_minutes')
        hold = config['exploration_schedule']['hold_minutes']
        decay = config['exploration_schedule']['decay_minutes']
        origin = config['exploration_schedule'].get('origin_elapsed_minutes', 0.)
        if not all(math.isfinite(x) for x in (hold, decay, origin)) or min(hold, origin) < 0 or decay <= 0:
            raise ValueError('Invalid exploration schedule')
        fraction = min(1.0, max(0.0, (elapsed_minutes - origin - hold) / decay))
    elif basis == 'meaningful_decisions':
        origin = spec['origin_decisions']
        hold = spec.get('hold_decisions', 0)
        decay = spec['decay_decisions']
        if any(type(x) is not int or x < 0 for x in (decisions, origin, hold, decay)) or decay == 0:
            raise ValueError('Invalid meaningful-decision exploration schedule')
        fraction = min(1.0, max(0.0, (decisions - origin - hold) / decay))
    elif basis is None:
        fraction = min(1.0, max(0.0, decisions / config['exploration_decay_decisions']))
    else:
        raise ValueError('Unknown exploration schedule basis: '+str(basis))
    result = {}
    for phase in ('draft', 'guidance', 'drink', 'exam', 'memory'):
        result[phase] = {}
        for key in ('temperature', 'uniform_mix', 'entropy_coefficient'):
            begin, end = config['exploration'][phase][key]
            result[phase][key] = begin + fraction * (end - begin)
    return result


def parameters(examples, scheduled):
    return [dict(scheduled[('exam', 'drink', 'draft', 'guidance', 'memory')[e.phase]]) for e in examples]


def distributions(logits, mask, settings):
    """q(a|s)=(1-epsilon)*softmax(logits/T)+epsilon/number_of_legal_actions.

    The policy being differentiated by PPO is exactly the policy that sampled
    each action. Illegal padded actions retain probability zero. Settings are
    frozen with each rollout record, even when the global schedule advances.
    """
    if len(settings) != len(logits) or not mask.any(-1).all():
        raise ValueError('invalid masked behavior batch')
    for s in settings:
        if not math.isfinite(s['temperature']) or s['temperature'] <= 0 or not 0 <= s['uniform_mix'] < 1:
            raise ValueError('invalid exploration temperature/uniform mixture')
    temperature = logits.new_tensor([s['temperature'] for s in settings])[:, None]
    epsilon = logits.new_tensor([s['uniform_mix'] for s in settings])[:, None]
    base = torch.distributions.Categorical(logits=(logits / temperature).masked_fill(~mask, -torch.inf))
    prior = mask.to(logits.dtype) / mask.sum(-1, keepdim=True)
    for i, s in enumerate(settings):
        if 'action_prior' in s:
            values = logits.new_tensor(s['action_prior'])
            count = int(mask[i].sum())
            if len(values) != count or not torch.isfinite(values).all() or (values < 0).any() or not torch.isclose(values.sum(), values.new_tensor(1.)):
                raise ValueError('Invalid legal action exploration prior')
            prior[i, mask[i]] = values
    probabilities = ((1 - epsilon) * base.probs + epsilon * prior).masked_fill(~mask, 0)
    behavior = torch.distributions.Categorical(probs=probabilities)
    return behavior, base
