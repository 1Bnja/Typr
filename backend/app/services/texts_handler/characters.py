"""Shared text alphabets; no processing or handler dependencies."""

from string import ascii_letters, digits
from types import MappingProxyType

COMMON_PUNCTUATION = frozenset(".,;:?!'\"()-")
SPANISH_LETTERS = frozenset("ñÑáéíóúÁÉÍÓÚüÜ")
WHITESPACE = frozenset(" \t\r\n")
LETTERS_AND_DIGITS = frozenset(ascii_letters + digits) | SPANISH_LETTERS
BASE_CHARACTERS = COMMON_PUNCTUATION.union(WHITESPACE, ascii_letters + digits + "‘’")
ALLOWED_CHARACTERS = MappingProxyType(
    {
        "eng": BASE_CHARACTERS,
        "spa": BASE_CHARACTERS | SPANISH_LETTERS | frozenset("¿¡"),
    }
)
