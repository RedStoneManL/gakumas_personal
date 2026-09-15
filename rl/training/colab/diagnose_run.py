"""Read mounted-Drive diagnostics without a live kernel, Torch, or training ZIP.

This is a diagnostic reader, not a checkpoint restore validator. It never writes
to the run and deliberately does not load or hash model/optimizer weights.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re


MAX_METADATA_BYTES = 16 * 1024 * 1024


def _bytes(path, limit=MAX_METADATA_BYTES):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Not a regular file: {path}')
    if path.stat().st_size > limit:
        raise ValueError(f'Diagnostic read size limit exceeded: {path}')
    return path.read_bytes()


def _json(path):
    return json.loads(_bytes(path).decode('utf-8-sig'))


def _child(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError(f'Path outside diagnostic run: {relative}')
    return path


def _verified_small(snapshot, manifest, name):
    expected = manifest['files'][name]
    data = _bytes(_child(snapshot, name))
    if len(data) != expected['size'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
        raise ValueError(f'Metadata checksum mismatch: {name}')
    return json.loads(data)


def tail_text(path, lines=60, limit=512 * 1024):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Not a regular diagnostic log: {path}')
    with path.open('rb') as stream:
        size = stream.seek(0, 2)
        start = max(0, size - limit)
        stream.seek(start)
        data = stream.read(limit)
    if start:
        data = data.partition(b'\n')[2]
    return '\n'.join(data.decode('utf-8', errors='replace').splitlines()[-lines:])


def _metric_summary(row):
    result = {k: row[k] for k in (
        'iteration', 'namespace', 'episodes', 'decisions', 'execution_settings',
        'collection_seconds', 'update_seconds', 'seconds', 'policy_timings',
        'raw_score_mean', 'raw_score_min', 'raw_score_max', 'terminations',
        'loadout_profiles', 'setup_modes') if k in row}
    if 'ppo' in row:
        result['ppo'] = {k: row['ppo'][k] for k in (
            'optimizer_steps', 'kl', 'clip_fraction', 'entropy', 'value_loss',
            'effective_microbatch_size', 'oom_fallback_count', 'kl_stop_reason') if k in row['ppo']}
    return result


def _metrics_tail(run, manifest, namespace, count=3):
    log = manifest.get('logs', {}).get(namespace + '/metrics.jsonl')
    if not log:
        return []
    suffix = b''
    for chunk in reversed(log['chunks']):
        data = _bytes(_child(run, chunk['path']))
        if len(data) != chunk['size'] or hashlib.sha256(data).hexdigest() != chunk['sha256']:
            raise ValueError(f'Diagnostic metric chunk checksum mismatch: {chunk["path"]}')
        if len(data) + len(suffix) > MAX_METADATA_BYTES:
            raise ValueError('Metric tail exceeded diagnostic read size limit')
        suffix = data + suffix
        if suffix.count(b'\n') >= count + 1:
            break
    rows = []
    for line in suffix.splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(_metric_summary(row))
        except (ValueError, UnicodeError):
            pass  # The earliest line can start in the middle of a log chunk.
    return rows[-count:]


def resource_summary(path, limit=256 * 1024 * 1024):
    """Stream bounded telemetry into stage summaries without retaining PID history."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Not a regular resource log')
    groups, events, consumed, invalid = {}, [], 0, 0
    with path.open('rb') as stream:
        while consumed < limit:
            line = stream.readline(min(1024 * 1024, limit - consumed))
            if not line:
                break
            consumed += len(line)
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('Expected resource object')
            except (ValueError, UnicodeError):
                invalid += 1
                continue
            if row.get('event') != 'resource_sample':
                events.append({k: row[k] for k in ('timestamp', 'event', 'reason', 'error', 'boot_id', 'returncode') if k in row})
                events = events[-20:]
                continue
            status = row.get('runtime_status') or {}
            # The status is the last published boundary, not a fresh learner query.
            key = (row.get('observer_id'), str(status.get('iteration')), str(status.get('stage')))
            if key not in groups and len(groups) >= 1000:
                continue
            group = groups.setdefault(key, {'iteration': status.get('iteration'), 'stage': status.get('stage'),
                'first_timestamp': row.get('timestamp'), 'samples': 0, 'metrics': {}})
            group['last_timestamp'] = row.get('timestamp')
            group['samples'] += 1
            totals = row.get('groups') or {}
            root_pss = totals.get('root', {}).get('pss_bytes', {}).get('total')
            complete = row.get('tree_enumeration_complete', False) and row.get('tree_classification_complete', False)
            values = {'root_pss_gib': root_pss / 2**30 if isinstance(root_pss, (int, float)) else None}
            for name in ('workers', 'all'):
                pss = totals.get(name, {}).get('pss_bytes', {}).get('total')
                values[name + '_pss_gib'] = pss / 2**30 if complete and isinstance(pss, (int, float)) else None
            values['worker_count'] = sum(p.get('spawn_worker') is True for p in row.get('processes', [])) if complete else None
            available = (row.get('system_memory') or {}).get('available_bytes')
            values['system_available_gib'] = available / 2**30 if isinstance(available, (int, float)) else None
            for name, value in values.items():
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    continue
                metric = group['metrics'].setdefault(name, {'first': value, 'min': value, 'max': value, 'valid_samples': 0})
                metric.update(last=value, min=min(metric['min'], value), max=max(metric['max'], value),
                              valid_samples=metric['valid_samples'] + 1)
    return {'stages': list(groups.values()), 'events': events, 'invalid_lines': invalid,
            'bytes_read': consumed, 'truncated': path.stat().st_size > consumed,
            'note': 'Stages use the last published boundary status; missing metrics remain absent. '
                    'Compare similar stages and decision counts before inferring a leak.'}


