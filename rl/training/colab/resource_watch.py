"""Read-only, standalone process-tree resource observer; no training imports."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import itertools
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid


def utc():
    return datetime.now(timezone.utc).isoformat()


def memory_reading(process):
    result = {'rss_bytes': None, 'pss_bytes': None, 'uss_bytes': None, 'errors': []}
    try:
        result['rss_bytes'] = process.memory_info().rss
    except Exception as error:
        result['errors'].append(f'memory_info: {type(error).__name__}: {error}')
    try:
        method = getattr(process, 'memory_footprint', None) or process.memory_full_info
        full = method()
        result['pss_bytes'], result['uss_bytes'] = getattr(full, 'pss', None), getattr(full, 'uss', None)
        result['detail_source'] = method.__name__
    except Exception as error:
        result['errors'].append(f'memory_details: {type(error).__name__}: {error}')
    return result


def aggregate(rows):
    groups = {}
    for name in ('root', 'workers', 'other_children', 'all'):
        members = rows if name == 'all' else [r for r in rows if r['group'] == name]
        metrics = {'process_count': len(members)}
        for field in ('rss_bytes', 'pss_bytes', 'uss_bytes'):
            values = [r[field] for r in members if r[field] is not None]
            metrics[field] = {'total': sum(values) if len(values) == len(members) else None,
                'observed_sum': sum(values) if values or not members else None,
                'observed_count': len(values), 'missing_count': len(members) - len(values)}
        groups[name] = metrics
    return groups


def process_tree(root):
    errors, processes = [], {root.pid: root}
    try:
        processes.update({p.pid: p for p in root.children(recursive=True)})
    except Exception as error:
        errors.append(f'children: {type(error).__name__}: {error}')
    records = {}
    for pid, process in processes.items():
        record = {'pid': pid, 'ppid': None, 'name': None, 'create_time': None, 'spawn_worker': False}
        try:
            record.update(ppid=process.ppid(), name=process.name(), create_time=process.create_time())
            command = ' '.join(process.cmdline())
            record['spawn_worker'] = record['ppid'] == root.pid and (
                'multiprocessing.spawn' in command or 'spawn_main(' in command or '--multiprocessing-fork' in command)
        except Exception as error:
            record['identity_error'] = f'{type(error).__name__}: {error}'
        record.update(memory_reading(process))
        records[pid] = record
    for pid, row in records.items():
        ancestor, seen = pid, set()
        row['group'] = 'root' if pid == root.pid else 'other_children'
        while ancestor in records and ancestor not in seen:
            seen.add(ancestor)
            if records[ancestor]['spawn_worker']:
                row['group'] = 'workers'; break
            ancestor = records[ancestor]['ppid']
        row['native_node'] = str(row['name']).lower() in ('node', 'node.exe')
    return {'processes': list(records.values()), 'groups': aggregate(list(records.values())),
            'tree_read_errors': errors,
            'tree_enumeration_complete': not errors,
            'tree_classification_complete': not errors and not any('identity_error' in r for r in records.values()),
            'memory_scope': 'RSS may double-count shared pages; PSS/USS never substituted with RSS. '
                            'Workers include direct spawned Python workers and their observed descendants.'}


def cgroup_memory(pid, proc_root=Path('/proc'), mount_root=Path('/sys/fs/cgroup')):
    report = {'scope': 'Target process cgroup (may include other VM processes); not process-tree memory.',
              'path': None, 'current_bytes': None, 'max_bytes': None, 'events': None, 'errors': []}
    if platform.system() != 'Linux':
        report['errors'].append('cgroup memory unavailable on this platform'); return report
    try:
        rows = (proc_root / str(pid) / 'cgroup').read_text().splitlines()
        v2 = next((line.split(':', 2)[2] for line in rows if line.startswith('0::')), None)
        if v2 is not None:
            base = (mount_root / v2.lstrip('/')).resolve(); current, maximum = 'memory.current', 'memory.max'
        else:
            path = next(line.split(':', 2)[2] for line in rows if 'memory' in line.split(':')[1].split(','))
            base = (mount_root / 'memory' / path.lstrip('/')).resolve()
            current, maximum = 'memory.usage_in_bytes', 'memory.limit_in_bytes'
        if not base.is_relative_to(mount_root.resolve()):
            raise ValueError('Target cgroup path escaped mount root')
        report.update(path=str(base), membership_source=str(proc_root / str(pid) / 'cgroup'))
        for file, key in ((current, 'current_bytes'), (maximum, 'max_bytes')):
            try:
                value = (base / file).read_text().strip()
                report[key] = value if value == 'max' else int(value)
            except Exception as error:
                report['errors'].append(f'{file}: {error}')
        try:
            report['events'] = {k: int(v) for k, v in (line.split() for line in
                (base / 'memory.events').read_text().splitlines())}
        except Exception as error:
            report['errors'].append(f'memory.events: {error}')
    except Exception as error:
        report['errors'].append(f'cgroup discovery: {error}')
    return report


def gpu_sample():
    binary = shutil.which('nvidia-smi')
    if not binary:
        return {'gpus': None, 'error': 'nvidia-smi unavailable'}
    try:
        result = subprocess.run([binary, '--query-gpu=index,utilization.gpu,memory.used,memory.total',
            '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=3, check=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        rows = []
        for line in result.stdout.splitlines():
            values = [s.strip() for s in line.split(',')]
            if len(values) != 4:
                raise ValueError('Unexpected nvidia-smi columns')
            numeric = lambda value: float(value) if value not in ('N/A', '[N/A]', 'Not Supported') else None
            rows.append(dict(zip(('index', 'utilization_percent', 'used_mib', 'total_mib'), map(numeric, values))))
        return {'gpus': rows, 'scope': 'Whole-device counters, not just the target process.'}
    except Exception as error:
        return {'gpus': None, 'error': f'{type(error).__name__}: {error}'}


def append_record(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
        stream.flush(); os.fsync(stream.fileno())


def observe(pid, create_time, *, output, local_output=None, status_path=None, interval=15,
            psutil_module=None, sleep=time.sleep, max_samples=None):
    if not math.isfinite(interval) or interval < 5:
        raise ValueError('Observer interval must be at least 5 seconds')
    if not math.isfinite(create_time) or create_time <= 0:
        raise ValueError('Target creation time must be finite and positive')
    if psutil_module is None:
        import psutil as psutil_module
    outputs = list(dict.fromkeys(Path(p).resolve() for p in (local_output, output) if p is not None))
    if not outputs or any(p.exists() for p in outputs):
        raise FileExistsError('Observer requires new unique output files; it never appends to an old session')
    observer_id = uuid.uuid4().hex
    reserved = set()
    def emit(record):
        record = {'schema': 'hif-resource-watch/1', 'observer_id': observer_id, 'timestamp': utc(),
                  'target_pid': pid, 'target_create_time': create_time, **record}
        for path in outputs:
            try:
                if path not in reserved:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open('x', encoding='utf8'):
                        pass
                    reserved.add(path)
                append_record(path, record)
            except OSError as error:
                print(f'resource observer write failed ({path}): {error}', file=sys.stderr, flush=True)
    boot = Path('/proc/sys/kernel/random/boot_id')
    try:
        boot_id = boot.read_text().strip() if boot.is_file() else None
    except OSError:
        boot_id = None
    emit({'event': 'observer_started', 'host': platform.node(),
          'boot_id': boot_id,
          'durability': 'Per-record flush/fsync; a VM or mount loss may still lose the final records.'})
    for index in range(max_samples) if max_samples is not None else itertools.count():
        try:
            root = psutil_module.Process(pid)
            actual_time, status = root.create_time(), root.status()
            if actual_time != create_time or status in ('zombie', 'dead'):
                emit({'event': 'process_disappeared', 'reason': 'pid_reused' if actual_time != create_time else status,
                      'returncode': None}); return
            sample = process_tree(root)
            try:
                memory = psutil_module.virtual_memory()
                sample['system_memory'] = {'total_bytes': memory.total, 'available_bytes': memory.available}
            except Exception as error:
                sample['system_memory'] = {'total_bytes': None, 'available_bytes': None, 'error': str(error)}
            sample['cgroup_memory'], sample['gpu'] = cgroup_memory(pid), gpu_sample()
            if status_path is not None:
                try:
                    sample['runtime_status'] = json.loads(Path(status_path).read_text(encoding='utf8'))
                except Exception as error:
                    sample['runtime_status'] = None; sample['runtime_status_error'] = str(error)
            emit({'event': 'resource_sample', **sample})
        except (psutil_module.NoSuchProcess, psutil_module.ZombieProcess):
            emit({'event': 'process_disappeared', 'reason': 'not_found_or_zombie', 'returncode': None}); return
        except Exception as error:
            emit({'event': 'observer_sample_error', 'error': f'{type(error).__name__}: {error}'})
        if max_samples is None or index + 1 < max_samples:
            sleep(interval)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--create-time', type=float, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--local-output', type=Path)
    parser.add_argument('--status-path', type=Path)
    parser.add_argument('--interval', type=float, default=15)
    args = parser.parse_args(argv)
    if args.pid < 1:
        parser.error('pid must be positive')
    observe(args.pid, args.create_time, output=args.output, local_output=args.local_output,
            status_path=args.status_path, interval=args.interval)


if __name__ == '__main__':
    main()
