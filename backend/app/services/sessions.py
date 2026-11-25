from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import String, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthSession, User
from app.security import create_access_token, decode_session_token

IDLE_TIMEOUT = timedelta(minutes=15)
ABSOLUTE_TIMEOUT = timedelta(hours=24)
RENEWAL_INTERVAL = timedelta(minutes=1)


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


def _validated_session(db: Session, token: str) -> tuple[User, datetime, datetime] | None:
    claims = decode_session_token(token)
    if claims is None:
        return None
    subject, session_id = claims
    now = utc_now()
    row = db.execute(
        select(User, AuthSession.idle_expires_at, AuthSession.absolute_expires_at)
        .join(AuthSession, AuthSession.user_id == User.id).where(
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.idle_expires_at > now,
            AuthSession.absolute_expires_at > now,
        )
    ).one_or_none()
    if row is None:
        return None
    user, idle, absolute = row
    return (user, idle, absolute) if str(user.id) == subject else None


def session_user(db: Session, token: str) -> User | None:
    row = _validated_session(db, token)
    return row[0] if row is not None else None


def _utc_deadline(deadline: datetime) -> datetime:
    # SQLite room fixtures return naive datetimes for columns that store UTC.
    return deadline.replace(tzinfo=deadline.tzinfo or timezone.utc)


def _renewal_due_at(idle: datetime) -> datetime:
    return idle - IDLE_TIMEOUT + RENEWAL_INTERVAL


@dataclass(frozen=True)
class RaceSessionCheck:
    idle: datetime
    absolute: datetime

    def renewal_not_due(self) -> bool:
        # Recheck after handling the frame: handling may cross the cadence boundary.
        return utc_now() < min(_renewal_due_at(self.idle), self.absolute)


def validate_race_session(db: Session, token: str) -> RaceSessionCheck | None:
    """Valida el token sin hidratar el `User`: la carrera solo necesita los plazos.

    El join a `users` conserva la garantía de que el usuario existe; se
    seleccionan columnas sueltas en lugar de la entidad para evitar el coste
    de construir un objeto ORM en cada trama.
    """
    claims = decode_session_token(token)
    if claims is None:
        return None
    subject, session_id = claims
    now = utc_now()
    row = db.execute(
        select(
            AuthSession.user_id,
            AuthSession.idle_expires_at,
            AuthSession.absolute_expires_at,
        )
        .join(User, User.id == AuthSession.user_id)
        .where(
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.idle_expires_at > now,
            AuthSession.absolute_expires_at > now,
        )
    ).one_or_none()
    if row is None:
        return None
    user_id, idle, absolute = row
    if str(user_id) != subject:
        return None
    return RaceSessionCheck(_utc_deadline(idle), _utc_deadline(absolute))


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


def renew_from_practice(db: Session, token: str, notice_id: int) -> tuple[datetime, datetime] | None:
    return _renew_from_activity(db, token, notice_id)


def renew_from_race(db: Session, token: str) -> bool:
    return _renew_from_activity(db, token) is not None


def _renew_from_activity(
    db: Session, token: str, notice_id: int | None = None,
) -> tuple[datetime, datetime] | None:
    claims = decode_session_token(token)
    if claims is None:
        return None
    subject, session_id = claims
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id.cast(String) == subject,
        ).with_for_update()
    )
    # Recheck after taking the lock: waiting behind another writer cannot buy time.
    now = utc_now()
    if session is None or session.revoked_at is not None:
        return None
    idle = _utc_deadline(session.idle_expires_at)
    absolute = _utc_deadline(session.absolute_expires_at)
    if (
        now >= min(idle, absolute)
        or decode_session_token(token) is None
    ):
        return None

    previous = session.last_practice_notice
    if notice_id is None or previous is None or notice_id > previous:
        if notice_id is not None:
            # Practice notices retain their own ordering; race progress is ordered by the room.
            session.last_practice_notice = notice_id
        if now >= _renewal_due_at(idle):
            idle = session.idle_expires_at = min(now + IDLE_TIMEOUT, absolute)
    db.commit()
    return idle, absolute
