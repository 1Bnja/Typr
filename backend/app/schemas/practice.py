from datetime import datetime

from pydantic import ConfigDict, Field, model_validator

from app.schemas.base import CamelModel
from app.schemas.game import GameParticipantResult
from app.text_constants import MAX_CONTENT_LENGTH
from app.text_enums import Difficulty, Language


class PracticeTextInput(CamelModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)
    language: Language


class PracticeMatchCreate(CamelModel):
    model_config = ConfigDict(extra="forbid")

    text_id: int | None = Field(default=None, gt=0)
    text: PracticeTextInput | None = None
    difficulty: Difficulty | None = None
    time_ms: int = Field(gt=0, le=2_147_483_647)
    # Señales crudas: el servidor calcula PPM, precisión, progreso y puntaje.
    typed: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)
    keystrokes: int = Field(gt=0, le=2_147_483_647)
    errors: int = Field(ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def validate_request(self):
        if (self.text_id is None) == (self.text is None):
            raise ValueError("Envía textId o text, pero no ambos.")
        if self.errors > self.keystrokes:
            raise ValueError("errors no puede superar keystrokes.")
        return self


class PracticeMatchPublic(GameParticipantResult):
    id: int
    text_id: int
    language: Language
    difficulty: Difficulty
    score: int
    started_at: datetime
    finished_at: datetime


class LeaderboardEntry(CamelModel):
    position: int
    user_id: int
    username: str
    ppm: int
    precision_pct: float
    score: int
    time_ms: int
    finished_at: datetime


class MonthlyLeaderboard(CamelModel):
    month: str
    difficulty: Difficulty
    language: Language | None
    timezone: str
    entries: list[LeaderboardEntry]
