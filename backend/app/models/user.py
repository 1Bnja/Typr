from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.game import GameParticipant
    from app.models.room import Room
    from app.models.text import Text


class User(Base):
    """Tabla `users` (ver supabase/db/init.sql)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # username y email ya son UNIQUE en init.sql, asi que Postgres crea su
    # indice: no hace falta `index=True` (seria un indice duplicado).
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(72), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # texts.record_user_id es ON DELETE SET NULL: que lo resuelva Postgres.
    texts: Mapped[list["Text"]] = relationship(
        back_populates="record_user", passive_deletes="all"
    )
    # rooms.host_id es ON DELETE CASCADE.
    rooms: Mapped[list["Room"]] = relationship(
        back_populates="host", foreign_keys="Room.host_id", passive_deletes="all"
    )
    # game_participants.user_id es ON DELETE CASCADE y aca si queremos el
    # delete-orphan, para que borrar un usuario desde el ORM limpie sus filas.
    participations: Mapped[list["GameParticipant"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
