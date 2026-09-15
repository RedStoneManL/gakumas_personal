"""Explicit parameter and Adam migration to independent build/exam towers."""
import copy
from collections import Counter
import torch
from .legacy_model import DraftPolicy as LegacyPolicy
from .model import DraftPolicy, MODEL_SCHEMA


def groups(model, rates, eps=1e-5):
    result = []
    for phase in ('exam', 'drink', 'draft', 'guidance', 'memory'):
        params = [p for name, p in model.named_parameters() if
            (not name.startswith(('drink_', 'draft_', 'guidance_', 'memory_')) if phase == 'exam'
             else name.startswith(phase+'_'))]
        result.append({'params': params, 'lr': rates[phase]})
    return torch.optim.Adam(result, eps=eps)


def migrate(info, device='cpu', depth=4):
    if info['model_schema'] != 'hif-memory-draft-drink-exam-policy/1':
        raise ValueError('Only a legacy five-phase model is eligible for this migration')
    legacy = LegacyPolicy(**info['model_config'])
    legacy.load_state_dict(info['model_state'], strict=True)
    model = DraftPolicy(**info['model_config'], depth=depth, original=legacy).to(device)
    return model


def migrate_adam(info, model, optimizer):
    """Copy old moments into both towers; new identity blocks start fresh.

    This is an algorithm/version migration, not continuation of old on-policy
    data. All newly collected records must bind to the new policy version.
    """
    legacy = LegacyPolicy(**info['model_config'])
    old_groups = []
    for phase in ('exam', 'drink', 'draft', 'guidance', 'memory'):
        old_groups.append([name for name, _ in legacy.named_parameters() if
            (not name.startswith(('drink_', 'draft_', 'guidance_', 'memory_')) if phase == 'exam'
             else name.startswith(phase+'_'))])
    saved = info['optimizer_state']
    if len(saved['param_groups']) != 5:
        raise ValueError('Unrecognized legacy Adam groups')
    by_name = {}
    for names, group in zip(old_groups, saved['param_groups']):
        if len(names) != len(group['params']):
            raise ValueError('Legacy parameter ordering does not match checkpoint')
        by_name.update({name: saved['state'].get(index) for name, index in zip(names, group['params'])})
    target = optimizer.state_dict()
    parameter_names = {id(p): name for name, p in model.named_parameters()}
    counts = Counter()
    for live_group, serialized in zip(optimizer.param_groups, target['param_groups']):
        for parameter, index in zip(live_group['params'], serialized['params']):
            name = parameter_names[id(parameter)]
            source_name = model.legacy_parameter_name(name)
            source = by_name.get(source_name) if source_name is not None else None
            if source is None:
                counts['fresh_parameter_tensors'] += 1
                continue
            state = copy.deepcopy(source)
            for key in ('exp_avg', 'exp_avg_sq'):
                if key not in state or state[key].shape != parameter.shape:
                    raise ValueError(f'Adam shape mismatch for {name}')
            target['state'][index] = state
            counts['copied_parameter_tensors'] += 1
    optimizer.load_state_dict(target)
    return {'schema': 'arena-split-adam-migration/1', 'target_model_schema': MODEL_SCHEMA,
            'moments_copied_to_both_task_towers': True, 'new_residual_blocks_fresh': True,
            'old_rollout_data_reused': False, **counts}
