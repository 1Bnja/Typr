from pydantic import EmailStr
from app.schemas.base import CamelModel


class UserPublic(CamelModel):
    """Datos minimos de un usuario, para anidar en otras respuestas.

    Es lo que expone `GameParticipantDetail.user`, asi que no agrega campos sin
    pensarlo: cada campo nuevo se multiplica por cada participante de la partida.
    """

    id: int
    username: str


class UserMe(CamelModel):
    id: int
    username: str
    email: EmailStr
    avatar_url: str | None
