from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import REAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.enums import GAME_MODE_ENUM, GameMode

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.text import Text
    from app.models.user import User

class Game(Base):
    __tablename__ = "games"
    # Los nombres coinciden con los de init.sql: si no, Alembic genera
    # CREATE INDEX duplicados en el proximo autogenerate.
    __table_args__ = (
        Index("ix_games_room_id", "room_id"),
        Index("ix_games_text_id", "text_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"))
    text_id: Mapped[int] = mapped_column(ForeignKey("texts.id", ondelete="RESTRICT"), nullable=False)
    mode: Mapped[GameMode | None] = mapped_column(GAME_MODE_ENUM, server_default=GameMode.SINGLEPLAYER.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    room: Mapped["Room | None"] = relationship(back_populates="games", foreign_keys=[room_id], passive_deletes="all")
    text: Mapped["Text"] = relationship(back_populates="games", foreign_keys=[text_id], passive_deletes="all")
    participants: Mapped[list["GameParticipant"]] = relationship(back_populates="game", cascade="all, delete-orphan", passive_deletes=True)


class GameParticipant(Base):
    __tablename__ = "game_participants"
    __table_args__ = (
        UniqueConstraint("game_id", "user_id", name="uq_game_participants_game_id_user_id"),
        Index("ix_game_participants_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    time_ms: Mapped[int | None] = mapped_column(Integer)
    ppm: Mapped[int | None] = mapped_column(Integer)
    precision_pct: Mapped[float | None] = mapped_column(REAL)
    progress: Mapped[float | None] = mapped_column(REAL)
    position: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int | None] = mapped_column(Integer)
    game: Mapped["Game"] = relationship(back_populates="participants", foreign_keys=[game_id])
    user: Mapped["User"] = relationship(back_populates="participations", foreign_keys=[user_id])
