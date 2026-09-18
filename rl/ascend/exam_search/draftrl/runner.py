from __future__ import annotations
import copy
import ctypes
import hashlib
import json
import math
import os
import random
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import torch
from .encoding import DraftEncoder, DraftState, encode_guidance, encode_drink_inventory, encode_exam, collate
from .guidance import Guidance
from .memory import MemoryState
from .scenarios import assign
from .general_scenarios import augment, prepare_memory_mode
from .drinks import DrinkInventory
from .contracts import validate_entry
from .deck_size import counted_size, exempt_count
from .choice import ChoiceState
POLICY_VISIBILITY = 'full-at-exam-start'
RUNNER_SCHEMA = 'arena-generalist-joint-search/1'
from .checkpoint import transfer, load, save, digest, json_write, source_version
from r1rl.environment import Workers, arena_module
from .distributed import update_distributed as update
from gakumas_training.device import resolve_device, seed_device, device_report, optimizer_options, empty_accelerator_cache, load_optimizer_state
from .distribution import distributions, schedule, parameters
from .runtime_window import RuntimeWindow
from .resource_modes import RuntimeResources
from .sample_bank import SampleBank
from .bank_rollout import rollout_bank
from .async_decisions import AsyncDecisions
from .practice import mode_for, routed_parameters, make_fork_tasks, apply_fork_returns, practice_diagnostics, fork_coverage, auxiliary_controller
from .best_of import summarize_groups
from .coverage import Coverage
from .play_evaluation import prepare_suite, evaluate_play
from .gradient_diagnostics import inspect_gradients
from .construction_reward import duplicate_stats, apply_draft_penalty
from . import keycard_focus
from .keycard_probe import check as keycard_check
from . import duplicate_limits
from . import learning_rates
from . import stage_progress


def append(path, row):
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def hash_entry(entry):
    return hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def choose(model, examples, device, greedy=False, driver='policy', rngs=None, exploration=None, *, settings_override=None):
    with torch.no_grad():
        batch = collate(examples, device)
        if greedy:
            logits, values = model.policy(batch), None
            value_best4 = None
        else:
            logits, values, atoms = model.learning_forward(batch)
            from .value_distribution import best_of_tensor
            value_best4 = best_of_tensor(atoms).tolist() if atoms is not None else None
        settings = (parameters(examples, exploration) if exploration else
                    [{'temperature': 1.0, 'uniform_mix': 0.0, 'entropy_coefficient': 0.0} for e in examples])
        if settings_override is not None:settings=settings_override
        distribution, base = distributions(logits, batch['mask'], settings)
        if driver == 'random':
            selected = torch.tensor([rng.randrange(len(e.submissions)) for rng, e in zip(rngs, examples)], device=device)
        else:
            selected = logits.argmax(-1) if greedy else distribution.sample()
        logp = distribution.log_prob(selected)
        if not torch.isfinite(logp).all() or (values is not None and not torch.isfinite(values).all()):
            raise FloatingPointError('invalid policy output')
        norm = batch['mask'].sum(-1).float().log().clamp_min(1)
        diagnostics = [{'behavior_entropy_fraction': h, 'base_entropy_fraction': b,
                        'behavior_max_probability': p, 'base_max_probability': q}
                       for h, b, p, q in zip((distribution.entropy() / norm).tolist(),
                       (base.entropy() / norm).tolist(), distribution.probs.max(-1).values.tolist(),
                       base.probs.max(-1).values.tolist())]
        if value_best4 is not None:
            for e,d,v,a in zip(examples,diagnostics,value_best4,atoms.tolist()):
                if e.phase == 0:
                    d.update(predicted_best4=v,old_return_atoms=a,value_prediction_mode='frozen_pre_action')
    return selected.tolist(), logp.tolist(), (values.tolist() if values is not None else [None]*len(examples)), settings, diagnostics


