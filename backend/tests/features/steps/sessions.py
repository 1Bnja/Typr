from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import jwt
from behave import given, then, when
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Room, User
from app.services import sessions
from registration import new_account, register

PROFILE = "/api/v1/users/me"


def login(client, account):
    response = client.post("/api/v1/auth/login", json={
        "email": account["email"], "password": account["password"],
    })
    assert response.status_code == 200, response.text
    return response.json()["token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def sign(claims):
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@given('a logged-in fixture with a "{credential}" credential')
def credential_fixture(context, credential):
    context.client = TestClient(app)
    context.add_cleanup(context.client.close)
    context.account = new_account()
    response = register(context.account)
    assert response.status_code == 201, response.text
    user_id = context.user_id = response.json()["id"]
    context.now = datetime.now(timezone.utc).replace(microsecond=0)
    with patch.object(sessions, "utc_now", return_value=context.now):
        token = login(context.client, context.account)
    assert context.client.get(PROFILE, headers=bearer(token)).json()["id"] == user_id
    claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if credential == "absent":
        context.headers = {}
        return
    if credential == "invalid":
        token = "not-a-jwt"
    elif credential == "tampered":
        head, body, signature = token.split(".")
        token = f"{head}.{body}.{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"
    elif credential == "expired JWT":
        token = sign(dict(claims, exp=context.now - timedelta(seconds=1)))
    elif credential in ("idle-expired", "absolute-expired"):
        deadline = context.now + timedelta(minutes=15)
        if credential == "absolute-expired":
            from app.models import AuthSession

            with SessionLocal.begin() as db:
                session = db.get(AuthSession, UUID(claims["jti"]))
                deadline = session.absolute_expires_at
                session.idle_expires_at = deadline + timedelta(minutes=1)
        clock = patch.object(sessions, "utc_now", return_value=deadline)
        clock.start()
        context.add_cleanup(clock.stop)
    elif credential == "revoked":
        from app.models import AuthSession

        with SessionLocal() as db:
            db.get(AuthSession, UUID(claims["jti"])).revoked_at = context.now
            db.commit()
    elif credential == "nonexistent user":
        with SessionLocal.begin() as db:
            db.execute(delete(User).where(User.id == user_id))
    elif credential == "legacy":
        token = sign({"sub": str(user_id), "exp": claims["exp"]})
    elif credential == "unknown session":
        token = sign(dict(claims, jti=str(uuid4())))
    elif credential == "mismatched user":
        other = register(new_account())
        assert other.status_code == 201, other.text
        token = sign(dict(claims, sub=str(other.json()["id"])))
    context.headers = bearer(token)


@when("it requests a private profile and tries to create a room")
def protected_requests(context):
    with SessionLocal() as db:
        context.room_count = db.scalar(select(func.count()).select_from(Room))
    context.responses = [
        context.client.get(PROFILE, headers=context.headers),
        context.client.post("/api/v1/rooms", headers=context.headers, json={
            "language": "spa", "difficulty": "easy",
        }),
    ]


def assert_unauthorized(response):
    assert response.status_code == 401, response.status_code
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json() == {"detail": "No autenticado bro"}


@then("both requests return only a bearer 401 and no room is created")
def no_private_effects(context):
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Room)) == context.room_count
    for response in context.responses:
        assert_unauthorized(response)


@when("it reads its profile just before the idle deadline")
def read_before_deadline(context):
    context.deadline = context.now + timedelta(minutes=15)
    with patch.object(sessions, "utc_now", return_value=context.deadline - timedelta(seconds=1)):
        assert context.client.get(PROFILE, headers=context.headers).status_code == 200


@then("it is rejected at the original deadline and a fresh login works")
def read_at_deadline(context):
    with patch.object(sessions, "utc_now", return_value=context.deadline):
        assert_unauthorized(context.client.get(PROFILE, headers=context.headers))
        new_headers = bearer(login(context.client, context.account))
        assert new_headers != context.headers
        assert context.client.get(PROFILE, headers=new_headers).json()["id"] == context.user_id
