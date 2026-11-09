"""Check canonical content without loading the complete text catalogue."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import TextProcessingStep
from ..errors import TextDatabaseError, TextValidationError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from ..context import TextContext


DUPLICATE_SQL = """
SELECT id
FROM texts
WHERE content = %(content)s
LIMIT 1
"""


class CheckDuplicateTextStep(TextProcessingStep):
    def __init__(self, db: Session) -> None:
        super().__init__()
        self.db = db

    def handle(self, context: TextContext) -> None:
        context.require_normalized()
        try:
            from app.database import execute_sql

            existing = execute_sql(
                self.db, DUPLICATE_SQL, {"content": context.content}
            ).scalar()
        except Exception as error:
            try:
                self.db.rollback()
            except Exception:
                error.add_note("Database rollback also failed.")
            raise TextDatabaseError("lookup") from error
        if existing is not None:
            raise TextValidationError(
                "duplicate_content", "Text content already exists."
            )
        context.record_duplicate_check(self.db)
        self.forward(context)
