"""Copy a verified safe training boundary to a new, compatible Colab run.

The caller verifies its bundle and canonicalizes new_identity['config'] first.
Only the four runtime performance settings may change. Source run files are read-only.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import tempfile

from persistence import (SnapshotStore, RUN_SCHEMA, atomic_json, bind_identity,
                         canonical_bytes, copy_verified, file_hash, object_hash, safe_child)


MIGRATION_SCHEMA = 'gakumas-compatible-run-migration/1'


def _json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Expected a regular migration input: {path}')
    return json.loads(path.read_text(encoding='utf8'))


def _config_compatibility(old, new):
    for identity in (old, new):
        if identity.get('schema') != RUN_SCHEMA:
            raise ValueError('Unsupported run identity schema')
        if identity.get('config_sha256') != object_hash(identity.get('config')):
            raise ValueError('Run identity config checksum does not match')
    allowed_identity = {'run_name', 'bundle', 'config', 'config_sha256'}
    if ({k: v for k, v in old.items() if k not in allowed_identity} !=
            {k: v for k, v in new.items() if k not in allowed_identity}):
        raise ValueError('Migration task, Arena version, model or encoding identity differs')
    old_config, new_config = old['config'], new['config']
    permitted = deepcopy(old_config)
    try:
        permitted['workers'] = new_config['workers']
        permitted['episodes_per_update'] = new_config['episodes_per_update']
        permitted['ppo']['minibatch_size'] = new_config['ppo']['minibatch_size']
        permitted['ppo']['microbatch_size'] = new_config['ppo']['microbatch_size']
    except (KeyError, TypeError) as error:
        raise ValueError('Migration requires canonical workers/PPO config fields') from error
    if permitted != new_config:
        raise ValueError('Only workers, episodes_per_update and PPO batch sizes may change during migration')
    if type(new_config['workers']) is not int or new_config['workers'] < 1:
        raise ValueError('Migration workers must be a positive integer')
    microbatch = new_config['ppo']['microbatch_size']
    if type(microbatch) is not int or microbatch < 1:
        raise ValueError('Migration microbatch size must be a positive integer')
    return {name: {'old': a, 'new': b} for name, a, b in (
        ('workers', old_config['workers'], new_config['workers']),
        ('episodes_per_update', old_config['episodes_per_update'], new_config['episodes_per_update']),
        ('ppo.minibatch_size', old_config['ppo']['minibatch_size'], new_config['ppo']['minibatch_size']),
        ('ppo.microbatch_size', old_config['ppo']['microbatch_size'], microbatch)) if a != b}


def _checkpoint(path, identity):
    from gakumas_training.runtime.checkpoint import load_checkpoint
    return load_checkpoint(path, task=identity['task'], config=identity['config'],
        arena_version=identity['arena_version'], model_schema=identity['model_schema'],
        encoding_schema=identity['encoding_schema'])


def _state_matches(state, checkpoint):
    for key in ('iteration', 'policy_version', 'seed_cursor', 'episodes_seen', 'decisions'):
        if state.get(key) != checkpoint.get(key):
            raise ValueError(f'Checkpoint and persistent state disagree: {key}')
    elapsed = state.get('active_wall_seconds')
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Invalid migrated cumulative active wall time')


def _existing_target(persistent_root, target_name, local_run, new_identity, source_name):
    target = persistent_root / target_name
    marker = _json(target / 'migration.json')
    if (marker.get('schema') != MIGRATION_SCHEMA or marker.get('source_run_name') != source_name or
            marker.get('target_run_name') != target_name or
            marker.get('target_identity_sha256') != object_hash(new_identity)):
        raise ValueError('Existing migration target belongs to a different request')
    if _json(target / 'run-identity.json') != new_identity:
        raise ValueError('Existing migration target identity does not match')
    store = SnapshotStore(persistent_root, target_name, new_identity)
    state = store.restore(local_run)
    if state is None:
        raise ValueError('Existing migration has no complete recoverable target snapshot')
    manifest = _json(local_run / 'manifest.json')
    if (manifest.get('migration', marker) != marker or state.get('migration', marker) != marker):
        raise ValueError('Existing target snapshot has different migration provenance')
    if manifest.get('migration') != marker and state.get('migration') != marker:
        raise ValueError('Existing target snapshot lost its durable migration provenance')
    for key in ('config', 'arena_version', 'model_schema', 'encoding_schema'):
        if manifest.get(key) != new_identity.get(key):
            raise ValueError(f'Existing target runtime manifest differs: {key}')
    checkpoint = _checkpoint(local_run / 'checkpoints/latest.pt', new_identity)
    _state_matches(state, checkpoint)
    if checkpoint['iteration'] < marker['iteration'] or checkpoint['seed_cursor'] < marker['seed_cursor']:
        raise ValueError('Existing migration target predates its migration boundary')
    return state


def migrate_run(persistent_root, source_run_name, target_run_name, local_run, new_identity):
    """Migrate once, or recover an already completed identical migration.

    Failed/partial targets fail closed. Callers must not fall back to fresh
    training after this function raises. Existing source snapshots are untouched.
    """
    persistent_root, local_run = Path(persistent_root).resolve(), Path(local_run).resolve()
    for name in (source_run_name, target_run_name):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', name):
            raise ValueError('Migration run names must be safe single directory names')
    if source_run_name == target_run_name:
        raise ValueError('Migration requires a new target run name')
    if not persistent_root.is_dir():
        raise FileNotFoundError('Persistent root must already exist')
    source_dir = safe_child(persistent_root, source_run_name)
    target_dir = safe_child(persistent_root, target_run_name)
    if (local_run.is_relative_to(persistent_root) or persistent_root.is_relative_to(local_run)):
        raise ValueError('Migration local scratch must be separate from persistent data')
    new_identity = deepcopy(new_identity)
    if new_identity.get('run_name') != target_run_name:
        raise ValueError('New identity run name differs from migration target')
    if target_dir.exists() and any(target_dir.iterdir()):
        return _existing_target(persistent_root, target_run_name, local_run, new_identity, source_run_name)
    if local_run.exists() and any(local_run.iterdir()):
        raise ValueError('Migration refuses to overwrite an existing local run')
    old_identity = _json(source_dir / 'run-identity.json')
    if old_identity.get('run_name') != source_run_name or not (source_dir / 'snapshots').is_dir():
        raise ValueError('Source is not an initialized snapshot run')
    changes = _config_compatibility(old_identity, new_identity)
    # Constructor only checks already-existing source identity/directories. No
    # publish, retention, pointer replacement or source-file rewrite is invoked.
    source = SnapshotStore(persistent_root, source_run_name, old_identity)
    selected = source.latest()
    if selected is None:
        raise ValueError('Source has no complete recoverable snapshot')
    # Pin this already-verified immutable boundary while restoring; a concurrently
    # advancing source must not silently change which generation is migrated.
    source.latest = lambda **kwargs: selected
    local_run.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.migration-', dir=local_run.parent) as temporary:
        scratch = Path(temporary) / 'source'
        state = deepcopy(source.restore(scratch))
        checkpoint_path = scratch / 'checkpoints/latest.pt'
        checkpoint = _checkpoint(checkpoint_path, old_identity)
        _state_matches(state, checkpoint)
        manifest = _json(scratch / 'manifest.json')
        for key in ('config', 'arena_version', 'model_schema', 'encoding_schema'):
            if manifest.get(key) != old_identity.get(key):
                raise ValueError(f'Source runtime manifest disagrees with identity: {key}')
        provenance = {'schema': MIGRATION_SCHEMA,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source_run_name': source_run_name, 'target_run_name': target_run_name,
            'source_identity_sha256': object_hash(old_identity),
            'target_identity_sha256': object_hash(new_identity),
            'source_bundle': deepcopy(old_identity.get('bundle')),
            'target_bundle': deepcopy(new_identity.get('bundle')),
            'source_snapshot': selected['path'].name,
            'source_snapshot_generation': selected['manifest']['generation'],
            'source_snapshot_manifest_sha256': file_hash(selected['path'] / 'snapshot.json'),
            'source_checkpoint_sha256': file_hash(checkpoint_path),
            'source_recovery_warnings': deepcopy(source.recovery_warnings),
            'iteration': checkpoint['iteration'], 'seed_cursor': checkpoint['seed_cursor'],
            'active_wall_seconds': state['active_wall_seconds'], 'config_changes': changes,
            'boundary': 'after_complete_update', 'bitwise_replay_claimed': False,
            'continuation': 'model/optimizer/encoder/RNG/cursors/history retained; worker ordering may differ'}
        checkpoint['config'] = deepcopy(new_identity['config'])
        # New-schema checkpoints can carry hot overrides. Retain those except
        # where the caller explicitly changed the corresponding base setting.
        if 'execution_settings' in checkpoint:
            for name, change in changes.items():
                key = name.removeprefix('ppo.')
                checkpoint['execution_settings'][key] = change['new']
                checkpoint.get('pending_execution_settings', {}).pop(key, None)
        from gakumas_training.runtime.checkpoint import save_checkpoint
        save_checkpoint(checkpoint_path, checkpoint)
        _checkpoint(checkpoint_path, new_identity)
        manifest['config'] = deepcopy(new_identity['config'])
        for key in ('execution_settings', 'pending_execution_settings', 'execution_control_state'):
            if key in checkpoint:
                state[key] = deepcopy(checkpoint[key])
                manifest[key] = deepcopy(checkpoint[key])
        if 'workers' in manifest:
            manifest['workers'] = checkpoint.get('execution_settings', new_identity['config'])['workers']
        if 'collection' in manifest:
            manifest['collection'] = ('single_worker_frozen_policy_complete_episodes' if
                checkpoint.get('execution_settings', new_identity['config'])['workers'] == 1 else
                'spawned_synchronous_waves_parent_batched_policy_complete_episodes')
        if 'collection' in manifest:
            manifest['collection'] = ('single_worker_frozen_policy_complete_episodes'
                if new_identity['config']['workers'] == 1 else
                'spawned_synchronous_waves_parent_batched_policy_complete_episodes')
        manifest['migration'] = provenance
        atomic_json(scratch / 'manifest.json', manifest)
        state['identity_sha256'] = object_hash(new_identity)
        state['migration'] = provenance
        atomic_json(scratch / 'colab-state.json', state)
        atomic_json(scratch / 'run-identity.json', new_identity)
        # Reserve a fresh target only after all source/config/checkpoint checks.
        # Any interruption after reservation leaves a visibly incomplete target
        # which a later migration call rejects instead of starting from scratch.
        target_dir.mkdir(parents=True, exist_ok=True)
        if any(target_dir.iterdir()):
            raise FileExistsError('Another initializer populated the migration target')
        with (target_dir / 'run-identity.json').open('xb') as stream:
            stream.write(canonical_bytes(new_identity) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        target = SnapshotStore(persistent_root, target_run_name, new_identity)
        bind_identity(local_run, new_identity)
        for path in scratch.rglob('*'):
            if path.is_file() and path.name != 'run-identity.json':
                copy_verified(path, safe_child(local_run, path.relative_to(scratch)))
        target.publish(local_run, state)
        verification = Path(temporary) / 'verified-target'
        verified_state = SnapshotStore(persistent_root, target_run_name, new_identity).restore(verification)
        restored_checkpoint = _checkpoint(verification / 'checkpoints/latest.pt', new_identity)
        _state_matches(verified_state, restored_checkpoint)
        if verified_state != state or _json(verification / 'manifest.json').get('migration') != provenance:
            raise ValueError('Published migration did not restore its exact state/provenance')
        for namespace in ('training', 'evaluation'):
            for path in (scratch / namespace).rglob('*.jsonl'):
                if path.read_bytes() != (verification / path.relative_to(scratch)).read_bytes():
                    raise ValueError('Migrated historical logs changed during snapshot publication')
        # Root marker is the final commit for idempotent migrate-from invocations.
        atomic_json(target_dir / 'migration.json', provenance)
        atomic_json(local_run / 'migration.json', provenance)
        return verified_state
