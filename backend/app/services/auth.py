from typing import Literal

from psycopg.errors import UniqueViolation
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.auth import RegisterRequest
from app.security import hash_password, verify_password


class UserAlreadyExists(Exception):
    def __init__(self, field: Literal["email", "username"]):
        super().__init__(field)
        self.field = field


def registration_conflict(
    db: Session, email: str, username: str
) -> UserAlreadyExists | None:
    email_matches = User.email == email
    matched_email = db.scalar(
        select(User.email)
        .where(or_(email_matches, User.username == username))
        .order_by(email_matches.desc())
        .limit(1)
    )
    if matched_email is None:
        return None
    return UserAlreadyExists("email" if matched_email == email else "username")


def register_user(db: Session, data: RegisterRequest) -> User:
    email = data.email.lower()
    conflict = registration_conflict(db, email, data.username)
    if conflict:
        raise conflict
    user = User(
        username=data.username,
        email=email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if isinstance(error.orig, UniqueViolation):
            # PostgreSQL may report the username constraint even if both collided.
            conflict = registration_conflict(db, email, data.username)
            if conflict:
                raise conflict from error
        raise
    db.refresh(user)
    return user

def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.hashed_password):
        return None 
    return user
