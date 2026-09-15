"""Uniform-random baseline over the env's action mask."""
from __future__ import annotations

import numpy as np


def act(mask: np.ndarray, rng: np.random.Generator) -> int:
    """Pick a uniformly random legal slot from a 0/1 ``action_mask``."""
    return int(rng.choice(np.flatnonzero(np.asarray(mask) > 0.5)))
