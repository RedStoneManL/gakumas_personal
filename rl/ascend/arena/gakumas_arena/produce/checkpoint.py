"""JSON-safe HIF decision-boundary checkpoints, restored into a configured run.

Callbacks are intentionally external. A destination run must be constructed with
the same policies/configuration; this module restores execution state, not code.
Never expose a checkpoint to the acting policy: it contains the environment RNG.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import fields, is_dataclass
from functools import lru_cache
import hashlib
import importlib
import json
import math
from pathlib import Path

import numpy as np

from ..engine.training import content_version


SCHEMA_VERSION = 'arena-produce-checkpoint/1'
_TAG = '__arena_checkpoint_type__'
_STATIC_RUNTIME = frozenset({
    'repository', 'scenario', 'idol_loadout', 'produce_reward_cfg', 'exam_action_selectors',
    'produce_row', 'produce_setting', 'runtime_setting', 'produce_effects', 'event_suggestions',
    'event_details', 'card_searches', 'lesson_levels', 'produce_item_interpreter',
    'np_random', 'produce_choice_selector', 'audition_executor', 'end_day_executor',
    'customize_item_reward_selector', 'customize_item_offer_selector',
    'choices', 'events', 'customize_items', 'hif', 'hif_sampling_kernel',
    'hif_interval_shop', 'hif_special_training', 'hif_lifecycle',
})
_RUN_FIELDS = ('exam_history', 'completed_scheduled_days', 'terminated', 'fault', 'revision', '_observation')
_HELPERS = {
    'choices': {'runtime'}, 'events': {'runtime', 'library'},
    'hif': {'runtime', 'config', 'selection_memory', 'open_lessons', 'growth_panels', 'dearness_levels', 'produce_skills'},
    'hif_sampling_kernel': {'runtime', 'pools'},
    'hif_interval_shop': {'runtime'}, 'hif_special_training': {'runtime'},
    'hif_lifecycle': {'run', 'runtime'},
}
_MODULES = (
    'gakumas_rl.loadout', 'gakumas_rl.simulation.produce.runtime',
    'gakumas_rl.simulation.produce.items', 'gakumas_rl.simulation.produce.hif',
)


class ProduceCheckpointError(ValueError):
    pass


@lru_cache(maxsize=1)
def _records():
    # Fixed local module allowlist. A checkpoint cannot request arbitrary imports.
    return {f'{cls.__module__}.{cls.__qualname__}': cls
            for module in _MODULES for cls in vars(importlib.import_module(module)).values()
            if isinstance(cls, type) and is_dataclass(cls)}


def _encode(value):
    if value is None or type(value) in (str, bool, int):
        return value
    if isinstance(value, np.generic):
        return _encode(value.item())
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProduceCheckpointError('Checkpoint cannot contain non-finite numbers')
        return value
    if is_dataclass(value) and not isinstance(value, type):
        key = f'{type(value).__module__}.{type(value).__qualname__}'
        if key not in _records():
            raise ProduceCheckpointError(f'Unsupported state record: {key}')
        return {_TAG: 'record', 'record': key, 'fields': {f.name: _encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, np.ndarray):
        return {_TAG: 'array', 'dtype': str(value.dtype), 'items': _encode(value.tolist())}
    if isinstance(value, (set, frozenset, tuple)):
        values = list(value)
        if isinstance(value, (set, frozenset)):
            values.sort(key=lambda v: json.dumps(_encode(v), sort_keys=True))
        return {_TAG: type(value).__name__, 'items': [_encode(v) for v in values]}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    if isinstance(value, defaultdict):
        factories = {None: 'none', list: 'list', dict: 'dict', int: 'int', float: 'float', set: 'set'}
        if value.default_factory not in factories:
            raise ProduceCheckpointError('Unsupported defaultdict factory')
        return {_TAG: 'defaultdict', 'factory': factories[value.default_factory],
                'items': [[_encode(k), _encode(v)] for k, v in value.items()]}
    if isinstance(value, dict):
        if _TAG in value or any(not isinstance(k, str) for k in value):
            return {_TAG: 'map', 'items': [[_encode(k), _encode(v)] for k, v in value.items()]}
        return {k: _encode(v) for k, v in value.items()}
    raise ProduceCheckpointError(f'Unsupported checkpoint state value: {type(value).__name__}')


def _decode(value):
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    kind = value.get(_TAG)
    if kind is None:
        return {k: _decode(v) for k, v in value.items()}
    if kind == 'record':
        cls = _records().get(value['record'])
        if cls is None:
            raise ProduceCheckpointError(f'Unknown checkpoint record: {value["record"]}')
        allowed = {f.name for f in fields(cls)}
        if set(value['fields']) != allowed:
            raise ProduceCheckpointError(f'Checkpoint record fields changed: {value["record"]}')
        return cls(**{k: _decode(v) for k, v in value['fields'].items()})
    if kind in ('set', 'frozenset', 'tuple'):
        return {'set': set, 'frozenset': frozenset, 'tuple': tuple}[kind](_decode(value['items']))
    if kind in ('map', 'defaultdict'):
        result = {_decode(k): _decode(v) for k, v in value['items']}
        if kind == 'defaultdict':
            factory = {'none': None, 'list': list, 'dict': dict, 'int': int, 'float': float, 'set': set}.get(value['factory'])
            result = defaultdict(factory, result)
        return result
    if kind == 'array':
        dtype = np.dtype(value['dtype'])
        if dtype.hasobject:
            raise ProduceCheckpointError('Object arrays are not checkpoint state')
        return np.array(_decode(value['items']), dtype=dtype)
    raise ProduceCheckpointError(f'Unknown checkpoint type: {kind}')


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


@lru_cache(maxsize=4096)
def _file_hash(path, size, mtime_ns):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _files_digest(paths, base):
    result = {}
    for path in sorted(paths):
        stat = path.stat()
        result[path.relative_to(base).as_posix()] = _file_hash(str(path), stat.st_size, stat.st_mtime_ns)
    return _digest(result)


def _version(run):
    rt = run.runtime
    package = Path(__file__).resolve().parents[2]
    rule_paths = (list((package / 'gakumas_arena/produce').rglob('*.py'))
                  + list((package / 'gakumas_arena/produce/data').glob('*.json'))
                  + list((package / 'gakumas_rl/simulation/produce').rglob('*.py'))
                  + [package / 'gakumas_rl/repository/master_data.py', package / 'gakumas_rl/idol_config.py'])
    golden = content_version()
    return {'golden_rules': golden['golden_rules'], 'golden_sha256': golden['effective_sha256'],
            'produce_rules_sha256': _files_digest(rule_paths, package),
            'master_data_sha256': _files_digest(rt.repository.assets_dir.glob('*.yaml'), rt.repository.assets_dir)}


def _plain_configuration(value):
    """Hash immutable dataclasses without requiring reconstruction support."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain_configuration(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {str(k): _plain_configuration(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain_configuration(v) for v in value]
    return _encode(value)


