from pydantic import Field
from app.models.enums import Difficulty, Language, RoomStatus, RoomType
from app.schemas.base import CamelModel
from app.schemas.user import UserPublic

class RoomCreate(CamelModel):
    type: RoomType = RoomType.PRIVATE
    language: Language
    difficulty: Difficulty
    password: str | None = Field(default=None, min_length=4, max_length=64)

class RoomUpdate(CamelModel):
    type: RoomType | None = None
    language: Language | None = None
    difficulty: Difficulty | None = None
    status: RoomStatus | None = None

class RoomJoinRequest(CamelModel):
    password: str | None = None

class RoomPublic(CamelModel):
    id: int
    host_id: int
    type: RoomType | None
    language: Language
    difficulty: Difficulty
    status: RoomStatus | None
    member_count: int | None = None

class RoomDetail(RoomPublic):
    host: UserPublic
    members: list[UserPublic] = []
