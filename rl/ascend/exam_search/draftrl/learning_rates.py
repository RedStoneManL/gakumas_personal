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


def _groups(optimizer):
    """Accept historical five positional groups, or explicitly named v6 groups."""
    groups = optimizer.param_groups
    phases = tuple(PHASE_KEYS)
    extra = ('actor_relational', 'critic_relational')
    if len(groups) not in (len(phases), len(phases) + len(extra)):
        raise ValueError('Unexpected optimizer groups; cannot assign phase learning rates')
    names = [group.get('name') for group in groups]
    if len(groups) == len(phases) and all(name is None for name in names):
        return [(phase, phase, True, group) for phase, group in zip(phases, groups)]
    expected = set(phases + extra) if len(groups) == len(phases) + len(extra) else set(phases)
    if len(set(names)) != len(names) or set(names) != expected:
        raise ValueError('Optimizer group names must identify every phase and relational role exactly once')
    result = []
    for name, group in zip(names, groups):
        inherited = name in phases
        key = name if inherited else 'exam'
        if len(groups) != len(phases) and not {'schedule_key', 'inherited'} <= set(group):
            raise ValueError('Relational optimizer group metadata is missing')
        if group.get('schedule_key', key) != key or group.get('inherited', inherited) is not inherited:
            raise ValueError('Optimizer group learning rate ownership mismatch: ' + name)
        result.append((name, key, inherited, group))
    return result


def current(optimizer):
    return {name: group['lr'] for name, _, _, group in _groups(optimizer)}


def apply(optimizer, config, elapsed_minutes, *, completed_batches=None):
    groups = _groups(optimizer)
    state = scheduled(config, elapsed_minutes)
    from .relational_training import validate_config
    relational = validate_config(config)
    if (len(groups) == len(PHASE_KEYS) + 2) != relational:
        raise ValueError('Relational training configuration and optimizer groups disagree')
    if relational:
        cfg = config['relational']
        minutes = cfg.get('adaptation_minutes', 120.)
        # This is time in the new run, preserved by resume.  A later reset of the
        # ordinary LR schedule must not restart relational warm-start adaptation.
        age = number(elapsed_minutes, 'elapsed_minutes')
        if 'adaptation_batches' in cfg:
            if type(completed_batches) is not int or completed_batches < 0:
                raise ValueError('Batch-based relational adaptation requires explicit nonnegative completed_batches')
            fraction = min(1., completed_batches / cfg['adaptation_batches'])
            adaptation = {'basis': 'completed_batches', 'completed_batches': completed_batches,
                          'duration_batches': cfg['adaptation_batches']}
        else:
            fraction = min(1., age / minutes) if minutes else 1.
            adaptation = {'basis': 'elapsed_minutes', 'duration_minutes': minutes}
        initial = cfg.get('legacy_lr_ratio', .25)
        inherited_ratio = initial + fraction * (1. - initial)
        new_ratio = cfg.get('new_lr_multiplier', 1.)
        state['base_rates'] = dict(state['rates'])
        state['rates'] = {name: state['base_rates'][key] * (inherited_ratio if inherited else new_ratio)
                          for name, key, inherited, _ in groups}
        state['relational_adaptation'] = {
            **adaptation, 'elapsed_minutes': age, 'fraction': fraction,
            'inherited_ratio': inherited_ratio, 'new_ratio': new_ratio,
            'stage': 'complete' if fraction >= 1 else 'adapting',
        }
    for name, _, _, group in groups:
        group['lr'] = state['rates'][name]
    return state
