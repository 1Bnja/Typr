from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

from .errors import TextValidationError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.text_enums import Difficulty, Language
    from .processing.classiffy import ClassificationResult
    from .processing.persist import PersistedText


class TextContext:
    def __init__(self, content: str, language: Language | str) -> None:
        self.content = content
        self.language = language
        self.difficulty: Difficulty | None = None
        self.classification: ClassificationResult | None = None
        self._validated_input: tuple[str, str] | None = None
        self._normalized_input: tuple[str, str] | None = None
        self._quote_roles: Mapping[int, str] = MappingProxyType({})
        self._duplicate_input: tuple[str, str] | None = None
        self._duplicate_session: Session | None = None
        self._classified_input: tuple[str, str] | None = None
        self.persisted_text: PersistedText | None = None

    def record_validation(self, quote_roles: Mapping[int, str]) -> None:
        self._validated_input = (self.content, self.language)
        self._normalized_input = None
        self._quote_roles = MappingProxyType(dict(quote_roles))
        self.difficulty = self.classification = None
        self._duplicate_input = self._classified_input = None
        self._duplicate_session = None
        self.persisted_text = None

    def require_validated(self) -> Mapping[int, str]:
        if self._validated_input != (self.content, self.language):
            raise TextValidationError(
                "not_validated", "Validate the current input before normalization."
            )
        return self._quote_roles

    def record_normalization(self, content: str) -> None:
        self.require_validated()
        self.content = content
        self._normalized_input = (content, self.language)
        self.difficulty = self.classification = None
        self._duplicate_input = self._classified_input = None
        self._duplicate_session = None
        self.persisted_text = None

    def require_normalized(self) -> None:
        if self._normalized_input != (self.content, self.language):
            raise TextValidationError(
                "not_normalized", "Normalize the current input before classification."
            )

    def record_duplicate_check(self, db: Session) -> None:
        self.require_normalized()
        self._duplicate_input = (self.content, self.language)
        self._duplicate_session = db

    def require_duplicate_checked(self, db: Session) -> None:
        self.require_normalized()
        if (
            self._duplicate_input != (self.content, self.language)
            or self._duplicate_session is not db
        ):
            raise TextValidationError(
                "duplicate_check_required", "Check duplicates before persistence."
            )

    def record_classification(self, result: ClassificationResult) -> None:
        self.require_normalized()
        self.classification = result
        self.difficulty = result.difficulty
        self._classified_input = (self.content, self.language)
        self.persisted_text = None

    def require_classified(self) -> None:
        self.require_normalized()
        if self.persisted_text is not None:
            raise TextValidationError(
                "already_persisted", "The current context has already been persisted."
            )
        if (
            self._classified_input != (self.content, self.language)
            or self.classification is None
            or self.difficulty != self.classification.difficulty
        ):
            raise TextValidationError(
                "not_classified", "Classify the current input before persistence."
            )
