"""Terminal database-writing stage, using a caller-owned session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from app.text_enums import Difficulty, Language

from . import TextProcessingStep
from ..errors import TextDatabaseError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from ..context import TextContext


INSERT_SQL = """
INSERT INTO texts (content, language, difficulty, ideal_time_ms, record_user_id)
VALUES (
    %(content)s,
    CAST(%(language)s AS text_language),
    CAST(%(difficulty)s AS difficulty),
    NULL,
    NULL
)
RETURNING id, content, language, difficulty, ideal_time_ms, record_user_id
"""


@dataclass(frozen=True)
class PersistedText:
    """Detached snapshot returned by INSERT, not an ORM-managed entity."""

    id: int
    content: str
    language: Language
    difficulty: Difficulty
    ideal_time_ms: int | None
    record_user_id: int | None


def persisted_text(row: Mapping[str, Any]) -> PersistedText:
    return PersistedText(
        id=row["id"],
        content=row["content"],
        language=Language(row["language"]),
        difficulty=Difficulty(row["difficulty"]),
        ideal_time_ms=row["ideal_time_ms"],
        record_user_id=row["record_user_id"],
    )


class PersistTextStep(TextProcessingStep):
    def __init__(self, db: Session) -> None:
        super().__init__()
        self.db = db

    def handle(self, context: TextContext) -> None:
        context.require_duplicate_checked(self.db)
        context.require_classified()
        try:
            from app.database import execute_sql

            row = (
                execute_sql(
                    self.db,
                    INSERT_SQL,
                    {
                        "content": context.content,
                        "language": Language(context.language).value,
                        "difficulty": context.difficulty.value,
                    },
                )
                .mappings()
                .one()
            )
            text = persisted_text(row)
            self.db.commit()
        except Exception as error:
            try:
                self.db.rollback()
            except Exception:
                error.add_note("Database rollback also failed.")
            raise TextDatabaseError("write") from error
        context.persisted_text = text
        # Persistence is terminal: never run fallible downstream work after commit.
