"""Manual text loading through the existing processing facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Literal

from app.text_enums import Difficulty, Language

from . import TextFacade
from .errors import TextDatabaseError, TextValidationError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class LoadedPhrase:
    content: str
    status: Literal["stored", "duplicate", "rejected", "valid"]
    difficulty: Difficulty | None = None
    id: int | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class LoadSummary:
    generated: int
    stored: int
    duplicates: int
    rejected: int
    accepted_in_dry_run: int
    phrases: tuple[LoadedPhrase, ...] = ()


def load_phrases(
    phrases: Iterable[str],
    language: Language | str,
    *,
    dry_run: bool,
    db: Session | None = None,
    max_per_difficulty: int | None = None,
) -> LoadSummary:
    """Validate every phrase; only actual writes require a database session."""
    selected = Language(language)
    if not dry_run and db is None:
        raise ValueError("A database session is required unless dry_run is enabled.")
    if max_per_difficulty is not None and max_per_difficulty < 1:
        raise ValueError("The difficulty limit must be positive.")
    preview = TextFacade()
    creator = TextFacade(db) if db is not None and not dry_run else None
    seen: set[str] = set()
    accepted_by_difficulty: dict[Difficulty, int] = {}
    generated = stored = duplicates = rejected = accepted_in_dry_run = 0
    results: list[LoadedPhrase] = []

    for phrase in phrases:
        generated += 1
        try:
            context = preview.process(phrase, selected)
        except TextValidationError as error:
            rejected += 1
            results.append(LoadedPhrase(phrase, "rejected", reason_code=error.code))
            continue
        if context.content in seen:
            duplicates += 1
            results.append(LoadedPhrase(context.content, "duplicate", context.difficulty))
            continue
        seen.add(context.content)
        if (
            max_per_difficulty is not None
            and accepted_by_difficulty.get(context.difficulty, 0) >= max_per_difficulty
        ):
            rejected += 1
            results.append(
                LoadedPhrase(
                    context.content,
                    "rejected",
                    context.difficulty,
                    reason_code="difficulty_quota",
                )
            )
            continue
        if dry_run:
            accepted_in_dry_run += 1
            accepted_by_difficulty[context.difficulty] = (
                accepted_by_difficulty.get(context.difficulty, 0) + 1
            )
            results.append(LoadedPhrase(context.content, "valid", context.difficulty))
            continue
        try:
            assert creator is not None
            saved = creator.create(phrase, selected)
        except TextValidationError as error:
            if error.code == "duplicate_content":
                duplicates += 1
                results.append(LoadedPhrase(context.content, "duplicate", context.difficulty))
            else:
                rejected += 1
                results.append(
                    LoadedPhrase(context.content, "rejected", reason_code=error.code)
                )
        except TextDatabaseError as error:
            error.add_note(
                f"Load stopped at phrase {generated}; {stored} phrases were already stored."
            )
            raise
        else:
            stored += 1
            accepted_by_difficulty[saved.difficulty] = (
                accepted_by_difficulty.get(saved.difficulty, 0) + 1
            )
            results.append(
                LoadedPhrase(saved.content, "stored", saved.difficulty, saved.id)
            )
    return LoadSummary(
        generated, stored, duplicates, rejected, accepted_in_dry_run, tuple(results)
    )