def diagnose_run(persistent_root, run_name, *, tail_lines=60):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', run_name):
        raise ValueError('Invalid RUN_NAME')
    root = Path(persistent_root).resolve()
    run = _child(root, run_name)
    report = {'schema': 'hif-offline-diagnostics/1', 'run_name': run_name,
              'run_directory': str(run), 'warnings': [],
              'scope': 'Read-only historical metadata; no live process check, no weights loaded, no automatic restart'}
    identity_hash = None
    identity_path = run / 'run-identity.json'
    try:
        identity = _json(identity_path)
        canonical = json.dumps(identity, sort_keys=True, separators=(',', ':'),
                               ensure_ascii=False, allow_nan=False).encode()
        identity_hash = hashlib.sha256(canonical).hexdigest()
        cfg = identity.get('config', {})
        report['initial_config'] = {k: cfg.get(k) for k in (
            'task', 'workers', 'episodes_per_update', 'eval_every_updates', 'eval_episodes', 'ppo')}
    except (OSError, ValueError, TypeError) as error:
        report['warnings'].append(f'Run identity unavailable: {error}')
    for label, path in (
        ('historical_session_lease', root / '_notebook_sessions' / (run_name + '.json')),
        ('last_boundary_status', root / '_runtime_controls' / (run_name + '.status.json')),
        ('desired_execution', root / '_runtime_controls' / (run_name + '.json'))):
        if path.is_file():
            try:
                report[label] = _json(path)
            except (OSError, ValueError, TypeError) as error:
                report['warnings'].append(f'{label}: {error}')
    report['historical_status_note'] = ('A saved PID/returncode=null does not establish that the old VM is alive. '
        'last_boundary_status.last_error concerns control requests, not necessarily training failure.')
    snapshots = []
    for snapshot in (run / 'snapshots').glob('snapshot-*'):
        if not snapshot.is_dir() or snapshot.is_symlink():
            continue
        try:
            commit = _json(snapshot / 'COMMITTED.json')
            manifest_bytes = _bytes(snapshot / 'snapshot.json')
            if hashlib.sha256(manifest_bytes).hexdigest() != commit['manifest_sha256']:
                raise ValueError('Snapshot manifest checksum mismatch')
            manifest = json.loads(manifest_bytes)
            if (identity_hash is None or manifest.get('identity_sha256') != identity_hash
                    or manifest.get('schema') != 'gakumas-mounted-snapshot/1'
                    or type(manifest.get('generation')) is not int or manifest['generation'] < 0):
                raise ValueError('Snapshot identity/schema/generation mismatch')
            state = _verified_small(snapshot, manifest, 'colab-state.json')
            if state.get('identity_sha256') != identity_hash:
                raise ValueError('State identity mismatch')
            checkpoint = _child(snapshot, 'checkpoints/latest.pt')
            if (checkpoint.is_symlink() or not checkpoint.is_file()
                    or checkpoint.stat().st_size != manifest['files']['checkpoints/latest.pt']['size']):
                raise ValueError('Checkpoint missing or size mismatch')
            record = {'snapshot': str(snapshot), 'generation': manifest['generation'], 'state': state,
                      'validation': 'Commit and state metadata hashes verified; checkpoint size only. '
                                    'Full weight integrity must still be checked by normal resume.'}
            if 'session.json' in manifest['files']:
                record['session'] = _verified_small(snapshot, manifest, 'session.json')
            snapshots.append((record, manifest))
        except (OSError, ValueError, KeyError, TypeError) as error:
            report['warnings'].append(f'{snapshot.name}: {error}')
    snapshots.sort(key=lambda pair: (pair[0]['generation'], pair[0]['snapshot']))
    report['saved_snapshots'] = [pair[0] for pair in snapshots]
    if snapshots:
        record, manifest = snapshots[-1]
        report['latest_saved_state'] = record['state']
        for namespace in ('training', 'evaluation'):
            try:
                report[namespace + '_metrics'] = _metrics_tail(run, manifest, namespace)
            except (OSError, ValueError, KeyError, TypeError) as error:
                report['warnings'].append(f'{namespace} metrics: {error}')
    diagnostics = root / '_session_diagnostics' / run_name
    for label, name in (('console_logs', 'training-console.log'), ('resource_logs', 'resources*.jsonl')):
        entries = []
        for path in sorted(diagnostics.glob('*/' + name), reverse=True)[:3]:
            try:
                entry = {'path': str(path), 'bytes': path.stat().st_size, 'tail': tail_text(path, tail_lines)}
                if label == 'resource_logs':
                    entry['summary'] = resource_summary(path)
                entries.append(entry)
            except (OSError, ValueError) as error:
                report['warnings'].append(f'{path}: {error}')
        report[label] = entries
    if not report['console_logs']:
        report['warnings'].append('No training-console.log found for this RUN_NAME; check the name and Drive account.')
    report['resource_history_note'] = ('Earlier notebooks did not record a continuous host-RAM history. '
        'Missing resource logs cannot prove or disprove a memory leak or OOM.')
    return report


def print_report(report):
    for key in ('run_name', 'latest_saved_state', 'historical_session_lease',
                'last_boundary_status', 'desired_execution', 'training_metrics', 'evaluation_metrics', 'warnings'):
        if key in report:
            print('\n' + key + ':')
            print(json.dumps(report[key], ensure_ascii=False, indent=2))
    for key in ('console_logs', 'resource_logs'):
        for entry in report.get(key, []):
            print('\n' + entry['path'])
            if 'summary' in entry:
                print(json.dumps(entry['summary'], ensure_ascii=False, indent=2))
            for line in entry['tail'].splitlines():
                print(line[:2400] + (' ... [完整行见导出的 JSON]' if len(line) > 2400 else ''))
    print('\n诊断未读取权重内容；恢复时仍由训练入口完整校验检查点。')
    print('保存的 PID/returncode 不代表旧进程当前仍存活；旧版没有连续的 RAM 历史。')