def _configuration(run):
    rt = run.runtime
    return _digest(_plain_configuration({
        'scenario': rt.scenario, 'idol_loadout': rt.idol_loadout,
        'produce_reward_cfg': rt.produce_reward_cfg,
        'hif_config': rt.hif.config if rt.hif else None,
        'selection_memory': rt.hif.selection_memory if rt.hif else None,
        'research_config': getattr(rt, 'hif_research_config', None),
        'lifecycle_config': getattr(getattr(rt, 'hif_lifecycle', None), 'config', None),
        'event_schedule': run.event_schedule, 'day_actions': run.day_actions,
        'max_exam_decisions': run.max_exam_decisions,
        'id_overrides': run.bridge.id_overrides, 'enchant_overrides': run.bridge.enchant_overrides,
    }))


def snapshot(run):
    """Capture an already configured run at a public produce decision boundary."""
    if run.runtime._ability_chain_guard_depth:
        raise ProduceCheckpointError('Cannot checkpoint in the middle of an effect chain')
    if getattr(getattr(run, 'lifecycle', None), 'status', None) == 'running_exam':
        raise ProduceCheckpointError('Cannot checkpoint in the middle of an exam')
    # Materialize the current offer once, before capturing RNG and candidate state.
    run.observe()
    rt = run.runtime
    helpers = {}
    for name, excluded in _HELPERS.items():
        helper = getattr(rt, name, None)
        if helper is not None:
            helpers[name] = _encode({k: v for k, v in vars(helper).items() if k not in excluded})
    payload = {'runtime': _encode({k: v for k, v in vars(rt).items() if k not in _STATIC_RUNTIME}),
               'run': _encode({k: getattr(run, k) for k in _RUN_FIELDS}),
               'rng': _encode(rt.np_random.bit_generator.state), 'helpers': helpers,
               'customize_item': _encode(rt.customize_items.export())}
    return {'schema_version': SCHEMA_VERSION, 'produce_id': rt.scenario.produce_id,
            'ruleset': getattr(rt, 'hif_ruleset_version', 'legacy-hif-golden/1'),
            'content_version': _version(run), 'configuration_sha256': _configuration(run),
            'external_callbacks': 'Reattach the same deterministic policies; callback state is not serialized.',
            'payload': payload, 'payload_sha256': _digest(payload)}


