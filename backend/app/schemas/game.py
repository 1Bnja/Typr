from datetime import datetime
from pydantic import Field
from app.models.enums import GameMode
from app.schemas.base import CamelModel
from app.schemas.user import UserPublic

class GameCreate(CamelModel):
    room_id: int | None = None
    text_id: int
    mode: GameMode | None = None

class GameParticipantResult(CamelModel):
    time_ms: int = Field(gt=0)
    ppm: int = Field(ge=0)
    precision_pct: float = Field(ge=0, le=100)
    progress: float = Field(ge=0, le=1)

class GameFinishRequest(CamelModel):
    finished_at: datetime | None = None

class GameResultRequest(CamelModel):
    result: GameParticipantResult

class GameParticipantPublic(CamelModel):
    id: int
    user_id: int
    time_ms: int | None
    ppm: int | None
    precision_pct: float | None
    progress: float | None
    position: int | None
    score: int | None

class GameParticipantDetail(GameParticipantPublic):
    user: UserPublic

class GamePublic(CamelModel):
    id: int
    room_id: int | None
    text_id: int
    mode: GameMode | None
    started_at: datetime | None
    finished_at: datetime | None

class GameDetail(GamePublic):
    participants: list[GameParticipantDetail] = []
