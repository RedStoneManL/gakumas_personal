"""Continuous exploration migration at a committed real-decision boundary."""
import copy
import math

from .distribution import schedule

PHASES = ('exam', 'drink', 'draft', 'guidance', 'memory')
KEYS = ('temperature', 'uniform_mix', 'entropy_coefficient')
CHANGED_FIELDS = {'exploration', 'exploration_schedule'}


def make_decision_config(source, decisions, snapshot, decay_decisions):
    if source.get('exploration_schedule', {}).get('basis') != 'elapsed_minutes':
        raise ValueError('Expected the explicitly selected wall-clock source')
    if type(decisions) is not int or decisions < 0:
        raise ValueError('Invalid committed decision boundary')
    if type(decay_decisions) is not int or decay_decisions <= 0:
        raise ValueError('Invalid remaining decision horizon')
    target = copy.deepcopy(source)
    for phase in PHASES:
        for key in KEYS:
            value = snapshot[phase][key]
            start, end = source['exploration'][phase][key]
            if not math.isfinite(value) or not min(start, end) <= value <= max(start, end):
                raise ValueError('Boundary exploration is outside the source schedule')
            target['exploration'][phase][key] = [value, end]
    target['exploration_schedule'] = {
        'basis': 'meaningful_decisions', 'origin_decisions': decisions,
        'hold_decisions': 0, 'decay_decisions': decay_decisions,
    }
    if schedule(target, decisions) != snapshot:
        raise ValueError('Exploration continuity failed at the boundary')
    return target


def validate_change(source, target, *, decisions=None, snapshot=None):
    before = {k:v for k,v in source.items() if k not in CHANGED_FIELDS}
    after = {k:v for k,v in target.items() if k not in CHANGED_FIELDS}
    if before != after:
        raise ValueError('Exploration migration changed unrelated training parameters')
    if source == target:
        return {}
    spec = target.get('exploration_schedule', {})
    if spec.get('basis') != 'meaningful_decisions':
        raise ValueError('Only meaningful-decision exploration migration is authorized')
    origin = spec['origin_decisions']
    expected_snapshot = (snapshot if snapshot is not None else
        {p:{k:target['exploration'][p][k][0] for k in KEYS} for p in PHASES})
    if decisions is not None and origin != decisions:
        raise ValueError('Exploration origin differs from committed decisions')
    expected = make_decision_config(source, origin, expected_snapshot, spec['decay_decisions'])
    if expected != target:
        raise ValueError('Exploration endpoints or schedule changed outside the migration')
    return {'basis': spec['basis'], 'origin_decisions': origin,
        'decay_decisions': spec['decay_decisions'], 'boundary_values': expected_snapshot,
        'continuous_at_boundary': True,
        'counter': 'Committed completed-training-episode decisions with more than one legal action; each real decision once, including current-policy four-game repeats and bank exams. Excludes search simulations, evaluations, forced actions, and optimizer epochs.'}
