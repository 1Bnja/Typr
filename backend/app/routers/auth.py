from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.api_docs import UNAUTHORIZED
from app.deps import bearer_scheme, get_db
from app.schemas.auth import (
    LoginRequest,
    PracticeActivityRequest,
    PracticeActivityResponse,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserPublic
from app.services.auth import register_user, authenticate, UserAlreadyExists
from app.services.sessions import issue_session, renew_from_practice, revoke_session

router = APIRouter(tags=["auth"])


def registration_validation_details(errors):
    fields = ("username", "email", "password")
    types = (
        "missing",
        "string_type",
        "string_too_short",
        "string_too_long",
        "string_pattern_mismatch",
        "value_error",
        "model_attributes_type",
        "json_invalid",
    )
    details = []
    for error in errors:
        loc = error["loc"]
        field = next((field for field in fields if tuple(loc) == ("body", field)), None)
        kind = next((kind for kind in types if error["type"] == kind), "invalid")
        # Build from constants; validation messages and context can contain input.
        details.append({"loc": ["body", field] if field else ["body"], "type": kind})
    return details


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
    description="Creates an account with email, username and password.",
    responses={409: {"description": "The email or the username is already in use."}},
)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    try:
        return register_user(db, data)
    except UserAlreadyExists as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Este correo ya está en uso"
                if error.field == "email"
                else "El usuario ya existe bro"
            ),
        ) from error


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    description="Exchanges email and password for a session token. Send it as `Authorization: Bearer <token>`.",
    responses={401: {"description": "Invalid credentials."}},
)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas bro",
        )
    return TokenResponse(token=issue_session(db, user.id), user=user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
    description="Revokes the session identified by the bearer token.",
    responses=UNAUTHORIZED,
)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None or not revoke_session(db, credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado bro",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/practice-activity",
    response_model=PracticeActivityResponse,
    summary="Renew a session from practice activity",
    description=(
        "Extends the idle deadline of the current session when the user is "
        "actively practicing. Returns the new idle and absolute expiration times."
    ),
    responses=UNAUTHORIZED,
)
def practice_activity(
    data: PracticeActivityRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    deadlines = credentials and renew_from_practice(
        db, credentials.credentials, data.notice_id
    )
    if deadlines is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado bro",
            headers={"WWW-Authenticate": "Bearer"},
        )
    idle, absolute = deadlines
    return PracticeActivityResponse(idle_expires_at=idle, absolute_expires_at=absolute)
