from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import String, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthSession, User
from app.security import create_access_token, decode_session_token

IDLE_TIMEOUT = timedelta(minutes=15)
ABSOLUTE_TIMEOUT = timedelta(hours=24)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def issue_session(db: Session, user_id: int) -> str:
    now = utc_now()
    absolute = (now + min(
        ABSOLUTE_TIMEOUT, timedelta(minutes=settings.jwt_expire_minutes),
    )).replace(microsecond=0)  # JWT exp is expressed in whole seconds.
    session_id = uuid4()
    token = create_access_token(user_id, session_id, absolute)
    db.add(AuthSession(
        id=session_id, user_id=user_id,
        idle_expires_at=min(now + IDLE_TIMEOUT, absolute),
        absolute_expires_at=absolute,
    ))
    db.commit()
    return token


def session_user(db: Session, token: str) -> User | None:
    claims = decode_session_token(token)
    if claims is None:
        return None
    subject, session_id = claims
    now = utc_now()
    user = db.scalar(
        select(User).join(AuthSession, AuthSession.user_id == User.id).where(
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.idle_expires_at > now,
            AuthSession.absolute_expires_at > now,
        )
    )
    return user if user is not None and str(user.id) == subject else None


def revoke_session(db: Session, token: str) -> bool:
    claims = decode_session_token(token)
    if claims is None:
        return False
    subject, session_id = claims
    now = utc_now()
    revoked = db.scalar(
        update(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id.cast(String) == subject,
            AuthSession.revoked_at.is_(None),
            AuthSession.idle_expires_at > now,
            AuthSession.absolute_expires_at > now,
        ).values(revoked_at=now).returning(AuthSession.id)
    )
    db.commit()
    return revoked is not None
