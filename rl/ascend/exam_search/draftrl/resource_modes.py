"""Resource presets and configurable scale; apply between complete batches."""
from __future__ import annotations

import ctypes
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import torch
from .checkpoint import json_write
from gakumas_training.device import capture_retry_rng, restore_retry_rng, empty_accelerator_cache

SCHEMA = 'arena-resource-mode/1'
PARALLEL_FIELDS = {'workers', 'parallel_roots', 'microbatch', 'inference_batch', 'torch_threads'}
PRESETS = {
    'cluster': {'workers': 96, 'torch_threads': 2, 'microbatch': 2, 'parallel_roots': 24,
                'inference_batch': 32, 'cuda_memory_fraction': 0.9, 'priority': 'normal'},
    'daily': {'workers': 10, 'torch_threads': 2, 'microbatch': 4, 'parallel_roots': 2, 'inference_batch': 2,
              'cuda_memory_fraction': 0.35, 'priority': 'below_normal'},
    'high': {'workers': 20, 'torch_threads': 4, 'microbatch': 8, 'parallel_roots': 3, 'inference_batch': 3,
             'cuda_memory_fraction': 0.70, 'priority': 'normal'},
    'extra': {'workers': 24, 'torch_threads': 6, 'microbatch': 24, 'parallel_roots': 4, 'inference_batch': 4,
              'cuda_memory_fraction': 0.85, 'priority': 'normal'},
    'ultra': {'workers': 48, 'torch_threads': 6, 'microbatch': 24, 'parallel_roots': 16, 'inference_batch': 16,
              'cuda_memory_fraction': 0.85, 'priority': 'normal'},
}


def validate_request(value):
    if not isinstance(value, dict) or set(value) - {
            'schema', 'mode', 'request_id', 'requested_at', 'reason', 'parallelism'}:
        raise ValueError('Invalid resource request fields')
    if value.get('schema') != SCHEMA or value.get('mode') not in PRESETS:
        raise ValueError('Unknown resource mode')
    if 'parallelism' in value:
        fields = value['parallelism']
        if (value['mode'] != 'cluster' or not isinstance(fields, dict)
                or set(fields) - PARALLEL_FIELDS
                or any(type(n) is not int or n < 1 for n in fields.values())):
            raise ValueError('Cluster parallelism must contain positive integer scale settings')
    if not isinstance(value.get('request_id'), str) or not 1 <= len(value['request_id']) <= 128:
        raise ValueError('Invalid resource request ID')
    stamp = datetime.fromisoformat(value.get('requested_at', ''))
    if stamp.tzinfo is None:
        raise ValueError('Resource request timestamp needs a timezone')
    if not isinstance(value.get('reason', ''), str) or len(value.get('reason', '')) > 500:
        raise ValueError('Invalid resource request reason')
    return dict(value)


def apply_settings(settings, device='cuda'):
    torch.set_num_threads(settings['torch_threads'])
    # Release unused cached allocations when switching down. Live tensors survive.
    empty_accelerator_cache()
    if str(device).startswith('cuda'):
        torch.cuda.set_per_process_memory_fraction(settings['cuda_memory_fraction'])
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        priority = {'below_normal': 0x4000, 'normal': 0x20}[settings['priority']]
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), priority):
            raise OSError(ctypes.get_last_error(), 'Cannot apply training process priority')


class RuntimeResources:
    def __init__(self, output, default_mode):
        if default_mode not in PRESETS:
            raise ValueError('Unknown default resource mode')
        self.path = Path(output) / 'resource-mode.json'
        self.default_mode = default_mode
        self.current = None
        self.last_rejection = None

    def requested(self):
        if not self.path.exists():
            json_write(self.path, {'schema': SCHEMA, 'mode': self.default_mode,
                'request_id': 'startup', 'requested_at': datetime.now(timezone.utc).isoformat(),
                'reason': 'User-selected training resource preset'})
        if self.path.stat().st_size > 8192:
            raise ValueError('Resource request is too large')
        return validate_request(json.loads(self.path.read_text(encoding='utf-8-sig')))

    def apply(self, request, config, batch, pool, pool_factory):
        """Caller must have completed all episodes and the optimizer update."""
        request = validate_request(request)
        if (self.current and request['request_id'] == self.current['request_id']
                and request['mode'] == self.current['mode']):
            return pool, False
        settings = dict(PRESETS[request['mode']])
        if request['mode'] == 'cluster':
            overrides = config.get('parallelism', {})
            fields = PARALLEL_FIELDS
            if not isinstance(overrides, dict) or set(overrides) - fields:
                raise ValueError('Unknown cluster parallelism setting')
            overrides = {**overrides, **request.get('parallelism', {})}
            for name, value in overrides.items():
                if type(value) is not int or value < 1:
                    raise ValueError(f'Invalid cluster {name}: {value}')
            settings.update(overrides)
        # PPO weights each microbatch by the full optimizer block length, so
        # a final shorter microbatch (24+24+16=64) preserves that block.
        if not 1 <= settings['microbatch'] <= config.get('effective_minibatch', 64):
            raise ValueError('Resource mode must preserve the effective PPO batch')
        changed = self.current is None or any(self.current.get(k) != v for k, v in settings.items())
        if changed:
            # Pool construction must not advance model/action RNG state.
            import random
            rng = capture_retry_rng()
            try:
                if pool is not None:
                    pool.close()
                apply_settings(settings, config['device'])
                pool = pool_factory(settings['workers'])
            finally:
                restore_retry_rng(rng)
        config.update(workers=settings['workers'], minibatch=settings['microbatch'],
                      torch_threads=settings['torch_threads'])
        self.current = {**request, **settings, 'applied_at': datetime.now(timezone.utc).isoformat(),
                        'applied_after_batch': batch, 'effective_minibatch': config.get('effective_minibatch', 64),
                        'intentional_pause_seconds': 0}
        if isinstance(getattr(pool, 'processes', None), list):
            self.current['worker_pids'] = [p.pid for p in pool.processes]
        return pool, True

    def progress_fields(self):
        return {'resource_settings': self.current}
