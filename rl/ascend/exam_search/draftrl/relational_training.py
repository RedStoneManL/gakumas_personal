"""Versioned relational warm start and explicit parameter groups; no device backend changes."""
import copy
import math

SCHEMA = 'arena-joint-relational/1'
PHASES = ('exam', 'drink', 'draft', 'guidance', 'memory')
PREFIXES = ('drink_', 'draft_', 'guidance_', 'memory_')


def is_relational(name):
    return name.startswith(('actor_relational.', 'critic_relational.'))


def parameter_groups(model, rates):
    result = []
    for phase in PHASES:
        params = [p for name, p in model.named_parameters()
                  if not is_relational(name) and
                  (not name.startswith(PREFIXES) if phase == 'exam' else name.startswith(phase + '_'))]
        result.append({'params': params, 'lr': rates[phase], 'name': phase,
                       'schedule_key': phase, 'inherited': True})
    for role in ('actor', 'critic'):
        params = [p for name, p in model.named_parameters() if name.startswith(role + '_relational.')]
        if params:
            result.append({'params': params, 'lr': rates['exam'], 'name': role + '_relational',
                           'schedule_key': 'exam', 'inherited': False})
    ids = [id(p) for group in result for p in group['params']]
    if len(ids) != len(set(ids)) or set(ids) != {id(p) for p in model.parameters()}:
        raise ValueError('Optimizer groups must own every parameter exactly once')
    return result


def named_groups(model, optimizer):
    lookup = {id(p): n for n, p in model.named_parameters()}
    return [[lookup[id(p)] for p in group['params']] for group in optimizer.param_groups]


def migrate_optimizer(info, model, optimizer, device):
    """Copy inherited moments by NAME, never by coincidental serialized index."""
    import torch
    from .model import DraftPolicy
    from .legacy_model import DraftPolicy as Legacy
    names = info.get('optimizer_parameter_names')
    if names is None:
        cls = Legacy if info['model_schema'] == 'hif-memory-draft-drink-exam-policy/1' else DraftPolicy
        # Constructor is only for historical ordering; never changes training RNG.
        with torch.random.fork_rng(devices=[]):
            old_model = cls(**info['model_config'])
        old_groups = parameter_groups(old_model, dict.fromkeys(PHASES, 1.))
        lookup = {id(p): n for n, p in old_model.named_parameters()}
        names = [[lookup[id(p)] for p in g['params']] for g in old_groups]
    saved = info['optimizer_state']
    if len(names) != len(saved['param_groups']):
        raise ValueError('Checkpoint optimizer group identity is ambiguous')
    old = {}
    for group_names, group in zip(names, saved['param_groups']):
        if len(group_names) != len(group['params']):
            raise ValueError('Checkpoint optimizer parameter count mismatch')
        for name, index in zip(group_names, group['params']):
            if name in old:
                raise ValueError('Duplicate checkpoint optimizer parameter name')
            old[name] = saved['state'].get(index)
    lookup = {id(p): name for name, p in model.named_parameters()}
    copied = fresh = 0
    for group in optimizer.param_groups:
        for parameter in group['params']:
            name = lookup[id(parameter)]
            source_name = name
            if info['model_schema'] == 'hif-memory-draft-drink-exam-policy/1':
                source_name = None if is_relational(name) else model.legacy_parameter_name(name)
            state = old.get(source_name)
            if state is None:
                fresh += 1
                continue
            state = copy.deepcopy(state)
            for key in ('exp_avg', 'exp_avg_sq'):
                if key not in state or state[key].shape != parameter.shape:
                    raise ValueError('Adam tensor mismatch: ' + name)
                state[key] = state[key].to(device=parameter.device, dtype=parameter.dtype)
            # Adam's non-capturable step remains CPU, as in the existing loader.
            if isinstance(state.get('step'), torch.Tensor):
                state['step'] = state['step'].cpu()
            optimizer.state[parameter] = state
            copied += 1
    return {'mode': 'named-relational-warm-start', 'copied_parameter_tensors': copied,
            'fresh_parameter_tensors': fresh, 'old_rollout_data_reused': False}


def validate_config(config):
    cfg = config.get('relational', {})
    if not isinstance(cfg, dict) or type(cfg.get('enabled', False)) is not bool:
        raise ValueError('Relational configuration must be an object with a boolean enabled flag')
    if not cfg.get('enabled', False):
        return False
    if cfg.get('schema') != SCHEMA:
        raise ValueError('Unknown relational configuration schema')
    allowed = {'enabled', 'schema', 'semantics_path', 'legacy_lr_ratio', 'adaptation_minutes', 'adaptation_batches',
               'new_lr_multiplier'}
    if set(cfg) - allowed:
        raise ValueError('Unknown relational settings: ' + repr(sorted(set(cfg) - allowed)))
    for key, default in (('legacy_lr_ratio', .25), ('adaptation_minutes', 120.), ('new_lr_multiplier', 1.)):
        value = cfg.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Invalid relational setting: ' + key)
        if value < 0 or (key != 'adaptation_minutes' and value == 0):
            raise ValueError('Relational rates must be positive')
    if cfg.get('legacy_lr_ratio', .25) > 1:
        raise ValueError('Legacy adaptation ratio must not exceed one')
    if 'adaptation_batches' in cfg:
        batches = cfg['adaptation_batches']
        if type(batches) is not int or batches <= 0:
            raise ValueError('Relational adaptation_batches must be a positive integer')
    return True
