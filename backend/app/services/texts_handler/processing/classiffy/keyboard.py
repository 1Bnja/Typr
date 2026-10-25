"""Fixed US and Latin American keyboard model for text-difficulty-v1."""

from dataclasses import dataclass
from functools import cache
from math import dist
from string import ascii_letters, digits
from types import MappingProxyType
from typing import Mapping

from ...errors import TextValidationError
from ...characters import COMMON_PUNCTUATION, SPANISH_LETTERS

Press = tuple[str, bool]
Sequence = tuple[Press, ...]
ROWS = {"AE": (0.0, 0.0), "AD": (1.0, 0.25), "AC": (2.0, 0.5), "AB": (3.0, 1.0)}
HOME_COLUMNS = (0, 1, 2, 3, 4, 4, 7, 7, 8, 9, 10, 10, 10)
PUNCTUATION_KEYS = {
    "eng": {
        ".": ("AB09", False),
        ",": ("AB08", False),
        ";": ("AC10", False),
        ":": ("AC10", True),
        "?": ("AB10", True),
        "!": ("AE01", True),
        "'": ("AC11", False),
        '"': ("AC11", True),
        "(": ("AE09", True),
        ")": ("AE10", True),
        "-": ("AE11", False),
    },
    "spa": {
        ".": ("AB09", False),
        ",": ("AB08", False),
        ";": ("AB08", True),
        ":": ("AB09", True),
        "¿": ("AE12", False),
        "?": ("AE11", True),
        "¡": ("AE12", True),
        "!": ("AE01", True),
        "'": ("AE11", False),
        '"': ("AE02", True),
        "(": ("AE08", True),
        ")": ("AE09", True),
        "-": ("AB10", False),
    },
}


@dataclass(frozen=True)
class Keyboard:
    sequences: Mapping[str, Sequence]
    costs: Mapping[str, float]
    maximum_cost: float


def _position(key: str) -> tuple[float, float]:
    y, offset = ROWS[key[:2]]
    return int(key[2:]) - 1 + offset, y


def _press_cost(press: Press) -> float:
    key, shifted = press
    home = f"AC{HOME_COLUMNS[int(key[2:])]:02d}"
    return 1 + dist(_position(key), _position(home)) + 0.5 * shifted


@cache
def keyboard(language: str) -> Keyboard:
    """Build immutable maps with exact coverage of the canonical alphabet."""
    if not isinstance(language, str) or language not in PUNCTUATION_KEYS:
        raise TextValidationError(
            "unsupported_language", "Language must be spa or eng."
        )
    sequences = {}
    for row, letters in (("AD", "qwertyuiop"), ("AC", "asdfghjkl"), ("AB", "zxcvbnm")):
        for index, char in enumerate(letters, 1):
            key = f"{row}{index:02d}"
            sequences[char] = ((key, False),)
            sequences[char.upper()] = ((key, True),)
    for index, char in enumerate("1234567890", 1):
        sequences[char] = ((f"AE{index:02d}", False),)
    sequences.update(
        {char: (press,) for char, press in PUNCTUATION_KEYS[language].items()}
    )
    alphabet = set(ascii_letters + digits) | COMMON_PUNCTUATION
    if language == "spa":
        alphabet |= SPANISH_LETTERS | set("¿¡")
        sequences["ñ"] = (("AC10", False),)
        sequences["Ñ"] = (("AC10", True),)
        for accent, vowel in zip("áéíóúÁÉÍÓÚ", "aeiouAEIOU"):
            sequences[accent] = (("AD11", False),) + sequences[vowel]
        sequences["ü"] = (("AD11", True),) + sequences["u"]
        sequences["Ü"] = (("AD11", True),) + sequences["U"]
    if set(sequences) != alphabet:
        raise RuntimeError("Keyboard map does not cover the canonical alphabet.")
    costs = {
        char: sum(_press_cost(press) for press in sequence)
        for char, sequence in sequences.items()
    }
    return Keyboard(
        MappingProxyType(sequences), MappingProxyType(costs), max(costs.values())
    )
