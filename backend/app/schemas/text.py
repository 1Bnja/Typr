from pydantic import Field, field_validator

from app.models.enums import Difficulty, Language
from app.schemas.base import CamelModel
from app.schemas.user import UserPublic

MAX_CONTENT_LENGTH = 5000

class TextCreate(CamelModel):
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)
    language: Language
    difficulty: Difficulty
    ideal_time_ms: int | None = Field(default=None, gt=0)

    @field_validator("content", mode="after")
    @classmethod
    def content_no_vacio(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("el texto no puede estar vacio")
        return value


class TextUpdate(CamelModel):
    content: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT_LENGTH)
    language: Language | None = None
    difficulty: Difficulty | None = None
    ideal_time_ms: int | None = Field(default=None, gt=0)

    @field_validator("content", mode="after")
    @classmethod
    def content_no_vacio(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("el texto no puede estar vacio")
        return value


class TextPublic(CamelModel):
    id: int
    content: str
    language: Language
    difficulty: Difficulty
    ideal_time_ms: int | None
    record_user_id: int | None


class TextDetail(TextPublic):
    record_user: UserPublic | None = None
