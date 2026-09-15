"""Batch-boundary scale requests for the explicitly selected portable run."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock
from uuid import uuid4
from generalist_data import alive, read_json

FIELDS = ('workers', 'parallel_roots', 'inference_batch', 'microbatch', 'torch_threads')
LOCK = RLock()


def state(run):
    run = Path(run).resolve()
    config = read_json(run/'manifest.json').get('config', {})
    progress = read_json(run/'progress.json')
    return {'run_id': run.name,
            'enabled': config.get('resource_mode') == 'cluster' and progress.get('status') == 'running'
                       and alive(progress.get('trainer_pid')) is True,
            'actual': progress.get('resource_settings') or {},
            'requested': read_json(run/'resource-mode.json'),
            'configured': config.get('parallelism', {}),
            'effective_minibatch': config.get('effective_minibatch'),
            'error': progress.get('resource_request_error'),
            'fields': list(FIELDS), 'options': [{'mode': 'cluster'}]}


def request(run, value):
    if not isinstance(value, dict) or set(value) != {'run_id', 'parallelism'}:
        raise ValueError('Expected run_id and parallelism')
    settings = value['parallelism']
    if (not isinstance(settings, dict) or set(settings) != set(FIELDS)
            or any(type(n) is not int or n < 1 for n in settings.values())):
        raise ValueError('Every scale setting must be a positive integer')
    run = Path(run).resolve()
    with LOCK:
        current = state(run)
        if value['run_id'] != current['run_id'] or not current['enabled']:
            raise ValueError('Selected run is not running or does not accept cluster resource changes')
        if settings['microbatch'] > current['effective_minibatch']:
            raise ValueError('Microbatch must fit the configured effective minibatch')
        request = {'schema': 'arena-resource-mode/1', 'mode': 'cluster',
                   'request_id': str(uuid4()), 'requested_at': datetime.now(timezone.utc).isoformat(),
                   'parallelism': settings, 'reason': 'User requested parallelism from the local dashboard'}
        temporary = run/('resource-mode.'+request['request_id']+'.tmp')
        temporary.write_text(json.dumps(request)+'\n', encoding='utf-8', newline='\n')
        os.replace(temporary, run/'resource-mode.json')
        return state(run)
