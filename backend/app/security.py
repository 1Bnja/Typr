from datetime import datetime
from uuid import UUID
import bcrypt
import jwt
from app.config import settings

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed_password.encode())

def create_access_token(user_id: int, session_id: UUID, expires_at: datetime) -> str:
    payload = {"sub": str(user_id), "exp": expires_at, "jti": str(session_id)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str, *required: str) -> dict:
    return jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
        options={"require": list(required)},
    )


def decode_access_token(token: str) -> int | None:
    """Stateless WebSocket compatibility until room session enforcement lands."""
    try:
        return int(_decode(token, "sub")["sub"])
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
        return None


def decode_session_token(token: str) -> tuple[str, UUID] | None:
    try:
        payload = _decode(token, "sub", "exp", "jti")
        return payload["sub"], UUID(payload["jti"])
    except (jwt.InvalidTokenError, AttributeError, TypeError, ValueError, OverflowError):
        return None
