from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import DIFFICULTY_ENUM, LANGUAGE_ENUM, ROOM_STATUS_ENUM, ROOM_TYPE_ENUM
from app.models.enums import Difficulty, Language, RoomStatus, RoomType

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.user import User

ROOM_CODE_LENGTH = 6
MAX_ROUNDS = 10
MIN_TIME_LIMIT_S = 30
MAX_TIME_LIMIT_S = 600

room_members = Table(
    "room_members",
    Base.metadata,
    Column("room_id", ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
    Column("member_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("is_ready", Boolean, nullable=False, server_default=false()),
    # Unico: un usuario pertenece a una sola sala a la vez (migracion 0003).
    Index("uq_room_members_member_id", "member_id", unique=True),
)


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        Index("ix_rooms_status", "status"),
        CheckConstraint(f"rounds BETWEEN 1 AND {MAX_ROUNDS}", name="ck_rooms_rounds"),
        CheckConstraint(
            f"time_limit_s BETWEEN {MIN_TIME_LIMIT_S} AND {MAX_TIME_LIMIT_S}",
            name="ck_rooms_time_limit_s",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(ROOM_CODE_LENGTH), unique=True, nullable=False)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[RoomType | None] = mapped_column(ROOM_TYPE_ENUM, server_default=RoomType.PRIVATE.value)
    language: Mapped[Language] = mapped_column(LANGUAGE_ENUM, nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(DIFFICULTY_ENUM, nullable=False)
    rounds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    # None = automatico: 2 veces el tiempo ideal del texto de cada ronda.
    time_limit_s: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[RoomStatus | None] = mapped_column(ROOM_STATUS_ENUM, server_default=RoomStatus.WAITING.value)
    host: Mapped["User"] = relationship(back_populates="rooms", foreign_keys=[host_id], passive_deletes="all")
    members: Mapped[list["User"]] = relationship(secondary=room_members, passive_deletes=True)
    games: Mapped[list["Game"]] = relationship(back_populates="room", passive_deletes="all")
