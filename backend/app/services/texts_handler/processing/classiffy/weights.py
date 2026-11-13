"""Editable constants for the initial deterministic classification model."""

from types import MappingProxyType

VERSION = "text-difficulty-v2"
# Three bands for newly classified phrases. The database retains its legacy
# 'expert' enum value for existing rows and game compatibility.
THRESHOLDS = (38, 52)
MEAN_WORD_LENGTH_SCALE = 12
MAX_WORD_LENGTH_SCALE = 24
LENGTH_SCORE_CEILING = 150
SCORE_SCALE = 100
WEIGHTS = MappingProxyType(
    {
        "entropy": 0.24,
        "effort": 0.22,
        "mean_length": 0.12,
        "variety": 0.08,
        "max_length": 0.08,
        "length": 0.20,
        "symbols": 0.06,
    }
)
