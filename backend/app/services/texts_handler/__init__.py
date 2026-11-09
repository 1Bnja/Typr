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
