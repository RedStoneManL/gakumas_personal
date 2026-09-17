"""Finish one value pass after actor KL stopping, without replaying actions."""
import time
import torch
from gakumas_training.device import optimizer_options
from .encoding import collate
from .update_diagnostics import update_coverage
from . import sharded
from .value_calibration import state_digest
from .value_distribution import quantile_loss
from .kl_value_migration import SETTINGS

HEADS = {'value_head', 'drink_value_head', 'draft_value_head',
         'guidance_value_head', 'memory_value_head', 'exam_quantile_head'}


def value_parameter(name):
    return name.startswith('critic.') or name.split('.')[0] in HEADS


def complete_values(model, optimizer, records, targets, weights, accepted,
                    attempted, order, config, device, progress=None, mesh=None):
    if config.get('critic_completion') != SETTINGS:
        raise ValueError('Unaudited critic completion settings')
    remaining = [i for i in order if i not in accepted]
    if len(set(order)) != len(records) or set(order) != set(range(len(records))):
        raise ValueError('Critic completion must cover the current rollout exactly')
    value_accepted, value_attempted = set(accepted), set(attempted)
    frozen = lambda name: not value_parameter(name)
    before = state_digest(model, frozen)
    flags = {name: parameter.requires_grad for name, parameter in model.named_parameters()}
    selected_parameters = [p for n, p in model.named_parameters() if value_parameter(n)]
    losses, value_losses, distribution_losses, norms = [], [], [], []
    last_progress = time.monotonic()
    try:
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(flags[name] and value_parameter(name))
        # Two layouts. shared: every rank holds the same full record list (the group
        # broadcast it, as before this change), so blocks are global and strided.
        # local: each rank holds only its own records; block_plan keeps the ranks in
        # lockstep and block_length supplies the global divisor.
        shared = mesh is not None and getattr(mesh, 'shared_records', False)
        local_mesh = None if shared else mesh
        if shared:
            effective = config['effective_minibatch']
            num_blocks = -(-len(remaining) // effective)
            bounds = [(i*effective, min((i+1)*effective, len(remaining))) for i in range(num_blocks)]
        else:
            bounds, num_blocks, _ = sharded.block_plan(local_mesh, len(remaining), config['effective_minibatch'])
        for block_index in range(num_blocks):
            start, end = bounds[block_index]
            block = remaining[start:end]
            block_size = len(block) if shared else sharded.block_length(local_mesh, len(block))
            optimizer.zero_grad(set_to_none=True)
            value_attempted.update(block)
            block_value = block_distribution = block_loss = 0.
            shard = block[mesh.rank::mesh.size] if shared else block
            for offset in range(0, len(shard), config['minibatch']):
                indices = shard[offset:offset+config['minibatch']]
                batch = collate([records[i]['encoded'] for i in indices], device)
                values, atoms = model.value_outputs(batch)
                truth = targets[indices].to(device)
                weight = weights[indices].to(device)
                scalar = (torch.nn.functional.smooth_l1_loss(values, truth, reduction='none')
                          * weight).sum()/block_size
                distribution = values.new_zeros(())
                if atoms is not None:
                    distribution = (quantile_loss(atoms, truth) * weight
                                    * (batch['phase']==0)).sum()/block_size
                loss = config['value_coefficient']*scalar + config.get(
                    'value_calibration', {}).get('distribution_coefficient', 1.)*distribution
                if not torch.isfinite(loss):
                    raise FloatingPointError('Nonfinite critic-only completion loss')
                loss.backward()
                block_loss += float(loss.detach())
                block_value += float(scalar.detach())
                block_distribution += float(distribution.detach())
            if any(p.grad is not None for n, p in model.named_parameters() if frozen(n)):
                raise RuntimeError('Actor gradient leaked into critic completion')
            if mesh is not None:
                mesh.gradients(model)
                totals = mesh.sum_values({'loss': block_loss, 'value': block_value,
                                          'distribution': block_distribution})
                block_loss, block_value, block_distribution = (totals[k] for k in ('loss', 'value', 'distribution'))
            norm = torch.nn.utils.clip_grad_norm_(selected_parameters, config['max_grad'],
                                                 error_if_nonfinite=True, **optimizer_options(model))
            optimizer.step()
            value_accepted.update(block)
            losses.append(block_loss); value_losses.append(block_value)
            distribution_losses.append(block_distribution); norms.append(float(norm))
            if progress is not None and time.monotonic()-last_progress >= 30:
                progress(stage='critic_completion', records_seen=end,
                         records_total=len(remaining), optimizer_steps=len(losses), actor_frozen=True)
                last_progress = time.monotonic()
    finally:
        optimizer.zero_grad(set_to_none=True)
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(flags[name])
    after = state_digest(model, frozen)
    if before != after:
        raise RuntimeError('Critic completion changed frozen actor parameters')
    if value_accepted != set(range(len(records))):
        raise RuntimeError('Incomplete value pass')
    mean = lambda values: sum(values)/len(values) if values else 0.
    return {'enabled': True, 'completed_records': len(remaining), 'optimizer_steps': len(losses),
            'loss': mean(losses), 'value_loss': mean(value_losses),
            'distribution_loss': mean(distribution_losses), 'grad_norm': mean(norms),
            'actor_unchanged': True, 'actor_sha256_before': before, 'actor_sha256_after': after,
            'coverage': sharded.reduce_coverage(local_mesh, update_coverage(records, value_accepted, value_attempted)),
            'target_semantics': 'Current batch actual returns: construction Best4 and own-exam terminal distribution.',
            'policy_replay': False}