def rollout(pool, model, entry, catalog, config, device, start_seed, *, count=None,
            target_decisions=None, greedy=False, fixed_drinks=None, spec=None, driver='policy', log_path=None, exploration=None, scenario_bank=None,keep_entries=False,
            index_offset=0, seed_stride=1):
    """One frozen current policy across construction, resources, memories and exam."""
    assert (count is None) != (target_decisions is None)
    training = target_decisions is not None
    if training and (driver != 'policy' or fixed_drinks is not None):
        raise ValueError('Diagnostic behavior or fixed drinks cannot produce PPO samples')
    rollout_source = source_version()
    print(json.dumps({'event': 'rollout_begin', 'schema': RUNNER_SCHEMA,
        'source_sha256': rollout_source, 'start_seed': start_seed, 'training': training,
        'target_decisions': target_decisions, 'episode_count': count}), flush=True)
    active, records, summaries = {}, [], []
    router = config.get('_search_router') if training else None
    flow = AsyncDecisions(router) if router else None
    next_seed, started, meaningful = start_seed, 0, 0
    from . import distributed as _dist
    _shards = _dist.ACTIVE.size if _dist.ACTIVE is not None else 1
    stage_progress.begin('collect' if training else 'evaluate',
        target_decisions if training else count,
        'decisions' if training else 'episodes', shards=_shards)
    rollout_started = time.monotonic()
    last_log = rollout_started

    def can_start():
        return started < count if count is not None else meaningful < target_decisions

    def begin_exam(i, row):
        row['entry'] = copy.deepcopy(row['memory'].entry)
        if len(row['entry']['resources']['drinks']) > row['drink_capacity']:
            raise ValueError('Drink loadout exceeds this scenario capacity')
        validate_entry(row['entry'], row['spec'], catalog, row['drink_pool'])
        row['keycard_tracking'] = keycard_focus.tracker(row['entry'])
        pool.send(i, 'reset', (row['entry'], row['seed']))
        _answer = pool.receive(i)
        row['obs'] = _answer['observation']
        row['pre_encoded'] = _answer.get('encoded')
        row['resolved_turn_types'] = list(row['obs']['context']['turn_types'])
        row['phase'] = 'exam'
        if row['obs']['result']['terminated'] or row['obs']['result']['truncated']:
            raise RuntimeError('invalid opening boundary')

    def begin_memory(i, row):
        ready = copy.deepcopy(row['guidance'].entry)
        ready['resources']['drinks'] = list(row['drinks'])
        row['memory'] = MemoryState(ready, catalog, row['spec'])
        # A disabled phase has no action, no fabricated finish command and no PPO row.
        if row['memory'].done:
            begin_exam(i, row)
        else:
            row['phase'] = 'memory'

    def begin_drinks(i, row):
        # This inventory is revealed only after the public deck and guidance are fixed.
        # Its independent sampling seed is diagnostic metadata, never a neural input.
        capacity = row['drink_capacity']
        if fixed_drinks is not None:
            if len(fixed_drinks) > capacity or not set(fixed_drinks) <= set(row['drink_pool']):
                raise ValueError('Fixed diagnostic drinks violate the scenario contract')
            row['drinks'] = list(fixed_drinks)
            row['drink_supply'] = {'supply_mode': 'fixed-diagnostic', 'capacity': capacity}
            begin_memory(i, row)
            return
        if capacity == 0:
            row['drinks'] = []
            row['drink_supply'] = {'supply_mode': 'disabled', 'capacity': 0,
                'selected': [], 'initial_inventory': {}, 'remaining_inventory': {}, 'done': True}
            begin_memory(i, row)
            return
        slot = row['local_index'] % 10
        mode = 'random' if slot < 7 else 'low_supply' if slot < 9 else 'coverage'
        target = row['drink_pool'][(row['local_index'] // 10) % len(row['drink_pool'])]
        row['inventory'] = DrinkInventory(row['drink_pool'], row['seed'] + 70_000_000,
            mode=mode, coverage_id=target if mode == 'coverage' else None, capacity=capacity)
        row['drinks'] = list(row['inventory'].selected)
        row['drink_supply'] = row['inventory'].public_summary()
        if row['inventory'].done:
            begin_memory(i, row)
        else:
            row['phase'] = 'drinks'

    while active or can_start():
        for i in range(config['workers']):
            if i not in active and can_start():
                index = next_seed - config['train_seed_base'] if target_decisions is not None else started + index_offset
                profile = config['_profiles'][index % len(config['_profiles'])]
                local_index = index // len(config['_profiles'])
                scene_index = local_index // len(profile['spec']['scenarios'])
                mode_entry, mode_spec, memory_mode = prepare_memory_mode(profile['entry'], profile['spec'], scene_index)
                scenario_entry, scenario_spec, scenario = assign(mode_entry, mode_spec, local_index,
                    coverage=target_decisions is not None and config.get('coverage_enabled', False))
                scenario_entry, scenario_spec, general = augment(scenario_entry, scenario_spec,
                    scene_index, next_seed, training=training)
                scenario_entry, scenario_spec = keycard_focus.prepare(scenario_entry, scenario_spec,
                    config, profile['id'], training=training)
                scenario_spec = duplicate_limits.prepare_spec(scenario_spec, config)
                if (general['memory_mode'], general['memory_capacity']) != (memory_mode['memory_mode'], memory_mode['memory_capacity']):
                    raise ValueError('Scene memory availability changed after coverage assignment')
                capacity = general['drink_capacity']
                if type(capacity) is not int or not 0 <= capacity <= 4:
                    raise ValueError('Scenario drink capacity must be an integer in 0..4')
                if scenario_spec.get('drink_capacity') != capacity:
                    raise ValueError('Scenario metadata and public capacity contract differ')
                multiplier = float(general['score_normalizer_multiplier'])
                if not math.isfinite(multiplier) or multiplier <= 0:
                    raise ValueError('Scenario score normalization must be finite and positive')
                course = str(general.get('course_id', general.get('course', 'unknown')))
                if course == 'unknown':
                    raise ValueError('Scenario must identify its exogenous course')
                draft = DraftEncoder(scenario_entry, catalog, scenario_spec)
                row = {'seed': next_seed, 'scenario': scenario, 'spec': scenario_spec, 'profile':profile['id'], 'plan':profile['plan'], 'drink_pool':profile['drink_pool'], 'score_scale':profile['score_scale'] * multiplier,
                       'general_scenario':general, 'course_id':course, 'drink_capacity':capacity,
                       'memory_mode':general['memory_mode'], 'memory_capacity':general['memory_capacity'],
                       'condition_cell':f"{general['memory_mode']}|drinks={capacity}",
                       'local_index':local_index, 'inventory':None,
                       'benchmark_cell':f"{profile['id']}__{course}__capacity{capacity}__memory-{general['memory_mode']}",
                       'drinks': [], 'phase': 'draft', 'draft': DraftState(draft), 'records': [], 'submissions': [],
                       'drink_choices': [], 'rng': random.Random(next_seed + 40000000), 'steps': 0, 'drink_used': 0,
                       'choice_state':None, 'choice_steps':[],
                       'exploration_mode':mode_for(config,local_index,training)}
                row['search_enabled'] = bool(router and router.select_episode(local_index))
                if training and auxiliary_controller(config) is not None:
                    row['controller_contract'] = auxiliary_controller(config)
                # seed_stride > 1 lets sharded learners walk disjoint interleaved seed
                # streams (rank r starts at start_seed + r and steps by the rank count),
                # so no two ranks can ever simulate the same episode.
                next_seed += seed_stride; started += 1
                active[i] = row
        blocked = set(flow.pending) if flow else set()
        ready = flow.poll(wait=bool(blocked) and len(blocked)==len(active)) if flow else []
        ids = [i for i in active if i not in blocked]
        examples = []
        for i in ids:
            row = active[i]
            if row['phase'] == 'draft':
                e = row['draft'].encode()
            elif row['phase'] == 'guidance':
                e = encode_guidance(row['guidance'], catalog)
            elif row['phase'] == 'drinks':
                e = encode_drink_inventory(row['inventory'], row['guidance'].entry, catalog, row['spec'])
            elif row['phase'] == 'memory':
                e = row['memory'].encode()
            else:
                if row['obs'].get('choice') is not None:
                    if row['choice_state'] is None:row['choice_state']=ChoiceState(row['obs'])
                    e=row['choice_state'].encode()
                else:
                    # Pre-encoded by the arena worker (r1rl.environment.worker) for plain
                    # exam views; anything else is encoded here as before.
                    e = row.get('pre_encoded')
                    if e is None:
                        e = encode_exam(row['obs'])
            examples.append(e)
        if ids:
            actions, logps, values, settings, diagnostics = choose(model, examples, device, greedy, driver,
                [active[i]['rng'] for i in ids], exploration,
                settings_override=routed_parameters(examples,[active[i]['exploration_mode'] for i in ids],exploration,config))
        else:
            actions, logps, values, settings, diagnostics = [], [], [], [], []
        proposals = list(zip(ids, examples, actions, logps, values, settings, diagnostics))
        if flow is not None:
            items = [
                {'worker': i, 'encoded': e, 'enabled': row['phase'] == 'exam' and row['search_enabled'],
                 'entry': row.get('entry'), 'observation': row.get('obs'), 'profile': row['profile'],
                 'score_scale': row['score_scale'], 'episode_id': f"joint:{row['seed']}",
                 'partial_selection': row['choice_state'].selected if row['choice_state'] else []}
                for i, e in zip(ids, examples) for row in [active[i]]]
            ready.extend(flow.submit(pool, items, proposals, config['_policy_version']))
        else:
            ready.extend((*proposal, {'loss_kind': 'ppo'}) for proposal in proposals)
        awaiting = []
        for i, e, action, logp, value, setting, diagnostic, extra in ready:
            row = active[i]
            command = e.submissions[action]
            if training and config.get('_coverage') is not None:
                config['_coverage'].observe(row,e,action)
            row['records'].append({'encoded': e, 'action': action, 'old_logp': logp, 'old_value': value,
                                   'episode_id':f"joint:{row['seed']}",'terminal':False,
                                   'policy_version':config.get('_policy_version'),
                                   'sampling_source':'joint' if training else 'validation',
                                   'exploration': setting, 'profile':row['profile'], 'plan':row['plan'],
                                   'exploration_mode':row['exploration_mode'],
                                   'course_id':row['course_id'], 'drink_capacity':row['drink_capacity'],
                                   'memory_mode':row['memory_mode'], 'memory_capacity':row['memory_capacity'],
                                    'condition_cell':row['condition_cell'], **diagnostic, **extra})
            if 'controller_contract' in row:
                row['records'][-1]['controller_contract'] = dict(row['controller_contract'])
            row['steps'] += 1
            meaningful += len(e.submissions) > 1
            if row['phase'] == 'draft':
                row['draft'].apply(command)
                if row['draft'].done:
                    row['draft_choices'] = row['draft'].history
                    row['guidance'] = Guidance(row['draft'].complete(), row['spec'])
                    row['phase'] = 'guidance'
            elif row['phase'] == 'guidance':
                row['guidance'].apply(command)
                if row['guidance'].done:
                    begin_drinks(i, row)
            elif row['phase'] == 'drinks':
                row['drink_choices'].append(command)
                row['inventory'].apply(command)
                row['drinks'] = list(row['inventory'].selected)
                row['drink_supply'] = row['inventory'].public_summary()
                if row['inventory'].done:
                    begin_memory(i, row)
            elif row['phase'] == 'memory':
                row['memory'].apply(command)
                if row['memory'].done:
                    begin_exam(i, row)
            else:
                if row['choice_state'] is not None:
                    row['choice_steps'].append({'native_decision_version':row['obs']['decision_version'],
                        'selected_before':list(row['choice_state'].selected),'command':command})
                    command=row['choice_state'].apply(command)
                    if command is None:continue
                    row['choice_state']=None
                row['drink_used'] += command.get('action', {}).get('type') == 'drink'
                keycard_focus.observe(row['keycard_tracking'], row['obs'], command)
                row['submissions'].append(command)
                pool.send(i, 'step', command)
                awaiting.append(i)
        for i in awaiting:
            row = active[i]
            _answer = pool.receive(i)
            row['obs'] = _answer['observation']
            row['pre_encoded'] = _answer.get('encoded')
            result = row['obs']['result']
            if result['truncated']:
                raise RuntimeError('truncated episode; no terminal reward fabricated')
            if result['terminated']:
                score = result['final_score']
                if score is None or not math.isfinite(score):
                    raise RuntimeError('no authoritative terminal score')
                for r in row['records']:
                    r['return'] = score / row['score_scale']
                row['records'][-1]['terminal']=True
                # Evaluation records need not retain the (large) neural inputs.
                if target_decisions is not None:
                    records.extend(row['records'])
                summary = {k: row[k] for k in ('seed', 'profile', 'plan', 'drinks', 'drink_choices', 'submissions', 'entry', 'draft_choices')}
                summary.update(schema=RUNNER_SCHEMA, source_sha256=rollout_source,
                    search_enabled=row['search_enabled'],
                    general_scenario=row['general_scenario'], course_id=row['course_id'],
                    drink_capacity=row['drink_capacity'], drink_supply=row['drink_supply'],
                    memory_mode=row['memory_mode'], memory_capacity=row['memory_capacity'],
                    condition_cell=row['condition_cell'],
                    benchmark_cell=row['benchmark_cell'], score_scale=row['score_scale'],
                    normalized_score=score / row['score_scale'])
                summary['guidance_choices'] = row['guidance'].history
                if 'controller_contract' in row:
                    summary['controller_contract'] = dict(row['controller_contract'])
                summary['keycard_focus'] = bool(row['spec'].get('required_initial_guidance'))
                summary['keycard_usage'] = keycard_focus.finish(row['keycard_tracking'])
                summary['choice_steps'] = row['choice_steps']
                summary['scenario'] = row['scenario']
                summary['resolved_turn_types'] = row['resolved_turn_types']
                summary['policy_turn_visibility'] = POLICY_VISIBILITY
                summary['memory_choices'] = row['memory'].history
                summary['selected_memories'] = sorted(row['memory'].selected)
                summary['memory_phase_decisions'] = sum(r['encoded'].phase == 4 for r in row['records'])
                if row['memory_mode'] == 'none' and (summary['selected_memories'] or summary['memory_choices'] or summary['memory_phase_decisions']):
                    raise RuntimeError('Disabled HIF memory scene generated a memory effect or decision')
                summary['initial_sleep_count'] = sum(c['definition_id'] == 23 for c in row['entry']['cards'])
                sleep_ids = {c['instance_id'] for c in row['entry']['cards'] if c['definition_id'] == 23}
                summary['removed_sleep_count'] = len(sleep_ids.intersection(row['obs']['zones']['removed']))
                summary['guidance_budget'] = row['guidance'].public_budget()
                summary['selected_cards'] = [c['definition_id'] for c in row['entry']['cards']]
                summary['duplicate_stats'] = duplicate_stats(row['entry']['cards'],
                    row['draft'].encoder.entry['cards'], catalog, config)
                summary['deck_size'] = counted_size(row['entry']['cards'],row['spec'])
                summary['physical_deck_size'] = len(row['entry']['cards'])
                summary['support_card_count'] = sum(c['definition_id'] in row['spec']['support_card_ids'] for c in row['entry']['cards'])
                summary['support_card_limit'] = row['spec']['support_card_limit']
                summary['exclude_prima_stella'] = row['spec']['exclude_prima_stella']
                summary['exempt_card_count'] = exempt_count(row['entry']['cards'],row['spec'])
                summary['draft_finish_reason'] = row['draft'].finish_reason
                summary.update(score=score, decisions=row['steps'], entry_sha256=hash_entry(row['entry']),
                               environment_seed=row['seed'], action_rng_seed=row['seed']+40_000_000,
                               exploration_schedule_snapshot=exploration,
                               exploration_mode=row['exploration_mode'],
                               sampling_source='joint' if training else 'validation',
                               policy_version=config.get('_policy_version'),
                               turns_elapsed=row['obs']['state']['turnsElapsed'],
                               final_stamina=row['obs']['state']['stamina'], drinks_used=row['drink_used'])
                if log_path:
                    append(log_path, summary)
                if training and scenario_bank is not None and not summary['keycard_focus']:
                    scenario_bank.add(summary)
                summaries.append({k: v for k, v in summary.items() if k != 'submissions' and (keep_entries or k != 'entry')})
                del active[i]
        if any(r['steps'] >= config['max_episode_decisions'] for r in active.values()):
            raise RuntimeError('decision guard reached, not a game terminal')
        if time.monotonic() - last_log > 30:
            _elapsed = time.monotonic() - rollout_started
            _target = target_decisions if training else count
            _done = meaningful if training else len(summaries)
            _rate = _done / _elapsed if _elapsed > 0 and _done else 0.
            _stage = 'collect' if training else 'evaluate'
            _batch = str(config.get('_policy_version', '')).split(':')[1:2]
            print('[PROGRESS] batch=%s stage=%-9s %s %s/%s (%s%%) | %s/min | elapsed %sm | eta %sm | %d live' % (
                _batch[0] if _batch else '?', _stage,
                'decisions' if training else 'episodes', _done, _target,
                round(100. * _done / _target, 1) if _target else '?',
                round(_rate * 60, 1), round(_elapsed / 60, 1),
                round((_target - _done) / _rate / 60, 1) if _rate and _target and _done < _target else 0,
                len(active)), flush=True)
            print(json.dumps({'event': 'rollout', 'completed': len(summaries), 'active': len(active),
                              'meaningful_decisions': meaningful, 'start_seed': start_seed,
                              'target': _target, 'target_kind': 'decisions' if training else 'episodes',
                              'percent': round(100. * _done / _target, 1) if _target else None,
                              'per_minute': round(_rate * 60, 1),
                              'elapsed_minutes': round(_elapsed / 60, 1),
                              'eta_minutes': round((_target - _done) / _rate / 60, 1) if _rate and _target and _done < _target else None,
                              'profiles':dict(Counter(r['profile'] for r in summaries))}), flush=True)
            stage_progress.update(_done, len(active))
            last_log = time.monotonic()
    stage_progress.end()
    if flow: flow.assert_drained()
    print(json.dumps({'event': 'rollout_ready', 'schema': RUNNER_SCHEMA,
        'episodes': len(summaries), 'meaningful_decisions': meaningful, 'next_seed': next_seed,
        'elapsed_minutes': round((time.monotonic() - rollout_started) / 60, 1),
        'capacity_counts': dict(Counter(str(r['drink_capacity']) for r in summaries)),
        'memory_mode_counts': dict(Counter(r['memory_mode'] for r in summaries)),
        'support_card_counts': dict(Counter(str(r['support_card_count']) for r in summaries)),
        'condition_counts': dict(Counter(r['condition_cell'] for r in summaries))}), flush=True)
    return records, summaries, meaningful, next_seed


def _score_summary(rows):
    values = sorted(r['score'] for r in rows)
    normalized = [r['normalized_score'] for r in rows]
    return {'count': len(rows), 'mean': statistics.mean(values),
        'normalized_mean': statistics.mean(normalized),
        'normalized_mean_se': statistics.stdev(normalized) / math.sqrt(len(rows)) if len(rows) > 1 else None,
        'minimum': min(values), 'maximum': max(values),
        'mean_se': statistics.stdev(values) / math.sqrt(len(rows)) if len(rows) > 1 else None,
        'bottom_quarter_mean': statistics.mean(values[:max(1, len(values) // 4)])}


def describe(episodes):
    if not episodes:
        raise ValueError('Cannot summarize an empty rollout')
    scores = sorted(r['score'] for r in episodes)
    result = _score_summary(episodes)
    def groups(key):
        return {name: _score_summary([r for r in episodes if key(r) == name])
                for name in sorted({key(r) for r in episodes})}
    scenarios = groups(lambda r: r['profile'] + '__' + r['scenario']['id'])
    for name, group in scenarios.items():
        rows = [r for r in episodes if r['profile'] + '__' + r['scenario']['id'] == name]
        group.update(mean_removed_sleep=statistics.mean(r['removed_sleep_count'] for r in rows),
            coverage_games=sum(r['scenario']['coverage'] for r in rows),
            memories_selected=dict(Counter(k for r in rows for k in r['selected_memories'])))
    conditions = groups(lambda r: r['condition_cell'])
    for name, group in conditions.items():
        row = next(r for r in episodes if r['condition_cell'] == name)
        group.update(memory_mode=row['memory_mode'], memory_capacity=row['memory_capacity'],
            drink_capacity=row['drink_capacity'])
    result.update(schema=RUNNER_SCHEMA, profiles=groups(lambda r: r['profile']), scenarios=scenarios,
        benchmark_cells=groups(lambda r: r['benchmark_cell']),
        memory_modes=groups(lambda r: r['memory_mode']), condition_cells=conditions,
        courses=groups(lambda r: r['course_id']),
        capacities=groups(lambda r: str(r['drink_capacity'])),
        scenario_macro_mean=statistics.mean(r['mean'] for r in scenarios.values()),
        std=statistics.stdev(scores) if len(scores) > 1 else 0,
        p10_empirical=scores[int((len(scores) - 1) * 0.1)],
        under_100k_fraction=sum(s < 100000 for s in scores) / len(scores),
        unique_drink_multisets=len({tuple(sorted(r['drinks'])) for r in episodes}),
        all_same_four_fraction=sum(len(r['drinks']) == 4 and len(set(r['drinks'])) == 1 for r in episodes) / len(episodes),
        drinks_selected=dict(Counter(str(d) for r in episodes for d in r['drinks'])),
        mean_drink_count=statistics.mean(len(r['drinks']) for r in episodes),
        episodes=sorted(episodes, key=lambda r: r['seed']))
    return result


def scenario_gain(candidate, baseline):
    a, b = candidate['episodes'], baseline['episodes']
    if [(x['seed'], x['benchmark_cell'], x['score_scale']) for x in a] != [
            (x['seed'], x['benchmark_cell'], x['score_scale']) for x in b]:
        raise ValueError('Scenario comparison seed or exogenous condition mismatch')
    gains = [x['score'] - y['score'] for x, y in zip(a, b)]
    normalized = [x['normalized_score'] - y['normalized_score'] for x, y in zip(a, b)]
    return {'mean': statistics.mean(gains),
        'normalized_mean': statistics.mean(normalized),
        'mean_se': statistics.stdev(gains) / math.sqrt(len(gains)) if len(gains) > 1 else 0,
        'normalized_mean_se': statistics.stdev(normalized) / math.sqrt(len(normalized)) if len(normalized) > 1 else 0,
        'positive_scenarios': sum(x > 0 for x in gains), 'count': len(gains),
        'comparison': 'Same fixed exogenous seeds, courses, multiplier scales, drink capacities and HIF memory availability; different policy actions can consume RNG differently'}


def validation_index(result, baseline, offset=0.25):
    """Each profile/course/drink-capacity/memory-mode cell has equal weight."""
    if set(result['benchmark_cells']) != set(baseline['benchmark_cells']):
        raise ValueError('Missing or changed validation benchmark cell')
    if [(r['seed'],r['benchmark_cell'],r['score_scale']) for r in result['episodes']] != [
            (r['seed'],r['benchmark_cell'],r['score_scale']) for r in baseline['episodes']]:
        raise ValueError('Validation seed or exogenous condition mismatch')
    return math.exp(statistics.mean(math.log(
        (v['normalized_mean'] + offset) / (baseline['benchmark_cells'][k]['normalized_mean'] + offset))
        for k, v in result['benchmark_cells'].items()))


def train(root, setup, config, initial, output, *, resume=False, continuation=None):
    from .search_supervision import validate_training_config
    validate_training_config(config)
    from .relational_runtime import configure
    from .relational_training import parameter_groups, migrate_optimizer
    semantic_path = configure(config, setup)
    relational = semantic_path is not None
    if not config.get('search',{}).get('enabled'):
        raise ValueError('The joint-search trainer requires its explicit search configuration')
    if resume and continuation is not None:raise ValueError('Choose one continuation mechanism')
    resume=resume or continuation is not None
    if config['gamma'] != 1:
        raise ValueError('Generalist score objective uses undiscounted complete episodes')
    from . import distributed as _distributed
    resolve_device(config['device'])
    window=RuntimeWindow(output,config)
    if not window.allows(0):
        raise ValueError('Configured training window has ended; set a new intended deadline before launching')
    torch.set_num_threads(config.get('parallelism', {}).get('torch_threads', config.get('torch_threads', 2)))
    random.seed(config['seed']); seed_device(config['seed'], config['device'])
    device = config['device']
    arena = setup.parent / 'runtime/arena'
    api = arena_module(arena)
    from gakumas_arena.engine.search import search_content_version
    search_version = search_content_version()
    read = lambda name: json.loads((setup/name).read_text(encoding='utf-8'))
    profiles, catalog, provenance = read('profiles.json'), read('catalog.json'), read('provenance.json')
    arena_hash = provenance['arena_version']['effective_sha256']
    if api.content_version()['effective_sha256'] != arena_hash:
        raise RuntimeError('Frozen Arena differs from prepared inputs')
    source_hash = source_version()
    setup_hashes = {n:digest(setup/n) for n in ('profiles.json','catalog.json','provenance.json','config.json')}
    if semantic_path is not None:
        # setup hashes use relative filenames to remain portable across hosts.
        try:
            semantic_name = semantic_path.relative_to(Path(setup).resolve()).as_posix()
        except ValueError as exc:
            raise ValueError('Semantic artifact must be inside setup for portable checkpoint verification') from exc
        setup_hashes[semantic_name] = digest(semantic_path)
    # '_setup' travels in the broadcast config so a worker rank can rebuild the
    # catalog, profiles and Arena pool for its shard without a second channel.
    run_config = {**config, '_profiles':profiles, '_setup':str(setup)}
    resumed=None;recovery=None
    if resume:
        if continuation is not None:
            from .continuation import prepare,restore_random,commit_recovery
            model,resumed,recovery=prepare(continuation,output,setup,config,arena_hash,device)
        else:
            from .recovery import prepare,restore_random,commit_recovery
            model,resumed,recovery=prepare(output,setup,config,arena_hash,device)
        reference=resumed['transfer']
    elif initial is not None:
        model, reference = transfer(initial,arena_hash,device,relational=relational)
    else:
        from .model import DraftPolicy
        model = DraftPolicy(quantiles=32,relational=relational).to(device)
        reference = {'initialization': 'random', 'optimizer_reset': True,
                     'restore_continuation': False, 'optimizer_migration_pending': False}
    for parameter in model.parameters():
        parameter.requires_grad_(True)
    if bool(model.config.get('relational')) != relational:
        raise ValueError('Architecture change requires a NEW output and --initial, not --resume/--continue-from')
    if relational and config.get('value_calibration') and not hasattr(model, 'exam_quantile_head') and not resumed:
        model.enable_quantiles(config['value_calibration']['quantiles'])
    rates = {phase:config['learning_rate' if phase=='exam' else phase+'_learning_rate']
             for phase in ('exam','drink','draft','guidance','memory')}
    groups = parameter_groups(model, rates)
    optimizer = torch.optim.Adam(groups,eps=config['adam_eps'], **optimizer_options(model))
    if resumed:load_optimizer_state(optimizer, resumed['optimizer_state'], device)
    elif initial is not None:
        from .migration import migrate_adam
        old = torch.load(initial, map_location='cpu', weights_only=True)
        if relational:
            reference['optimizer_migration'] = migrate_optimizer(old, model, optimizer, device)
        elif old['model_schema'] == 'hif-memory-draft-drink-exam-policy/1':
            reference['optimizer_migration'] = migrate_adam(old, model, optimizer)
        else:
            load_optimizer_state(optimizer, old['optimizer_state'], device)
            reference['optimizer_migration'] = {'same_schema_restored': True}
        reference['optimizer_migration_pending'] = False
        del old
    if not relational and config.get('value_calibration') and not hasattr(model, 'exam_quantile_head') and not resumed:
        model.enable_quantiles(config['value_calibration']['quantiles'], optimizer)
    efficiency=config.get('sample_efficiency',{})
    practice=config.get('practice',{})
    coverage=Coverage(resumed.get('practice_coverage') if resumed else None)
    if practice.get('coverage',False):run_config['_coverage']=coverage
    fork_next_seed=(resumed or {}).get('fork_next_seed',1_600_000_000)
    if efficiency.get('historical_actions_in_ppo',False):
        raise ValueError('Historical-action PPO replay is unsupported; replay public loadouts with the current policy')
    bank=None
    if efficiency.get('scenario_bank',False):
        contract=hashlib.sha256(json.dumps({'arena':arena_hash,'profiles':setup_hashes['profiles.json'],
            'catalog':setup_hashes['catalog.json']},sort_keys=True).encode()).hexdigest()
        bank=SampleBank([p['id'] for p in profiles],contract,
            capacity_per_profile=efficiency.get('bank_capacity_per_profile',64),seed=config['seed']+801,
            state=resumed.get('sample_bank') if resumed else None)
        removed = duplicate_limits.prune_bank(bank, catalog, config)
        print(json.dumps({'event':'duplicate_bank_pruned','removed_by_profile':removed}), flush=True)
    run_config['_card_families'] = duplicate_limits.family_ids(catalog)
    output.mkdir(parents=True,exist_ok=resume)
    resources = RuntimeResources(output, config.get('resource_mode', 'daily'))
    manifest_value={'config':config,'profiles':profiles,'entry':profiles[2]['entry'],
        'search_version': search_version, 'model_schema': model.__module__+':'+type(model).__name__,
        'pool':profiles[2]['spec'], 'provenance':provenance,'arena_path':str(arena),
        'arena_sha256':arena_hash,'setup_sha256':setup_hashes,'rl_source_sha256':source_hash,
        'transfer':reference,'hardware':device_report(device),
        'model_config':model.config,'model_parameters':sum(p.numel() for p in model.parameters()),
        'relational_semantics_sha256':digest(semantic_path) if semantic_path is not None else None,
        'schema':RUNNER_SCHEMA,
        'construction_sources':'Own-plan/free ordinary and support + cards; at most three physical support cards within 18-25 total cards; all registered Prima Stella cards forbidden. Native unique and Switch constraints retained. Guidance uses existing native prices and budget.',
        'objective':'Authoritative terminal score / (profile score scale * exogenous multiplier normalizer), shared by all five trained phases; profile-balanced PPO.',
        'best_selection':'Equal profile/course/drink-capacity/memory-mode cell geometric mean of normalized score ratios to the same initial policy on fixed evaluation seeds, with fixed 0.25 normalized offset; raw aggregate score is diagnostic only.',
        'memory_availability':'Environment-assigned balanced none (zero HIF memory options) / hif (up to four unique options), public before construction and independent of drink capacity. Native idol, card and P-item effects stay active. Disabled memory has no policy decision or PPO record.',
        'drink_supply':'After deck/guidance completion: 70% finite random 6-8 bottles, 20% low supply 2-3, 10% forced coverage bottle plus finite choices; capacity sampled independently 0-4; all are explicit experimental distributions.'}
    if not resume:json_write(output/'manifest.json',manifest_value)
    started = time.monotonic()
    batches,decisions,episode_index,best = 0,0,config['train_seed_base'],1.0
    state = {'schema':RUNNER_SCHEMA,'source_sha256':source_hash,'status':'running','started_at':datetime.now(timezone.utc).isoformat(),
        'run_dir':str(output),'trainer_pid':os.getpid(),'batch_decisions':config['batch_decisions'],
        'max_minutes':config['max_minutes'],'profiles':[p['id'] for p in profiles]}
    if resumed:
        state=copy.deepcopy(recovery['progress'])
        state.update(status='running',run_dir=str(output),source_sha256=source_hash,trainer_pid=os.getpid(),
                     batch_decisions=config['batch_decisions'],max_minutes=config['max_minutes'],
                     resumed_at=datetime.now(timezone.utc).isoformat())
        state['construction_constraint'] = {'max_same_name':duplicate_limits.limit(config),
            'max_same_name_overrides':duplicate_limits.overrides(config),
            'fourth_copy_penalty':practice.get('duplicates',{}).get('coefficient'),
            'scope':'all newly constructed and PPO rehearsal loadouts; historical fixed-play is diagnostic only'}
        for stale in ('stop_reason','evaluation_label','error','test_mean','test_index','test_best','test_initial',
                      'test_gain','completed_at','finished_at','result','final_mean','final_score','ppo_progress'):
            state.pop(stale,None)
        began=datetime.fromisoformat(state['started_at'])
        started-=(datetime.now(timezone.utc)-began).total_seconds()
        batches,decisions,episode_index,best=(resumed['batches'],resumed['decisions'],
            resumed['next_episode_index'],resumed['best_validation_index'])
    restored_rates = learning_rates.current(optimizer)
    state['optimizer_schedule'] = learning_rates.apply(optimizer, config, (time.monotonic()-started)/60,
                                                       completed_batches=batches)
    json_write(output/'optimizer-change.json', {'restored_rates':restored_rates,
        'applied':state['optimizer_schedule'], 'schedule':config.get('learning_rate_schedule'),
        'checkpoint_batch':batches, 'adam_moments_preserved':bool(resumed) or bool(reference.get('optimizer_migration')),
        'source_checkpoint_sha256':(recovery or {}).get('audit',{}).get('source_checkpoint_sha256') or reference.get('sha256')})
    if os.name=='nt' and not ctypes.windll.kernel32.SetThreadExecutionState(0x80000001):
        raise OSError('Cannot keep machine awake during training')

    def publish(event, **details):
        state.update(window.progress_fields())
        state.update(resources.progress_fields())
        state.update(stage=stage_progress.snapshot())
        state.update(event=event,batches=batches,decisions=decisions,
            elapsed_minutes=(time.monotonic()-started)/60,updated_at=datetime.now(timezone.utc).isoformat(),**details)
        json_write(output/'progress.json',state)
        append(output/'events.jsonl',copy.deepcopy(state))
        line=f'[{datetime.now():%H:%M:%S}] b{batches} {event} run {state["elapsed_minutes"]:.0f}m decisions={decisions}'
        line+=' | '+stage_progress.line()
        # Long silent stages carry their own detail; show it instead of burying it in JSON.
        if 'ppo_progress' in details:
            p=details['ppo_progress']
            line+=(f" | PPO epoch {p.get('epoch')}/{p.get('epochs_max')}"
                   f" records {p.get('records_seen')}/{p.get('records_total')}"
                   f" steps {p.get('optimizer_steps')} kl {p.get('kl',0):.4f}")
        if 'search_progress' in details:
            q=details['search_progress']
            # `roots` is only what is in flight right now; attempted/accepted are
            # cumulative for the run and are what says whether search is producing.
            _att,_acc=q.get('attempted',0),q.get('accepted',0)
            line+=f" | MCTS {q.get('roots')} in flight"
            if _att:
                line+=f", {_acc}/{_att} roots accepted ({100.*_acc/_att:.0f}%)"
            else:
                line+=", no root has finished yet"
        for k in ('train_mean','train_normalized_mean','validation_mean','validation_normalized_mean','best_validation_index'):
            if k in details:line+=f' {k}={details[k]:.3f}'
        if 'profile_scores' in details:
            line+=' | '+', '.join(f'{n}={v["mean"]:.0f} (n={v["count"]})' for n,v in details['profile_scores'].items())
        if 'memory_modes' in details:
            line+=' | memories: '+', '.join(f'{n}={v["normalized_mean"]:.3f} (n={v["count"]})' for n,v in details['memory_modes'].items())
        with (output/'progress.log').open('a',encoding='utf8') as f:f.write(line+'\n')
        print(line,flush=True)

    def unchanged():
        if source_version()!=source_hash or api.content_version()['effective_sha256']!=arena_hash:
            raise RuntimeError('Frozen training code/engine changed; last complete checkpoint retained')
        if search_content_version() != search_version:
            raise RuntimeError('Frozen search engine changed during training')
        if any(digest(setup/n)!=h for n,h in setup_hashes.items()):
            raise RuntimeError('Prepared scenario changed during training')

    def checkpoint(name):
        unchanged()
        from .checkpoint import save_committed
        save_committed(output/name,model,optimizer,arena_sha256=arena_hash,training_config=config,
            search_version=search_version, search_seed_counter=search_router.counter if search_router else 0,
            run_progress=copy.deepcopy(state),
            resource_settings=resources.current,
            sample_bank=bank.state_dict() if bank is not None else None,
            practice_coverage=coverage.rows,fork_next_seed=fork_next_seed,
            setup_sha256=setup_hashes,decisions=decisions,batches=batches,next_episode_index=episode_index,
            best_validation_index=best,transfer=reference,elapsed_minutes=(time.monotonic()-started)/60)

    pool = None
    search_router = None
    def apply_resources():
        nonlocal pool, search_router
        try:
            request = resources.requested()
        except (OSError, ValueError, TypeError) as exc:
            # A malformed UI/control file must not terminate a healthy trainer.
            if resources.current is None:
                raise
            if resources.last_rejection != str(exc):
                resources.last_rejection = str(exc)
                publish('resource_request_rejected', resource_request_error=str(exc))
            return
        # README: workers/search-workers are the whole job's parallelism, "not multiplied by
        # the learner count". Every rank therefore takes an equal share of the configured
        # totals, and run_config['workers'] must match this rank's pool because rollout()
        # indexes worker slots with range(config['workers']).
        _world = _distributed.ACTIVE.size if _distributed.ACTIVE is not None else 1
        pool, changed = resources.apply(request, run_config, batches, pool,
            lambda count: Workers(max(1, count // _world), arena, arena_hash))
        run_config['workers'] = max(1, resources.current['workers'] // _world)
        if changed:
            from .search_router import SearchRouter
            counter = (search_router.counter if search_router is not None else
                       (resumed or {}).get('search_seed_counter', 0))
            if search_router is not None:
                search_router.close()
            _roots = max(1, resources.current['parallel_roots'] // _world)
            search_cfg = {**config['search'], 'parallel_roots': _roots,
                          # inference_batch above parallel_roots is unreachable: each search
                          # process blocks on its own reply, so only that many are in flight.
                          'inference_batch': min(resources.current['inference_batch'], _roots)}
            search_cfg['objective_k'] = 4 if config.get('practice',{}).get('forks',{}).get('objective')=='best_of_k' else 1
            search_router = SearchRouter(model, device, search_cfg, seed_counter=counter,
                log_path=output/'search-roots.jsonl',
                progress=lambda **details: publish('search_progress', search_progress=details))
            run_config['_search_router'] = search_router
            resources.last_rejection = None
            state.pop('resource_request_error', None)
            publish('resource_mode_applied')

    def evaluate(label, policy=None, seed=None, count=None):
        publish('evaluating',evaluation_label=label)
        best4_enabled=practice.get('forks',{}).get('objective')=='best_of_k'
        eval_config={**run_config,'_policy_version':f'{source_hash}:{batches}:evaluation:{label}'}
        # Greedy evaluation is deterministic per (seed, index) and describe() aggregates
        # order-independently, so the episode set is sharded across the learner ranks and
        # gathered. With one rank this is the identical local call.
        from . import distributed as _distributed
        eval_seed=config['eval_seed_base'] if seed is None else seed
        eval_count=count or config['eval_episodes']
        if _distributed.ACTIVE is not None:
            episodes=_distributed.ACTIVE.evaluate_rollout(pool,policy if policy is not None else model,
                setup,catalog,eval_config,eval_seed,eval_count,
                log_path=output/f'{label}-episodes.jsonl',keep_entries=best4_enabled)
        else:
            _,episodes,_,_=rollout(pool,policy if policy is not None else model,None,catalog,eval_config,
                device,eval_seed,count=eval_count,greedy=True,
                log_path=output/f'{label}-episodes.jsonl',keep_entries=best4_enabled)
        result=describe(episodes)
        if best4_enabled:
            from .best_of import construction_evaluation
            result['best_of_4']=construction_evaluation(pool,policy if policy is not None else model,
                episodes,eval_config,device,choose,output,label)
        result['construction_max_same_name'] = duplicate_limits.limit(config)
        result['construction_max_same_name_overrides'] = duplicate_limits.overrides(config)
        json_write(output/f'{label}.json',result)
        return result

    def best4_check(result,label):
        if 'best_of_4' not in result:return
        from .best_of import comparison
        current=result['best_of_4'];reference=output/'best4-reference.json'
        if not reference.exists():json_write(reference,current)
        metric=comparison(current,json.loads(reference.read_text(encoding='utf8')))
        improved=not (output/'best4.pt').exists() or metric>state.get('best4_index',-math.inf)
        if improved:
            state['best4_index']=metric
            checkpoint('best4.pt')
        append(output/'best4-validation-history.jsonl',{'batch':batches,'decisions':decisions,
            'label':label,'index':metric,'best_index':state['best4_index'],
            'profiles':current['profiles'],'games':current['games'],
            'new_constructions':current['new_constructions'],'primary_checkpoint':'best4.pt'})
        publish('best4_validation',best4_validation_index=metric,best4_profiles=current['profiles'],
                primary_checkpoint='best4.pt')

    def index(result, baseline):
        return validation_index(result, baseline)

    def play_check(label):
        run_config['_policy_version']=f'{source_hash}:{batches}'
        publish('evaluating',evaluation_label=label)
        result=evaluate_play(pool,model,run_config,device,play_suite,choose,output,label,describe)
        baseline_path=output/'play-baseline.json'
        if not baseline_path.exists():json_write(baseline_path,result)
        base=json.loads(baseline_path.read_text(encoding='utf-8'))
        from .play_evaluation import paired_comparison
        paired=paired_comparison(result,base)
        result['paired_vs_baseline']=paired
        json_write(output/f'{label}.json',result)
        metric=index(result,base)
        append(output/'play-validation-history.jsonl',{'batch':batches,'decisions':decisions,
            'mean':result['mean'],'normalized_mean':result['normalized_mean'],'validation_index':metric,
            'profiles':result['profiles'],'benchmark_cells':result['benchmark_cells'],
            'paired_vs_baseline':paired,'replicas':play_suite['replicas'],
            'loadout_count':play_suite['loadout_count'],'reference_reset':play_suite.get('reference_reset')})
        publish('play_validation',play_validation_index=metric,play_validation_mean=result['mean'],
                play_profiles=result['profiles'])

    try:
        if resumed:
            commit_recovery(output,resumed,recovery)
        apply_resources()
        publish('resuming' if resumed else 'starting')
        if resumed and continuation is not None and not recovery.get('reset_joint_reference'):
            # Seal this audited revision before any long diagnostic or rollout.
            restore_random(resumed)
            checkpoint('latest.pt')
        if resumed and recovery.get('reset_joint_reference'):
            # No optimization takes place between the boundary checkpoint and
            # this new 180-episode reference. Old unrestricted scores stay archived.
            restore_random(resumed)
            for key in ('validation_index','best_validation_index','validation_profiles','gain_vs_start'):
                state.pop(key,None)
            baseline=evaluate('validation-initial')
            best=1.0
            profile_bests={k:v['normalized_mean'] for k,v in baseline['profiles'].items()}
            scenario_bests={k:v['normalized_mean'] for k,v in baseline['scenarios'].items()}
            for name in ('best.pt',*(f'best-{k}.pt' for k in (*profile_bests,*scenario_bests))):checkpoint(name)
            checkpoint('latest.pt')
            append(output/'validation-history.jsonl',{'batch':batches,'decisions':decisions,
                'schema':RUNNER_SCHEMA,'mean':baseline['mean'],'normalized_mean':baseline['normalized_mean'],
                'benchmark_cells':baseline['benchmark_cells'],'capacities':baseline['capacities'],
                'memory_modes':baseline['memory_modes'],'condition_cells':baseline['condition_cells'],
                'courses':baseline['courses'],'validation_index':1.0,'best_index':1.0,
                'gain_vs_start':scenario_gain(baseline,baseline),
                'profiles':baseline['profiles'],'scenarios':baseline['scenarios'],
                'construction_max_same_name':duplicate_limits.limit(config),'reference_reset':True,
                'construction_max_same_name_overrides':duplicate_limits.overrides(config)})
            json_write(output/'construction-benchmark.json',{'max_same_name':duplicate_limits.limit(config),
                'max_same_name_overrides':duplicate_limits.overrides(config),
                'start_batch':batches,'baseline_index':1.0,'reference':'resumed policy before any update under copy cap',
                'fixed_play_unchanged':True,'original_initial_weights_retained_for_final_test':True})
            publish('construction_baseline',validation_index=best,best_validation_index=best,
                validation_mean=baseline['mean'],validation_profiles=baseline['profiles'],
                profile_scores=baseline['profiles'],gain_vs_start=scenario_gain(baseline,baseline))
            last_eval=time.monotonic()-started
        elif resumed:
            baseline=recovery['baseline']
            if baseline is None:
                restore_random(resumed)
                baseline=evaluate('validation-initial')
                checkpoint('best.pt')
            if baseline.get('schema') != RUNNER_SCHEMA:
                raise ValueError('Recovery baseline is not a generalist normalized benchmark')
            profile_bests={k:v['normalized_mean'] for k,v in baseline['profiles'].items()}
            scenario_bests={k:v['normalized_mean'] for k,v in baseline['scenarios'].items()}
            for historical in recovery['history']:
                for name,bests in (('profiles',profile_bests),('scenarios',scenario_bests)):
                    for key,value in historical[name].items():
                        bests[key]=max(bests[key],value['normalized_mean'])
            restore_random(resumed)
            if recovery['history']:
                label=("validation-initial.json" if recovery['history'][-1].get('reference_reset') else
                       f"validation-{recovery['history'][-1]['batch']:04d}.json")
                last_eval=(output/label).stat().st_mtime-began.timestamp()
            else:last_eval=0
        else:
            checkpoint('initial.pt');checkpoint('latest.pt')
            baseline=evaluate('validation-initial')
            checkpoint('best.pt')
            profile_bests={k:v['normalized_mean'] for k,v in baseline['profiles'].items()}
            scenario_bests={k:v['normalized_mean'] for k,v in baseline['scenarios'].items()}
            for name in (*profile_bests,*scenario_bests):checkpoint(f'best-{name}.pt')
            publish('baseline',baseline_mean=baseline['mean'],profile_scores=baseline['profiles'],
                baseline_profiles=baseline['profiles'],scenarios=baseline['scenarios'],best_validation_index=best,
                memory_modes=baseline['memory_modes'],condition_cells=baseline['condition_cells'])
            last_eval=0
            checkpoint('latest.pt')
        if resumed and continuation is not None and config.get('learning_rate_schedule'):
            checkpoint('optimizer-batch-start.pt')
            publish('optimizer_batch_upgrade', optimizer_batch_change={
                'previous':resumed['training_config'].get('effective_minibatch',64),
                'current':config.get('effective_minibatch',64),
                'microbatch':run_config['minibatch'],
                'checkpoint_batch':batches,
                'learning_rate_origin_preserved':True,
                'exploration_schedule':config.get('exploration_schedule')}, active_exploration=schedule(config,decisions,
                elapsed_minutes=(time.monotonic()-started)/60))
        play_suite=None
        if practice.get('play_evaluation',{}).get('enabled',False):
            play_suite=prepare_suite(output,run_config)
            if not (output/'play-baseline.json').exists():play_check('play-validation-initial')
        run_config['_completed_batches'] = batches
        run_config['_policy_version'] = f'{source_hash}:{batches}'
        keycard_check(pool,model,run_config,catalog,device,output,batches,rollout,choose,checkpoint,publish)
        if practice.get('forks',{}).get('objective')=='best_of_k' and not (output/'best4-reference.json').exists():
            best4_check(evaluate('validation-best4-boundary'),'validation-best4-boundary')
            if resumed:restore_random(resumed)
            checkpoint('latest.pt')
        if config.get('critic_completion') and continuation is not None:
            if not hasattr(model, 'exam_quantile_head'):
                raise ValueError('KL/value continuation requires existing calibrated quantiles')
            checkpoint('kl-value-boundary.pt')
            checkpoint('latest.pt')
            publish('kl_value_boundary', target_kl=config['target_kl'], block_stop_kl=2*config['target_kl'],
                    critic_completion_enabled=True)
        if config.get('value_calibration') and not hasattr(model,'exam_quantile_head'):
            from .value_calibration import calibrate
            if resumed is None:
                raise ValueError('Critic calibration requires an audited continuation')
            # First seal the unchanged boundary; the supervisor can verify and
            # publish it before the explicitly requested critic-only warm-up.
            publish('critic_preparing',critic_calibration={'status':'starting','actor_frozen':True})
            checkpoint('value-boundary.pt')
            model.enable_quantiles(config['value_calibration']['quantiles'],optimizer)
            calibration_config={**run_config,'_calibration_source_info':resumed}
            report=calibrate(pool,model,optimizer,calibration_config,device,
                             continuation or output,output,choose,publish)
            publish('critic_calibrated',critic_calibration={k:report[k] for k in
                ('status','selected_epoch','actor_unchanged','non_exam_value_parameters_unchanged','wall_seconds')})
            checkpoint('critic-calibrated.pt')
            checkpoint('latest.pt')
        while decisions<config['target_decisions']:
            if config.get('max_batches') is not None and batches >= config['max_batches']:
                publish('batch_limit_reached')
                break
            # A completed batch is the only live update point for the user time control.
            # Refresh precedes expiry checks so an extension can replace the old deadline.
            if window.refresh():
                publish('training_window_updated')
            if not window.allows((time.monotonic()-started)/60):
                publish('training_window_ended',stop_reason='Effective training time window ended')
                break
            if (output/'stop-after-batch.json').exists():
                publish('stop_requested',stop_reason='Finish at completed checkpoint boundary, then run final evaluation')
                break
            apply_resources()
            before=time.monotonic()
            run_config['_policy_version']=f'{source_hash}:{batches}'
            run_config['_completed_batches'] = batches
            if bank is not None:bank.configure(practice.get('bank',{}),run_config['_policy_version'],batches)
            exploration=schedule(config,decisions,elapsed_minutes=(before-started)/60)
            stage_progress.begin_batch(batches)
            publish('collecting',active_exploration=exploration)
            search_before = search_router.diagnostics()
            # Sharded across the learner ranks: each walks its own interleaved seed stream
            # and an equal share of the soft decision budget. The bank is fed afterwards
            # from the gathered episodes so one deduplicating bank stays authoritative.
            _bank_rows=[]
            if _distributed.ACTIVE is not None and _distributed.ACTIVE.size>1:
                records,episodes,added,episode_index,_bank_rows=_distributed.ACTIVE.collect_rollout(
                    pool,model,setup,catalog,run_config,episode_index,config['batch_decisions'],
                    exploration,log_path=output/'train-episodes.jsonl',
                    keep_entries=practice.get('forks',{}).get('enabled',False),
                    search_log=output/'search-roots.jsonl',
                    search_seed_base=search_router.counter if search_router is not None else 0)
                if bank is not None:
                    for _row in _bank_rows:
                        if not _row.get('keycard_focus'):bank.add(_row)
            else:
                records,episodes,added,episode_index=rollout(pool,model,None,catalog,run_config,device,
                    episode_index,target_decisions=config['batch_decisions'],
                    log_path=output/'train-episodes.jsonl',exploration=exploration,scenario_bank=bank,
                    keep_entries=practice.get('forks',{}).get('enabled',False))
            joint_episode_count=len(episodes)
            tasks,fork_next_seed=make_fork_tasks(episodes,run_config,fork_next_seed)
            fork_stats=[]
            if tasks:
                # Measured at 3246 tasks / 4 per minute on rank0 alone; sharded across the
                # learners instead. apply_fork_returns groups by prefix and compares
                # multisets, so gather order is irrelevant, and it already raises on a
                # missing or duplicate continuation.
                _objective=practice.get('forks',{}).get('objective','mean')
                if _distributed.ACTIVE is not None and _distributed.ACTIVE.size>1:
                    # Each rank replays the forks of its own joint episodes and credits the
                    # group locally (apply_fork_returns extends `records` in place there);
                    # only the fork summaries and per-group diagnostics come back gathered.
                    fork_records,fork_episodes,fork_decisions,fork_stats=_distributed.ACTIVE.fork_rollout(
                        pool,model,setup,run_config,tasks,exploration,
                        records=records,summaries=episodes,objective=_objective,
                        log_path=output/'train-episodes.jsonl',source='fork_exam',
                        search_seed_base=search_router.counter if search_router is not None else 0)
                else:
                    fork_records,fork_episodes,fork_decisions=rollout_bank(pool,model,None,run_config,device,
                        len(tasks),exploration,choose,log_path=output/'train-episodes.jsonl',tasks=tasks,source='fork_exam')
                    fork_stats=apply_fork_returns(records,episodes,fork_records,fork_episodes,expected_tasks=tasks,
                        objective=_objective)
                if bank is not None:
                    for result in fork_episodes:bank.feedback(result['bank_key'],result['normalized_score'])
                for item in fork_stats:append(output/'fork-returns.jsonl',{'batch':batches+1,**item})
                episodes.extend(fork_episodes);added+=fork_decisions
            if bank is not None:
                ratio=efficiency.get('bank_extra_episodes_per_joint',0.25)
                if not 0<=ratio<=1:raise ValueError('bank extra episode ratio must be in [0,1]')
                extra_count=min(efficiency.get('bank_max_episodes_per_batch',10),math.floor(joint_episode_count*ratio))
                extra_tasks=None
                if practice.get('forks',{}).get('objective')=='best_of_k':
                    from .best_of import repeat_bank_tasks,apply_bank_returns
                    extra_tasks,fork_next_seed=repeat_bank_tasks(
                        keycard_focus.filter_bank_tasks(bank.sample(extra_count),run_config),fork_next_seed)
                if extra_tasks is not None and _distributed.ACTIVE is not None and _distributed.ACTIVE.size>1:
                    # Replica groups are whole on one rank and credited there; the replays
                    # run with bank=None everywhere, so the bank is fed here from summaries.
                    extra_records,extra_episodes,extra_decisions,bank_groups=_distributed.ACTIVE.bank_replay(
                        pool,model,setup,run_config,extra_tasks,exploration,log_path=output/'train-episodes.jsonl')
                    for row in extra_episodes:bank.feedback(row['bank_key'],row['normalized_score'])
                else:
                    extra_records,extra_episodes,extra_decisions=rollout_bank(pool,model,bank,run_config,device,
                        extra_count,exploration,choose,log_path=output/'train-episodes.jsonl',tasks=extra_tasks)
                    bank_groups=apply_bank_returns(extra_records,extra_episodes,extra_tasks) if extra_tasks is not None else []
                for item in bank_groups:append(output/'bank-group-returns.jsonl',{'batch':batches+1,**item})
                records.extend(extra_records);episodes.extend(extra_episodes);added+=extra_decisions
            duplicate_reward = apply_draft_penalty(records, episodes)
            collection=time.monotonic()-before
            gradient_cfg=practice.get('gradient_diagnostics',{})
            if gradient_cfg.get('enabled') and (batches+1)%gradient_cfg.get('every_batches',20)==0:
                publish('gradient_probe')
                probe=inspect_gradients(model,[r for r in records if r['loss_kind']=='ppo'],run_config,device)
                append(output/'gradient-diagnostics.jsonl',{'batch':batches+1,**probe})
            unchanged(); before=time.monotonic()
            state['optimizer_schedule'] = learning_rates.apply(optimizer,config,(before-started)/60,
                                                               completed_batches=batches)
            _epoch_cap=run_config.get('sample_efficiency',{}).get('ppo_epochs_max',run_config['epochs'])
            _ranks=_distributed.ACTIVE.size if _distributed.ACTIVE is not None else 1
            stage_progress.begin('ppo_update',len(records)*max(1,_epoch_cap),'records',shards=_ranks)
            # The first ppo_progress callback only fires after the first optimizer block,
            # which sits behind the records broadcast to the worker ranks. Say so now,
            # or the log and dashboard sit on the last bank line for the whole wait.
            publish('ppo_update_begin', ppo_records=len(records), ppo_epoch_cap=_epoch_cap)
            def _ppo_progress(**details):
                stage_progress.update((details.get('epoch',1)-1)*len(records)+details.get('records_seen',0))
                publish('ppo_progress', ppo_progress=details)
            losses=update(model,optimizer,records,run_config,device,
                progress=_ppo_progress)
            losses['learning_rates'] = learning_rates.current(optimizer)
            losses['optimizer_schedule'] = state['optimizer_schedule']
            stage_progress.end()
            update_seconds=time.monotonic()-before
            decisions+=added;batches+=1
            summary=describe(episodes)
            # update() reduced these over every rank's records; finalise the means here.
            _rs=losses.get('record_stats') or {}
            _fields=('behavior_entropy_fraction','base_entropy_fraction','behavior_max_probability','base_max_probability')
            stats={}
            for name in ('exam','drink','draft','guidance','memory'):
                _e=(_rs.get('exploration') or {}).get(name) or {}
                _c=_e.get('count',0)
                stats[name]={k:(_e.get(k,0.)/_c if _c else 0) for k in _fields}
            _pd={}
            for _key,_g in (_rs.get('practice') or {}).items():
                _pd[_key.replace('/','|')]={'decisions':int(_g.get('decisions',0)),'meaningful':int(_g.get('meaningful',0)),
                    'value_mae':_g.get('value_mae',0.)/max(1,_g.get('decisions',0)),
                    'behavior_max_probability':(_g.get('bmp_sum',0.)/_g['bmp_count']) if _g.get('bmp_count') else None}
            _phase_decisions={k:int(v) for k,v in (_rs.get('phase_decisions') or {}).items()}
            construction={'drink_capacity_counts':dict(Counter(str(r['drink_capacity']) for r in episodes)),
                'build_best_of_k':summarize_groups(fork_stats),
                'construction_objective':practice.get('forks',{}).get('objective','mean'),
                'construction_replicas':practice.get('forks',{}).get('replicas',2),
                'search_diagnostics': search_router.diagnostics(),
                'search_batch': search_router.delta(search_before),
                'keycard_practice':keycard_focus.summarize(episodes),
                'sampling_source_counts':dict(Counter(r['sampling_source'] for r in episodes)),
                'joint_episode_count':joint_episode_count,'bank_episode_count':sum(r['sampling_source']=='bank_exam' for r in episodes),
                'fork_episode_count':sum(r['sampling_source']=='fork_exam' for r in episodes),
                'fork_prefix_count':len(fork_stats),'practice_modes':dict(Counter(r.get('exploration_mode','normal') for r in episodes[:joint_episode_count])),
                'fork_coverage':fork_coverage(episodes[:joint_episode_count],fork_stats),
                'practice_diagnostics':_pd,
                'coverage_summary':coverage.summary(),
                'duplicate_regularization':duplicate_reward,
                'joint_deck_size_counts':dict(Counter(str(r['deck_size']) for r in episodes[:joint_episode_count])),
                'sample_bank':bank.describe() if bank is not None else None,
                'memory_mode_counts':dict(Counter(r['memory_mode'] for r in episodes)),
                'condition_counts':dict(Counter(r['condition_cell'] for r in episodes)),
                'memory_modes':summary['memory_modes'], 'condition_cells':summary['condition_cells'],
                'course_counts':dict(Counter(r['course_id'] for r in episodes)),
                'supply_mode_counts':dict(Counter(r['drink_supply']['supply_mode'] for r in episodes)),
                'train_normalized_mean':summary['normalized_mean'],
                'unique_decks':len({(r['profile'],tuple(sorted(r['selected_cards']))) for r in episodes}),
                'unique_turn_orders':len({tuple(r['resolved_turn_types']) for r in episodes}),
                'deck_size_counts':dict(Counter(str(r['deck_size']) for r in episodes)),
                'support_card_counts':dict(Counter(str(r['support_card_count']) for r in episodes)),
                'mean_p_spent':statistics.mean(r['guidance_budget']['p_spent'] for r in episodes),
                'mean_guided_cards':statistics.mean(r['guidance_budget']['guided_cards'] for r in episodes),
                'memory_selected_counts':dict(Counter(m for r in episodes for m in r['selected_memories']))}
            append(output/'metrics.jsonl',{'schema':RUNNER_SCHEMA,'source_sha256':source_hash,'batch':batches,'decisions':decisions,'train_mean':summary['mean'],
                'batch_decisions_target':config['batch_decisions'],'batch_decisions_actual':added,'episodes':len(episodes),
                'collection_seconds':collection,'update_seconds':update_seconds,'profiles':summary['profiles'],
                'resource_settings': resources.current,
                'scenarios':summary['scenarios'],'benchmark_cells':summary['benchmark_cells'],
                'capacities':summary['capacities'],'courses':summary['courses'],'exploration_settings':exploration,'exploration_stats':stats,
                'phase_decisions':_phase_decisions,**construction,**losses})
            checkpoint('latest.pt')
            if practice.get('coverage',False):json_write(output/'coverage.json',coverage.rows)
            publish('update',train_mean=summary['mean'],profile_scores=summary['profiles'],scenarios=summary['scenarios'],
                losses=losses,**construction)
            del records
            run_config['_policy_version'] = f'{source_hash}:{batches}'
            keycard_check(pool,model,run_config,catalog,device,output,batches,rollout,choose,checkpoint,publish)
            if time.monotonic()-started-last_eval >= 60*config.get('evaluation_interval_minutes', 60):
                evaluation=evaluate(f'validation-{batches:04d}')
                best4_check(evaluation,f'validation-{batches:04d}')
                metric=index(evaluation,baseline)
                for groups,bests in ((evaluation['profiles'],profile_bests),(evaluation['scenarios'],scenario_bests)):
                    for name,v in groups.items():
                        if v['normalized_mean']>bests[name]:bests[name]=v['normalized_mean'];checkpoint(f'best-{name}.pt')
                if metric>best:best=metric;checkpoint('best.pt')
                checkpoint('latest.pt');checkpoint(f'snapshot-{batches:04d}.pt')
                gain=scenario_gain(evaluation,baseline)
                append(output/'validation-history.jsonl',{'batch':batches,'decisions':decisions,'mean':evaluation['mean'],
                    'schema':RUNNER_SCHEMA,'normalized_mean':evaluation['normalized_mean'],
                    'construction_max_same_name':duplicate_limits.limit(config),
                    'construction_max_same_name_overrides':duplicate_limits.overrides(config),
                    'benchmark_cells':evaluation['benchmark_cells'],'capacities':evaluation['capacities'],
                    'memory_modes':evaluation['memory_modes'],'condition_cells':evaluation['condition_cells'],
                    'courses':evaluation['courses'],'validation_index':metric,'best_index':best,'gain_vs_start':gain,
                    'profiles':evaluation['profiles'],'scenarios':evaluation['scenarios']})
                publish('validation',validation_mean=evaluation['mean'],profile_scores=evaluation['profiles'],
                    validation_profiles=evaluation['profiles'],scenarios=evaluation['scenarios'],
                    validation_index=metric,best_validation_index=best,gain_vs_start=gain,
                    validation_normalized_mean=evaluation['normalized_mean'],
                    memory_modes=evaluation['memory_modes'],condition_cells=evaluation['condition_cells'],
                    capacities=evaluation['capacities'],courses=evaluation['courses'])
                last_eval=time.monotonic()-started
                if play_suite is not None:play_check(f'play-validation-{batches:04d}')
        latest=evaluate('validation-final')
        best4_check(latest,'validation-final')
        metric=index(latest,baseline)
        if metric>best:best=metric;checkpoint('best.pt')
        for groups,bests in ((latest['profiles'],profile_bests),(latest['scenarios'],scenario_bests)):
            for name,v in groups.items():
                if v['normalized_mean']>bests[name]:bests[name]=v['normalized_mean'];checkpoint(f'best-{name}.pt')
        checkpoint('latest.pt')
        if play_suite is not None:play_check('play-validation-final')
        del optimizer,model;empty_accelerator_cache()
        primary='best4.pt' if practice.get('forks',{}).get('objective')=='best_of_k' else 'best.pt'
        best_model,info=load(output/primary,device)
        final=evaluate('test-best',best_model,config['final_seed_base'],config['final_episodes'])
        del best_model;empty_accelerator_cache()
        initial_model,_=load(output/'initial.pt',device)
        initial_test=evaluate('test-initial',initial_model,config['final_seed_base'],config['final_episodes'])
        report={'test_best':final,'test_initial':initial_test,'test_gain':scenario_gain(final,initial_test),
            'primary_checkpoint':primary,'selection_objective':practice.get('forks',{}).get('objective','mean'),
            'test_index':index(final,initial_test),'best_validation_index':best,'total_training_decisions':decisions,
            'best_checkpoint_decisions':info['decisions'],'profile_best_validation_normalized_means':profile_bests,
            'note':'Held-out seeds never used for training/checkpoint selection. Per-profile winners are snapshots of one shared model, not independent policies.'}
        if 'best_of_4' in final:
            from .best_of import comparison
            report['test_best4_index']=comparison(final['best_of_4'],initial_test['best_of_4'])
        json_write(output/'result.json',report)
        publish('complete',status='complete',test_mean=final['mean'],test_index=report['test_index'],
            profile_scores=final['profiles'],best_validation_index=best,
            memory_modes=final['memory_modes'],condition_cells=final['condition_cells'])
    except BaseException as error:
        publish('failed',status='failed',error=f'{type(error).__name__}: {error}')
        raise
    finally:
        if search_router is not None:search_router.close()
        if pool:pool.close()
        api.close_training_worker()
        if os.name=='nt':ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

