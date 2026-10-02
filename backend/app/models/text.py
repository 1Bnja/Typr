from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text as SQLText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import DIFFICULTY_ENUM, LANGUAGE_ENUM, Difficulty, Language

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.user import User


class Text(Base):
    """Tabla `texts`: el texto que se tipea y su metadata."""

    __tablename__ = "texts"
    __table_args__ = (
        # El nombre coincide con el de init.sql: si no, Alembic genera un
        # CREATE INDEX duplicado en el proximo autogenerate.
        Index("ix_texts_language_difficulty", "language", "difficulty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(SQLText, nullable=False)
    language: Mapped[Language] = mapped_column(LANGUAGE_ENUM, nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(DIFFICULTY_ENUM, nullable=False)
    # Tiempo ideal de tipeo en ms. Nullable en el esquema.
    ideal_time_ms: Mapped[int | None] = mapped_column(Integer)
    # Mejor tiempo historico sobre este texto. Nullable con ON DELETE SET NULL,
    # por eso el tipo es int | None (el modelo previo lo tenia como NOT NULL).
    record_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    record_user: Mapped["User | None"] = relationship(
        back_populates="texts",
        foreign_keys=[record_user_id],
        passive_deletes="all",
    )
    # games.text_id es ON DELETE RESTRICT: Postgres impide borrar un texto que
    # ya tiene partidas, asi que el ORM no debe intentar nullificarlas.
    games: Mapped[list["Game"]] = relationship(
        back_populates="text", passive_deletes="all"
    )
