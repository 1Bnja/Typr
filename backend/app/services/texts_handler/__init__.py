"""Public entry point composing the text-processing chain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .context import TextContext
from .processing.classiffy import ClassifyTextStep
from .processing.normalize import NormalizeTextStep
from .processing.validate import ValidateTextStep
from .processing.duplicate import CheckDuplicateTextStep
from .processing.persist import PersistTextStep

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.text_enums import Language
    from .processing.persist import PersistedText


class TextFacade:
    def __init__(self, db: Session | None = None) -> None:
        self.chain = ValidateTextStep()
        self.chain.set_next(NormalizeTextStep()).set_next(ClassifyTextStep())
        self.creation_chain = None
        if db is not None:
            self.creation_chain = ValidateTextStep()
            self.creation_chain.set_next(NormalizeTextStep()).set_next(
                CheckDuplicateTextStep(db)
            ).set_next(ClassifyTextStep()).set_next(PersistTextStep(db))

    def generate(self) -> str:
        """Generate raw text without running either processing chain."""
        from .generator import generate_text

        return generate_text()

    def generate_phrases(self) -> list[str]:
        """Generate ten validated phrases per level, retrying incomplete groups."""
        from app.text_enums import Difficulty

        from .errors import TextValidationError
        from .generator import (
            GROUP_TARGETS,
            capitalize_initial,
            generate_group_text,
            matches_typing_difficulty,
            revise_phrase,
        )

        phrases: list[str] = []
        seen: set[str] = set()
        for difficulty in (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.ADVANCED):
            minimum, maximum, _, _ = GROUP_TARGETS[difficulty]
            group: list[str] = []
            previous_counts: tuple[int, ...] = ()
            repairs_remaining = 12
            for attempt in range(8):
                if len(group) == 10:
                    break
                raw = generate_group_text(
                    difficulty, 10 - len(group), previous_counts,
                    review_quality=attempt == 0,
                )
                observed_counts: list[int] = []
                for line in raw.splitlines():
                    candidate = capitalize_initial(line.strip())
                    if not candidate:
                        continue
                    observed_counts.append(
                        sum(any(char.isalnum() for char in token) for token in candidate.split())
                    )
                    try:
                        context = self.process(candidate, "spa")
                    except TextValidationError:
                        continue
                    if not minimum <= context.classification.word_count <= maximum:
                        if repairs_remaining == 0:
                            continue
                        repairs_remaining -= 1
                        revisions = revise_phrase(
                            difficulty, context.content, context.classification.word_count
                        )
                        for revised in revisions:
                            try:
                                revised_context = self.process(capitalize_initial(revised.strip()), "spa")
                            except TextValidationError:
                                continue
                            if (
                                minimum <= revised_context.classification.word_count <= maximum
                                and revised_context.difficulty == difficulty
                                and matches_typing_difficulty(revised_context.content, difficulty)
                                and revised_context.content not in seen
                            ):
                                context = revised_context
                                break
                        else:
                            continue
                    if (
                        not minimum <= context.classification.word_count <= maximum
                        or context.difficulty != difficulty
                        or not matches_typing_difficulty(context.content, difficulty)
                        or context.content in seen
                    ):
                        continue
                    seen.add(context.content)
                    group.append(context.content)
                    if len(group) == 10:
                        break
                previous_counts = tuple(observed_counts)
            if len(group) != 10:
                raise RuntimeError(
                    f"Could not generate ten valid {difficulty.value} phrases."
                )
            phrases.extend(group)
        return phrases

    def process(self, content: str, language: Language | str) -> TextContext:
        """Validate, normalize and classify without accessing the database."""
        context = TextContext(content, language)
        self.chain.handle(context)
        return context

    def create(self, content: str, language: Language | str) -> PersistedText:
        if self.creation_chain is None:
            raise RuntimeError("Text creation requires an injected database session.")
        context = TextContext(content, language)
        self.creation_chain.handle(context)
        if context.persisted_text is None:
            raise RuntimeError("Text creation did not produce a persisted result.")
        return context.persisted_text

    def update(self) -> None:
        pass
