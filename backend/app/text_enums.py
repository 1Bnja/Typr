"""Text domain values independent of ORM and database configuration."""

from enum import Enum


class Language(str, Enum):
    SPA = "spa"
    ENG = "eng"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    ADVANCED = "advanced"
    EXPERT = "expert"
