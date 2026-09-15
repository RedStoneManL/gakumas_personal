"""A small, auditable user control surface for training time, not hyperparameters."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = 'arena-training-window/1'


def aware_datetime(value, name='absolute_deadline'):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be an ISO datetime with a timezone')
    try:
        result = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f'{name} must be an ISO datetime with a timezone') from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f'{name} must include a timezone')
    return result


def positive_minutes(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('max_minutes must be finite and positive')
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError('max_minutes must be finite and positive')
    return result


class RuntimeWindow:
    """Read an atomically replaced per-run file only at safe batch boundaries.

    The duration still measures from the original run start. Changing this file
    does not reset elapsed time, exploration, policy weights, or random state.
    An invalid existing file raises instead of silently reverting its deadline.
    """

    def __init__(self, output, config):
        self.path = Path(output) / 'training-window.json'
        self.original = {
            'absolute_deadline': config.get('absolute_deadline'),
            'max_minutes': config['max_minutes'],
        }
        self.source_sha256 = None
        self.source = None
        self.deadline = None
        self.max_minutes = 0.0
        self.refresh()

    def refresh(self):
        try:
            payload = self.path.read_bytes()
        except FileNotFoundError:
            data = self.original
            source = 'original-config'
            payload = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
        else:
            try:
                data = json.loads(payload.decode('utf-8-sig'))
            except (ValueError, UnicodeError) as error:
                raise ValueError('Invalid training-window.json') from error
            if not isinstance(data, dict) or data.get('schema') != SCHEMA:
                raise ValueError(f'training-window.json requires schema {SCHEMA}')
            if data.get('absolute_deadline') is None or 'max_minutes' not in data:
                raise ValueError('training-window.json requires both absolute_deadline and max_minutes')
            source = str(self.path.resolve())
        fingerprint = hashlib.sha256(payload).hexdigest()
        if (source, fingerprint) == (self.source, self.source_sha256):
            return False
        deadline = aware_datetime(data['absolute_deadline']) if data.get('absolute_deadline') is not None else None
        minutes = positive_minutes(data['max_minutes'])
        self.deadline, self.max_minutes = deadline, minutes
        self.source, self.source_sha256 = source, fingerprint
        return True

    def allows(self, elapsed_minutes, *, now=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('Current time must include a timezone')
        return (elapsed_minutes < self.max_minutes and
                (self.deadline is None or now < self.deadline))

    def progress_fields(self):
        return {
            'effective_absolute_deadline': self.deadline.isoformat() if self.deadline else None,
            'effective_max_minutes': self.max_minutes,
            'max_minutes': self.max_minutes,
            'training_window_source': self.source,
            'training_window_source_sha256': self.source_sha256,
        }