def restore_into(run, checkpoint):
    """Restore into a fresh equivalently configured run without serializing callbacks."""
    rt = run.runtime
    if checkpoint.get('schema_version') != SCHEMA_VERSION:
        raise ProduceCheckpointError('Unsupported produce checkpoint schema')
    if checkpoint.get('produce_id') != rt.scenario.produce_id:
        raise ProduceCheckpointError('Checkpoint scenario mismatch')
    if checkpoint.get('ruleset') != getattr(rt, 'hif_ruleset_version', 'legacy-hif-golden/1'):
        raise ProduceCheckpointError('Checkpoint ruleset mismatch')
    if checkpoint.get('content_version') != _version(run):
        raise ProduceCheckpointError('Checkpoint content_version mismatch')
    if checkpoint.get('configuration_sha256') != _configuration(run):
        raise ProduceCheckpointError('Checkpoint configuration mismatch; create an equivalent run first')
    payload = checkpoint.get('payload', {})
    if checkpoint.get('payload_sha256') != _digest(payload):
        raise ProduceCheckpointError('Checkpoint payload checksum mismatch')
    runtime_state = _decode(payload['runtime'])
    run_state = _decode(payload['run'])
    helper_states = {k: _decode(v) for k, v in payload['helpers'].items()}
    if _STATIC_RUNTIME.intersection(runtime_state) or set(run_state) != set(_RUN_FIELDS):
        raise ProduceCheckpointError('Checkpoint contains forbidden or incomplete fields')
    for name, state in helper_states.items():
        if name not in _HELPERS or getattr(rt, name, None) is None or _HELPERS[name].intersection(state):
            raise ProduceCheckpointError(f'Checkpoint helper/configuration mismatch: {name}')
        if name == 'hif_lifecycle':
            try:
                rt.hif_lifecycle.validate_checkpoint_state(state)
            except ValueError as error:
                raise ProduceCheckpointError(str(error)) from error
    rng_state = _decode(payload['rng'])
    if rng_state.get('bit_generator') != rt.np_random.bit_generator.state['bit_generator']:
        raise ProduceCheckpointError('Checkpoint RNG implementation mismatch')
    try:
        probe_rng = type(rt.np_random.bit_generator)()
        probe_rng.state = rng_state
    except Exception as error:
        raise ProduceCheckpointError('Invalid checkpoint RNG state') from error
    # Decode and validate all structural content before mutating the destination.
    custom = _decode(payload['customize_item'])
    if not isinstance(custom, dict) or not isinstance(custom.get('history', []), list):
        raise ProduceCheckpointError('Invalid checkpoint custom item history')
    if custom.get('item_id'):
        row = rt.customize_items.table.first(custom['item_id'])
        if row is None:
            raise ProduceCheckpointError('Checkpoint custom item is not in master data')
        plan = rt.idol_loadout.stat_profile.plan_type if rt.idol_loadout else None
        if plan and row.get('planType') not in (plan, 'ProducePlanType_Common'):
            raise ProduceCheckpointError('Checkpoint custom item plan mismatch')
        for field in ('fire_count', 'cooldown_remaining'):
            count = custom.get(field, 0)
            if type(count) is not int or count < 0:
                raise ProduceCheckpointError(f'Invalid checkpoint custom item {field}')
        limit = int(row.get('produceEffectTriggerCount') or 0)
        if limit > 0 and custom.get('fire_count', 0) > limit:
            raise ProduceCheckpointError('Checkpoint custom item exceeds its fire limit')
    for key, value in runtime_state.items():
        setattr(rt, key, value)
    for name, state in helper_states.items():
        for key, value in state.items():
            setattr(getattr(rt, name), key, value)
    rt.customize_items.restore(custom)
    rt.customize_items.history = _decode(_encode(custom.get('history', [])))
    rt.np_random.bit_generator.state = rng_state
    for key, value in run_state.items():
        setattr(run, key, value)
    return run


__all__ = ['SCHEMA_VERSION', 'ProduceCheckpointError', 'snapshot', 'restore_into']
