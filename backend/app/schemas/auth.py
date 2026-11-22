from datetime import datetime

from pydantic import ConfigDict, EmailStr, Field, field_validator
from app.schemas.base import CamelModel
from app.schemas.user import UserPublic

class RegisterRequest(CamelModel):
    username: str = Field(min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def password_max_bytes(cls, value: str) -> str:
        if len(value.encode()) > 72:
            raise ValueError("tu pass es muy larga bro")
        return value

class LoginRequest(CamelModel):
    email: EmailStr
    password: str 

class TokenResponse(CamelModel):
    token: str
    user: UserPublic


class PracticeActivityRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")

    notice_id: int = Field(strict=True, gt=0, le=2**53 - 1)


class PracticeActivityResponse(CamelModel):
    idle_expires_at: datetime
    absolute_expires_at: datetime
