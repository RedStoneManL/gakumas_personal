"""Locate the independent Arena dependency and identify effective source data."""
from __future__ import annotations
from functools import lru_cache
import hashlib
import importlib
import json
from pathlib import Path
import sys


def ensure_arena(arena_root=None):
    explicit = arena_root is not None
    if arena_root is None:
        arena_root = Path(__file__).resolve().parents[4] / 'third_party' / 'gakumas_arena'
    arena_root = Path(arena_root).resolve()
    if explicit and not (arena_root / 'gakumas_arena').is_dir():
        raise FileNotFoundError(f'Explicit Arena root does not contain gakumas_arena: {arena_root}')
    if (arena_root / 'gakumas_arena').is_dir():
        path = str(arena_root)
        if path not in sys.path:
            sys.path.insert(0, path)
    module = importlib.import_module('gakumas_arena')
    actual = Path(module.__file__).resolve().parents[1]
    if (arena_root / 'gakumas_arena').is_dir() and actual != arena_root:
        raise RuntimeError(f'Arena already imported from a different checkout: {actual}')
    return actual


@lru_cache(maxsize=2)
def arena_version(arena_root):
    from gakumas_arena.engine.training import content_version
    from gakumas_arena.env import get_repository
    root = Path(arena_root)
    native = content_version()
    return {'hash_schema': 'arena-effective-rules-and-master/2',
            'native_sha256': native['effective_sha256'], 'public_schema': native['public_schema'],
            'produce_master_sha256': _produce_rules_digest(root, get_repository().assets_dir)}


def _produce_rules_digest(root, assets_dir):
    """Logical relative keys preserve hashes when the identical bundle moves.

    Native JS/JSON are covered by TrainingExam.content_version. Include every
    Python rule, scoring data, scenario, and packaged runtime config here, plus
    the actual selected master directory rather than an unused default path.
    """
    root, assets_dir = Path(root), Path(assets_dir)
    files = {}
    for folder, pattern in (('gakumas_arena', '*.py'), ('gakumas_rl', '*.py'),
                            ('gakumas_arena/produce/data', '*.json'),
                            ('gakumas_arena/scoring', '*.json'),
                            ('gakumas_arena/content', '*.json'),
                            ('gakumas_arena/scenarios', '*.yaml'),
                            ('gakumas_rl/configs', '*.json')):
        for path in sorted((root / folder).rglob(pattern)):
            files['package/' + path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(assets_dir.rglob('*.yaml')):
        files['master/' + path.relative_to(assets_dir).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def close_arena():
    from gakumas_arena.engine.training import close_training_worker
    close_training_worker()
