"""Fixed-depth classification stages; no persistence or external dependencies."""

from __future__ import annotations

from collections import Counter
from bisect import bisect_right
from dataclasses import dataclass, field
from math import log2
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

from app.text_enums import Difficulty

from .. import TextHandler
from .keyboard import keyboard
from .weights import (
    MAX_WORD_LENGTH_SCALE,
    MEAN_WORD_LENGTH_SCALE,
    SCORE_SCALE,
    THRESHOLDS,
    VERSION,
    WEIGHTS,
)

if TYPE_CHECKING:
    from ...context import TextContext

LEVELS = tuple(Difficulty)


@dataclass(frozen=True)
class ClassificationResult:
    version: str
    nonspace_characters: int
    unique_characters: int
    word_count: int
    entropy_bits: float
    mean_word_length: float
    max_word_length: int
    mean_key_cost: float
    normalized: Mapping[str, float]
    contributions: Mapping[str, float]
    score: float
    difficulty: Difficulty


@dataclass
class _Measurements:
    content: str
    language: str
    symbols: str = ""
    unique_characters: int = 0
    entropy_bits: float = 0
    word_count: int = 0
    mean_word_length: float = 0
    max_word_length: int = 0
    mean_key_cost: float = 0
    normalized: dict[str, float] = field(default_factory=dict)


def difficulty_for_score(score: float) -> Difficulty:
    """Apply exact half-open score bands without rounding."""
    return LEVELS[bisect_right(THRESHOLDS, score)]


def classify_text(context: TextContext) -> ClassificationResult:
    """Measure the current normalized context without replaying earlier stages."""
    context.require_normalized()
    return _prepare(_Measurements(context.content, context.language))


def _prepare(values: _Measurements) -> ClassificationResult:
    values.symbols = values.content.replace(" ", "")
    return _measure_characters(values)


def _measure_characters(values: _Measurements) -> ClassificationResult:
    counts = Counter(values.symbols)
    size = len(values.symbols)
    values.unique_characters = len(counts)
    values.entropy_bits = -sum(
        (count / size) * log2(count / size) for count in counts.values()
    )
    return _measure_words(values)


def _measure_words(values: _Measurements) -> ClassificationResult:
    # Retain the calibration assumption: whitespace tokens; letters/digits only.
    # Numeric tokens and internal hyphens are not a general linguistic tokenizer.
    lengths = list(
        filter(None, (sum(map(str.isalnum, token)) for token in values.content.split()))
    )
    values.word_count = len(lengths)
    values.mean_word_length = sum(lengths) / len(lengths) if lengths else 0
    values.max_word_length = max(lengths, default=0)
    return _measure_keyboard(values)


def _measure_keyboard(values: _Measurements) -> ClassificationResult:
    layout = keyboard(values.language)
    values.mean_key_cost = sum(map(layout.costs.__getitem__, values.symbols)) / len(
        values.symbols
    )
    return _normalize_metrics(values)


def _normalize_metrics(values: _Measurements) -> ClassificationResult:
    layout = keyboard(values.language)
    alphabet_size = len(layout.sequences)
    values.normalized = {
        "entropy": values.entropy_bits / log2(alphabet_size),
        "effort": values.mean_key_cost / layout.maximum_cost,
        "mean_length": min(values.mean_word_length / MEAN_WORD_LENGTH_SCALE, 1),
        "variety": values.unique_characters / alphabet_size,
        "max_length": min(values.max_word_length / MAX_WORD_LENGTH_SCALE, 1),
    }
    return _score(values)


def _score(values: _Measurements) -> ClassificationResult:
    contributions = {
        name: SCORE_SCALE * WEIGHTS[name] * value
        for name, value in values.normalized.items()
    }
    score = sum(contributions.values())
    return ClassificationResult(
        version=VERSION,
        nonspace_characters=len(values.symbols),
        unique_characters=values.unique_characters,
        word_count=values.word_count,
        entropy_bits=values.entropy_bits,
        mean_word_length=values.mean_word_length,
        max_word_length=values.max_word_length,
        mean_key_cost=values.mean_key_cost,
        normalized=MappingProxyType(values.normalized),
        contributions=MappingProxyType(contributions),
        score=score,
        difficulty=difficulty_for_score(score),
    )


class ClassifyTextHandler(TextHandler):
    def handle(self, context: TextContext) -> None:
        result = classify_text(context)
        context.record_classification(result)
        self.forward(context)
