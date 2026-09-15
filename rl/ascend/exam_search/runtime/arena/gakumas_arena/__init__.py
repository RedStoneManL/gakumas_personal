"""gakumas_arena: local, seeded Gakuen Idolmaster sandbox.

Public training uses ``TrainingExam`` over the pinned gakumas-tools golden;
``ArenaExam`` is the private debug interface.
The existing gakumas_rl produce/Gym/live interfaces remain compatibility paths:

- ``gakumas_arena.masterdata`` - our own loader over the datamined master-data dump
- ``gakumas_arena.env``        - ``make_exam_env`` / ``make_produce_env`` (Gymnasium envs)
- ``gakumas_arena.sim``        - ``run_exam`` / ``run_produce`` seeded rollouts with a policy
- ``gakumas_arena.agents``     - tiny baseline policies
"""

__version__ = "0.1.0"

from .engine import DEFAULT_EXAM_BACKEND, RULES_VERSION, ArenaExam
from .engine.training import (
    TrainingExam,
    create_training_exam,
    default_training_entry,
    effect_declaration,
    hif_round2_entry,
    make_training_entry,
)


def create_exam(config, *, seed=610397104, **kwargs):
    """Create an offline Arena exam using the current golden backend."""
    return ArenaExam(config, seed=seed, **kwargs)


__all__ = [
    "DEFAULT_EXAM_BACKEND",
    "RULES_VERSION",
    "ArenaExam",
    "TrainingExam",
    "__version__",
    "create_exam",
    "create_training_exam",
    "default_training_entry",
    "effect_declaration",
    "hif_round2_entry",
    "make_training_entry",
]
