from __future__ import annotations

from typing import TYPE_CHECKING

from app.text_constants import MAX_CONTENT_LENGTH

from . import TextProcessingStep
from ..errors import TextValidationError
from ..characters import ALLOWED_CHARACTERS, LETTERS_AND_DIGITS

if TYPE_CHECKING:
    from ..context import TextContext


def quote_roles(content: str, language: str) -> dict[int, str]:
    """Validate single quotes before their direction is normalized away."""
    roles = {}
    opened = None
    for index, char in enumerate(content):
        if char not in "'‘’":
            continue
        internal = (
            index > 0
            and index + 1 < len(content)
            and content[index - 1] in LETTERS_AND_DIGITS
            and content[index + 1] in LETTERS_AND_DIGITS
        )
        if internal:
            if language == "eng" and char == "'":
                roles[index] = "join"
                continue
            raise TextValidationError(
                "invalid_apostrophe", "Apostrophe inside a word is not allowed."
            )
        if opened is None:
            if char == "’":
                raise TextValidationError(
                    "unpaired_quote", "Closing quote has no opening quote."
                )
            opened = char
            roles[index] = "open"
        else:
            expected = "’" if opened == "‘" else "'"
            if char != expected:
                raise TextValidationError(
                    "unpaired_quote", "Single quote styles do not match."
                )
            opened = None
            roles[index] = "close"
    if opened is not None:
        raise TextValidationError(
            "unpaired_quote", "Single quoted block is not closed."
        )
    return roles


def validate_content(content: str, language: str) -> dict[int, str]:
    """Check raw input without importing ORM models or database settings."""
    if not isinstance(language, str) or language not in ALLOWED_CHARACTERS:
        raise TextValidationError(
            "unsupported_language", "Language must be spa or eng."
        )
    if not isinstance(content, str):
        raise TextValidationError("invalid_content", "Content must be a string.")
    if not content or not content.strip(" \t\r\n"):
        raise TextValidationError("empty_content", "Content must not be empty.")
    if len(content) > MAX_CONTENT_LENGTH:
        raise TextValidationError(
            "content_too_long", "Content exceeds the maximum length."
        )
    if not ALLOWED_CHARACTERS[language].issuperset(content):
        raise TextValidationError(
            "invalid_character", "Content contains an unsupported character."
        )
    return quote_roles(content, language)


class ValidateTextStep(TextProcessingStep):
    def handle(self, context: TextContext) -> None:
        roles = validate_content(context.content, context.language)
        context.record_validation(roles)
        self.forward(context)
