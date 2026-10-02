from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Index, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import DIFFICULTY_ENUM, LANGUAGE_ENUM, ROOM_STATUS_ENUM, ROOM_TYPE_ENUM
from app.models.enums import Difficulty, Language, RoomStatus, RoomType

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.user import User

room_members = Table(
    "room_members",
    Base.metadata,
    Column("room_id", ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
    # El nombre coincide con el de init.sql: si no, Alembic genera un
    # CREATE INDEX duplicado en el proximo autogenerate.
    Column("member_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_room_members_member_id", "member_id"),
)


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (Index("ix_rooms_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[RoomType | None] = mapped_column(ROOM_TYPE_ENUM, server_default=RoomType.PRIVATE.value)
    language: Mapped[Language] = mapped_column(LANGUAGE_ENUM, nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(DIFFICULTY_ENUM, nullable=False)
    status: Mapped[RoomStatus | None] = mapped_column(ROOM_STATUS_ENUM, server_default=RoomStatus.WAITING.value)
    host: Mapped["User"] = relationship(back_populates="rooms", foreign_keys=[host_id], passive_deletes="all")
    members: Mapped[list["User"]] = relationship(secondary=room_members, passive_deletes=True)
    games: Mapped[list["Game"]] = relationship(back_populates="room", passive_deletes="all")
