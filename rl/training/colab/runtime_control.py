"""Read user performance edits at learner safe boundaries, without changing identity."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from persistence import atomic_json


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate control field: {key}')
        result[key] = value
    return result


class RuntimeControl:
    def __init__(self, persistent_run):
        persistent_run = Path(persistent_run)
        folder = persistent_run.parent / '_runtime_controls'
        self.path = folder / (persistent_run.name + '.json')
        self.status_path = folder / (persistent_run.name + '.status.json')
        self.last_error = None
        self._rejected_digest = None

    def _event(self, trainer, event):
        event = {**event, 'iteration': trainer.iteration,
                 'timestamp': datetime.now(timezone.utc).isoformat()}
        print(json.dumps(event, ensure_ascii=False, allow_nan=False), flush=True)
        path = Path(trainer.output) / 'training' / 'runtime-controls.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')

    def publish_status(self, trainer, *, stage):
        import torch
        status = {'stage': stage, 'iteration': trainer.iteration,
                  'updated_at': datetime.now(timezone.utc).isoformat(),
                  'effective': trainer.execution_settings,
                  'pending': trainer.pending_execution_settings,
                  'last_request': dict(getattr(trainer, 'execution_control_state', {})),
                  'effective_inference_batch_size': getattr(trainer.policy_runner, 'effective_inference_batch_size', None),
                  'last_error': self.last_error,
                  'control_path': str(self.path)}
        if torch.cuda.is_available() and str(trainer.config.device).startswith('cuda'):
            free, total = torch.cuda.mem_get_info()
            status['gpu_memory'] = {'free_bytes': free, 'total_bytes': total,
                'allocated_bytes': torch.cuda.memory_allocated(),
                'reserved_bytes': torch.cuda.memory_reserved()}
        try:
            atomic_json(self.status_path, status)
        except OSError as error:
            # A transient Drive mount failure must not erase learner progress.
            print(json.dumps({'event': 'runtime_status_write_failed', 'error': str(error)}), flush=True)
        return status

    def __call__(self, stage, trainer):
        digest = None
        try:
            if self.path.exists():
                if self.path.is_symlink() or self.path.stat().st_size > 16384:
                    raise ValueError('Control must be a small regular JSON file')
                data = self.path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                saved = getattr(trainer, 'execution_control_state', {})
                if digest != saved.get('desired_sha256') and digest != self._rejected_digest:
                    requested = json.loads(data.decode('utf-8-sig'), object_pairs_hook=_unique_pairs)
                    if not isinstance(requested, dict) or not requested:
                        raise ValueError('Control must contain at least one performance field')
                    request_id = requested.pop('_request_id', None)
                    if request_id is not None and (not isinstance(request_id, str) or len(request_id) > 128):
                        raise ValueError('Control request ID must be a short string')
                    if not requested:
                        raise ValueError('Control must contain at least one performance field')
                    trainer.apply_execution_settings(requested, stage=stage)
                    trainer.execution_control_state = {'desired_sha256': digest, 'desired': requested,
                        'request_id': request_id, 'applied_at': datetime.now(timezone.utc).isoformat(), 'stage': stage}
                    self.last_error = self._rejected_digest = None
                    self._event(trainer, {'event': 'runtime_control_applied', 'stage': stage,
                        'requested': requested, 'effective': trainer.execution_settings,
                        'pending': trainer.pending_execution_settings})
        except (ValueError, TypeError, OSError, UnicodeError) as error:
            message = str(error)
            if digest != self._rejected_digest or message != self.last_error:
                self._event(trainer, {'event': 'runtime_control_rejected', 'stage': stage, 'error': message})
            self._rejected_digest, self.last_error = digest, message
        self.publish_status(trainer, stage=stage)
