"""Public entry point composing the text-processing chain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .context import TextContext
from .handler.classiffy import ClassifyTextHandler
from .handler.normalize import NormalizeTextHandler
from .handler.validate import ValidateTextHandler
from .handler.duplicate import CheckDuplicateTextHandler
from .handler.persist import PersistTextHandler

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.text_enums import Language
    from .handler.persist import PersistedText


class TextFacade:
    def __init__(self, db: Session | None = None) -> None:
        self.chain = ValidateTextHandler()
        self.chain.set_next(NormalizeTextHandler()).set_next(ClassifyTextHandler())
        self.creation_chain = None
        if db is not None:
            self.creation_chain = ValidateTextHandler()
            self.creation_chain.set_next(NormalizeTextHandler()).set_next(
                CheckDuplicateTextHandler(db)
            ).set_next(ClassifyTextHandler()).set_next(PersistTextHandler(db))

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
