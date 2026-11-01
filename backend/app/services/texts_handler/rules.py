"""Shared phrase constraints used before and after normalization."""

import re

from .errors import TextValidationError

MIN_PHRASE_LENGTH = 40
MAX_PHRASE_LENGTH = 250
MIN_WORDS = 5


def check_phrase_size(content: str) -> None:
    if len(content) < MIN_PHRASE_LENGTH:
        raise TextValidationError("content_too_short", "Phrase must contain at least 40 characters.")
    if len(content) > MAX_PHRASE_LENGTH:
        raise TextValidationError("content_too_long", "Phrase must contain at most 250 characters.")
    # Punctuation can adjoin words before NormalizeTextStep inserts spaces.
    words = re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)*", content)
    if len(words) < MIN_WORDS:
        raise TextValidationError("too_few_words", "Phrase must contain at least five words.")
