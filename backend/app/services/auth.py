from app.models import User
from app.schemas.auth import RegisterRequest
from app.security import hash_password, verify_password

from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

class UserAlreadyExists(Exception):
    pass

def register_user(db: Session, data: RegisterRequest) -> User:
    email = data.email.lower()
    existing = db.scalar(select(User).where(or_(User.username == data.username, User.email == email)))
    if existing:
        raise UserAlreadyExists("El usuario o correo ya existe bro")
    user = User(
        username=data.username,
        email=email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise UserAlreadyExists()
    db.refresh(user)
    return user

def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.hashed_password):
        return None 
    return user
