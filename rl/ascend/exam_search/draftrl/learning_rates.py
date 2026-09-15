"""Explicit per-group learning rates, applied after Adam restore and between batches."""
import math

PHASE_KEYS = {'exam': 'learning_rate', 'drink': 'drink_learning_rate',
              'draft': 'draft_learning_rate', 'guidance': 'guidance_learning_rate',
              'memory': 'memory_learning_rate'}


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'Invalid learning rate setting: {name}')
    return float(value)


def validate_schedule(config):
    for key in PHASE_KEYS.values():
        if number(config[key], key) <= 0:
            raise ValueError('Learning rates must be positive')
    plan = config.get('learning_rate_schedule')
    if plan is None:
        return None
    if not isinstance(plan, dict) or plan.get('schema') != 'arena-learning-rate-linear/1' or plan.get('basis') != 'elapsed_minutes':
        raise ValueError('Invalid learning rate schedule schema')
    origin, hold, decay, floor = [number(plan.get(k), k) for k in
        ('origin_elapsed_minutes', 'hold_minutes', 'decay_minutes', 'min_ratio')]
    if origin < 0 or hold < 0 or decay <= 0 or not 0 < floor <= 1:
        raise ValueError('Invalid learning rate schedule bounds')
    return plan


def scheduled(config, elapsed_minutes):
    plan = validate_schedule(config)
    elapsed = number(elapsed_minutes, 'elapsed_minutes')
    if elapsed < 0:
        raise ValueError('Elapsed minutes must be nonnegative')
    age = max(0., elapsed - plan['origin_elapsed_minutes']) if plan else 0.
    fraction = min(1., max(0., (age-plan['hold_minutes'])/plan['decay_minutes'])) if plan else 0.
    ratio = 1. - fraction*(1.-plan['min_ratio']) if plan else 1.
    return {'rates': {phase: config[key]*ratio for phase, key in PHASE_KEYS.items()},
            'elapsed_since_reset_minutes': age, 'decay_fraction': fraction,
            'stage': ('constant' if plan is None else 'hold' if age <= plan['hold_minutes']
                      else 'floor' if fraction >= 1 else 'decay')}


def current(optimizer):
    if len(optimizer.param_groups) != len(PHASE_KEYS):
        raise ValueError('Unexpected optimizer groups; cannot assign phase learning rates')
    return {phase: group['lr'] for phase, group in zip(PHASE_KEYS, optimizer.param_groups)}


def apply(optimizer, config, elapsed_minutes):
    current(optimizer)
    state = scheduled(config, elapsed_minutes)
    for phase, group in zip(PHASE_KEYS, optimizer.param_groups):
        group['lr'] = state['rates'][phase]
    return state
