from pydantic import ConfigDict, Field

from app.models.enums import Difficulty, Language, RoomStatus, RoomType
from app.models.room import MAX_ROUNDS, MAX_TIME_LIMIT_S, MIN_TIME_LIMIT_S
from app.schemas.base import CamelModel


class RoomCreate(CamelModel):
    model_config = ConfigDict(extra="forbid")

    type: RoomType = RoomType.PRIVATE
    language: Language
    difficulty: Difficulty
    rounds: int = Field(default=1, ge=1, le=MAX_ROUNDS)
    # None = automático: 2 veces el tiempo ideal del texto de cada ronda.
    time_limit_s: int | None = Field(
        default=None, ge=MIN_TIME_LIMIT_S, le=MAX_TIME_LIMIT_S
    )


class RoomUpdate(CamelModel):
    """Cambios parciales: solo se aplican los campos que vienen en el cuerpo."""

    model_config = ConfigDict(extra="forbid")

    type: RoomType | None = None
    language: Language | None = None
    difficulty: Difficulty | None = None
    rounds: int | None = Field(default=None, ge=1, le=MAX_ROUNDS)
    time_limit_s: int | None = Field(
        default=None, ge=MIN_TIME_LIMIT_S, le=MAX_TIME_LIMIT_S
    )


class RoomMemberPublic(CamelModel):
    id: int
    username: str
    is_host: bool
    is_ready: bool


class RoomPublic(CamelModel):
    id: int
    code: str
    host_id: int
    type: RoomType
    language: Language
    difficulty: Difficulty
    rounds: int
    time_limit_s: int | None
    status: RoomStatus
    members: list[RoomMemberPublic]
