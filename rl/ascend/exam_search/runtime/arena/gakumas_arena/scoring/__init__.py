"""Versioned pre-exam scoring providers; card execution stays in the golden engine."""

from .hif import calculate_hif_multiplier, resolve_hif_produce_scoring

__all__ = ['calculate_hif_multiplier', 'resolve_hif_produce_scoring']
