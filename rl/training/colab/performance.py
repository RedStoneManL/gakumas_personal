"""Seal initial identity settings once; runtime controls are stored separately."""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re


SCHEMA = 'hif-colab-performance-profile/1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def hardware_profile():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('A CUDA GPU is required for the Colab performance profile')
    cores = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else (os.cpu_count() or 1)
    quota = Path('/sys/fs/cgroup/cpu.max')
    if quota.is_file():
        amount, period = quota.read_text().strip().split()
        if amount != 'max':
            cores = min(cores, max(1, math.floor(int(amount) / int(period))))
    return {'gpu_name': torch.cuda.get_device_name(0),
            'gpu_memory_bytes': torch.cuda.get_device_properties(0).total_memory,
            'available_cpu_count': cores}


def suggested_settings(hardware):
    gib = hardware['gpu_memory_bytes'] / 2**30
    # These are conservative starting profiles, not measured speed rankings.
    cores = int(hardware['available_cpu_count'])
    # Leave room for the central encoder/learner on larger CPU allocations.
    workers = max(1, cores - 2 if cores >= 6 else cores)
    return {'workers': workers,
            'microbatch_size': 16 if gib >= 70 else 8 if gib >= 36 else 4 if gib >= 22 else 2}


def prepare_config(base_config, *, manifest_sha256, run_name, persistent_root,
                   output, hardware, workers='auto', microbatch_size='auto'):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', run_name):
        raise ValueError('Invalid run name')
    def request(value, name):
        if value == 'auto':
            return 'auto'
        if type(value) is int:
            number = value
        elif isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*', value.strip()):
            number = int(value.strip())
        else:
            raise ValueError(f'{name} must be auto or a positive integer')
        if number < 1:
            raise ValueError(f'{name} must be a positive integer')
        return number
    workers = request(workers, 'workers')
    microbatch_size = request(microbatch_size, 'microbatch_size')
    base_identity = {'bundle_manifest_sha256': manifest_sha256, 'base_config_sha256': digest(base_config)}
    folder = Path(persistent_root) / '_performance_configs'
    folder.mkdir(parents=True, exist_ok=True)
    sealed = folder / f'{run_name}.json'
    if sealed.exists():
        record = json.loads(sealed.read_text(encoding='utf8'))
        if (record.get('schema') != SCHEMA or record.get('base_identity') != base_identity
                or digest(record.get('config')) != record.get('config_sha256')):
            raise ValueError('Saved performance configuration differs from this bundle/task; use its original bundle or a new run name')
        values = record['settings']
        for requested, key in ((workers, 'workers'), (microbatch_size, 'microbatch_size')):
            if requested != 'auto' and int(requested) != values[key]:
                raise ValueError('Initial performance settings are fixed for this run; use the runtime control cell to adjust execution without changing base identity')
        resumed = True
    else:
        values = suggested_settings(hardware)
        for requested, key in ((workers, 'workers'), (microbatch_size, 'microbatch_size')):
            if requested != 'auto':
                values[key] = int(requested)
        resolved = deepcopy(base_config)
        resolved['workers'] = values['workers']
        resolved.setdefault('ppo', {})['microbatch_size'] = values['microbatch_size']
        resolved['ppo']['minibatch_size'] = max(resolved['ppo'].get('minibatch_size', 64), values['microbatch_size'])
        record = {'schema': SCHEMA, 'base_identity': base_identity, 'settings': values,
                  'initial_hardware': hardware, 'config': resolved, 'config_sha256': digest(resolved),
                  'measured_optimum_claimed': False}
        # Exclusive creation refuses concurrent initializers instead of replacing
        # another session's choices. A partial record is rejected on the next run.
        with sealed.open('x', encoding='utf8') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        resumed = False
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record['config'], ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return {'settings': record['settings'], 'reused_saved_profile': resumed,
            'initial_hardware': record['initial_hardware'], 'current_hardware': hardware,
            'sealed_config': str(sealed), 'effective_config': str(output),
            'initial_minibatch_size': record['config'].get('ppo', {}).get('minibatch_size'),
            'runtime_control_changes_base_identity': False,
            'measured_optimum_claimed': False}
