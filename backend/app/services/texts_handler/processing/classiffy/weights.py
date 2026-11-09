"""Editable constants for the initial deterministic classification model."""

from types import MappingProxyType

VERSION = "text-difficulty-v1"
THRESHOLDS = (25, 50, 75)
MEAN_WORD_LENGTH_SCALE = 12
MAX_WORD_LENGTH_SCALE = 24
SCORE_SCALE = 100
WEIGHTS = MappingProxyType(
    {
        "entropy": 0.35,
        "effort": 0.30,
        "mean_length": 0.15,
        "variety": 0.10,
        "max_length": 0.10,
    }
)
