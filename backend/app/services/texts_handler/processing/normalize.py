from __future__ import annotations

from string import digits
from typing import TYPE_CHECKING

from . import TextProcessingStep
from app.text_constants import MAX_CONTENT_LENGTH

from ..characters import WHITESPACE
from ..errors import TextValidationError

if TYPE_CHECKING:
    from ..context import TextContext


def normalize_content(context: TextContext) -> str:
    """Canonicalize spacing while preserving decimals and quote boundaries."""
    quotes = context.require_validated()
    content = context.content
    result = []
    previous = None
    double_open = False
    characters = ((i, c) for i, c in enumerate(content) if c not in WHITESPACE)
    for index, char in characters:
        if char in "'‘’":
            role = quotes[index]
            char = "'"
        elif char == '"':
            role = "close" if double_open else "open"
            double_open = not double_open
        elif char in "(¿¡":
            role = "open"
        elif char == ")":
            role = "close"
        elif char in ".," and (
            index > 0
            and index + 1 < len(content)
            and content[index - 1] in digits
            and content[index + 1] in digits
        ):
            role = "join"
        elif char == "-":
            role = "hyphen"
        elif char in ".,;:?!":
            role = "punctuation"
        else:
            role = "word"
        no_space = previous in ("open", "join") or role in (
            "close",
            "punctuation",
            "join",
        )
        required_space = (
            previous in ("close", "punctuation")
            and role in ("word", "open")
            or previous == "word"
            and role == "open"
        )
        had_space = index > 0 and content[index - 1] in WHITESPACE
        if result and not no_space and (had_space or required_space):
            result.append(" ")
        result.append(char)
        previous = role
    normalized = "".join(result)
    if len(normalized) > MAX_CONTENT_LENGTH:
        raise TextValidationError(
            "content_too_long", "Content exceeds the maximum length."
        )
    return normalized


class NormalizeTextStep(TextProcessingStep):
    def handle(self, context: TextContext) -> None:
        normalized = normalize_content(context)
        context.record_normalization(normalized)
        self.forward(context)
