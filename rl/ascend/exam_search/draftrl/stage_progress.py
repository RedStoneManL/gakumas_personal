"""One shared, process-local view of the stage the trainer is running right now.

The run heartbeat printed only `decisions=N`, a counter that stays at 0 until the first
PPO update commits, so for the first hour of a batch the log said nothing about where the
work actually was. Every long stage now reports here and publish() renders it, giving a
single line that answers "which stage, how far, how fast, how much longer".

Each learner rank tracks its own shard. publish() runs on rank 0 only, so the numbers
shown are rank 0's shard; shards are equal by construction, so the percentage and ETA
carry over to the job. `shards` is reported so the reader can scale the counts.
"""
import time

_stage = None
_batch = None
_batch_started = None
_finished = []


def begin_batch(batch):
    """Called once per training batch, before its first stage."""
    global _batch, _batch_started, _finished
    _batch, _batch_started, _finished = batch, time.monotonic(), []


def begin(name, total, unit='episodes', shards=1):
    global _stage
    _stage = {'name': name, 'total': total or 0, 'unit': unit, 'shards': shards,
              'done': 0, 'live': 0, 'started': time.monotonic()}


def update(done, live=0):
    if _stage is not None:
        _stage['done'], _stage['live'] = done, live


def end():
    global _stage
    if _stage is not None:
        _finished.append((_stage['name'], (time.monotonic() - _stage['started']) / 60))
        _stage = None


def snapshot():
    """Structured form, written into progress.json for the dashboard."""
    out = {'batch': _batch,
           'batch_minutes': round((time.monotonic() - _batch_started) / 60, 1) if _batch_started else None,
           'finished_stages': [{'stage': n, 'minutes': round(m, 1)} for n, m in _finished]}
    if _stage is None:
        return {**out, 'stage': None}
    elapsed = (time.monotonic() - _stage['started']) / 60
    rate = _stage['done'] / elapsed if elapsed > 0 and _stage['done'] else 0.
    left = _stage['total'] - _stage['done']
    return {**out, 'stage': _stage['name'], 'unit': _stage['unit'], 'shards': _stage['shards'],
            'done': _stage['done'], 'total': _stage['total'], 'live': _stage['live'],
            'percent': round(100. * _stage['done'] / _stage['total'], 1) if _stage['total'] else None,
            'per_minute': round(rate, 1), 'stage_minutes': round(elapsed, 1),
            'eta_minutes': round(left / rate, 1) if rate > 0 and left > 0 else 0.}


def line():
    """Compact clause appended to the human heartbeat line."""
    s = snapshot()
    if s['stage'] is None:
        parts = ['no stage running']
    else:
        shard = f" x{s['shards']} ranks" if s['shards'] > 1 else ''
        parts = [f"{s['stage']} {s['done']}/{s['total']} {s['unit']} {s['percent']}%{shard}",
                 f"{s['per_minute']}/min", f"{s['live']} live",
                 f"stage {s['stage_minutes']:.1f}m", f"eta {s['eta_minutes']:.1f}m"]
    if s['batch_minutes'] is not None:
        parts.append(f"batch {s['batch_minutes']:.1f}m")
    if s['finished_stages']:
        parts.append('done ' + ' '.join(f"{d['stage']}:{d['minutes']:.1f}m" for d in s['finished_stages']))
    return ' | '.join(parts)
