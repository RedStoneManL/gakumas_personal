"""Parallel collection, isolated task runs, and safe-boundary resume."""

from .config import RunConfig
from .trainer import Trainer

__all__ = ["RunConfig", "Trainer"]
