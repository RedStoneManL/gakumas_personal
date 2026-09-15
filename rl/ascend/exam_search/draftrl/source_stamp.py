"""Fresh equivalent Arena source checks using one directory scan per request.

No timed cache or skipped version gate. Native code and public API stay frozen;
this RL-side implementation is covered by the RL source fingerprint.
"""
import os
from pathlib import Path


def fresh_stamp(packages, extras):
    js, data = [], []
    def walk(directory):
        with os.scandir(directory) as entries:
            for item in entries:
                path = Path(item.path)
                # Match pathlib glob case handling on each host.
                suffix = os.path.normcase(path.suffix)
                if suffix in ('.js', '.json'):
                    info = item.stat()
                    (js if suffix == '.js' else data).append((path, info.st_mtime_ns, info.st_size))
                if item.is_dir(follow_symlinks=False):
                    walk(path)
    walk(packages)
    native = sorted(js, key=lambda row: row[0]) + sorted(data, key=lambda row: row[0])
    result = [(str(path), mtime, size) for path, mtime, size in native]
    for path in extras:
        info = path.stat()
        result.append((str(path), info.st_mtime_ns, info.st_size))
    return tuple(result)


def install():
    from gakumas_arena.engine import search, training
    if getattr(search._source_stamp, '_rl_fresh_scan', False):
        return
    original = search._source_stamp
    packages = training.VENDOR / 'packages'
    # The explicit adapter list belongs to this already-loaded Python module.
    # Changes to that module itself remain among the checked source files.
    extras = tuple(p for p in training._effective_paths() if not p.is_relative_to(packages))
    def stamp():
        try:
            return fresh_stamp(packages, extras)
        except OSError:
            # Retain Arena's failure behavior for an unreadable/missing tree.
            return original()
    if original() != stamp():
        raise RuntimeError('Fresh source scan differs from the frozen Arena stamp')
    stamp._rl_fresh_scan = True
    search._source_stamp = stamp
