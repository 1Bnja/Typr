from pydantic import EmailStr
from app.schemas.base import CamelModel

class UserPublic(CamelModel):
    id: int
    username: str

class UserMe(CamelModel):
    id: int
    username: str
    email: EmailStr
    avatar_url: str | None