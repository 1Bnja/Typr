from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import bcrypt
from behave import given, then, when
from fastapi.testclient import TestClient
from sqlalchemy import event, or_, select

from app.database import SessionLocal
from app.main import app
from app.models import User

REGISTER = "/api/v1/auth/register"


def new_account():
    username = f"qa_{uuid4().hex[:16]}"
    return {
        "username": username,
        "email": f"{username}@example.com",
        "password": "fixture-password-01",
    }


def register(account):
    with TestClient(app) as client:
        return client.post(REGISTER, json=account)


def conflict(response, detail):
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": detail}, response.text


@given("two new registrations that share {identity}")
def shared_identity(context, identity):
    first, second = new_account(), new_account()
    if identity in ("email", "both"):
        second["email"] = first["email"].upper()
    if identity in ("username", "both"):
        second["username"] = first["username"]
    context.accounts = first, second


@when("both registrations reach the database insert in separate transactions")
def overlap(context):
    barrier = Barrier(2, timeout=15)
    transactions = set()

    def before_flush(session, *_):
        # Force both requests past their initial reads before either inserts.
        if any(isinstance(record, User) for record in session.new):
            assert session.in_transaction()
            transactions.add(session.get_transaction())
            barrier.wait()

    event.listen(SessionLocal, "before_flush", before_flush)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            context.responses = list(workers.map(register, context.accounts))
    finally:
        event.remove(SessionLocal, "before_flush", before_flush)
    assert len(transactions) == 2


@then('one request succeeds and the other receives "{detail}" with status 409')
def race_responses(context, detail):
    winner, loser = sorted(context.responses, key=lambda response: response.status_code)
    assert winner.status_code == 201, winner.text
    conflict(loser, detail)
    context.winner_id = winner.json()["id"]


@then("exactly one matching account is persisted")
def one_row(context):
    with SessionLocal() as db:
        ids = db.scalars(
            select(User.id).where(
                or_(
                    User.email.in_([a["email"].lower() for a in context.accounts]),
                    User.username.in_([a["username"] for a in context.accounts]),
                )
            )
        ).all()
    assert ids == [context.winner_id], ids


@then("a new unrelated account can still register")
def register_after_conflict(context):
    response = register(new_account())
    assert response.status_code == 201, response.text


@given("two registered accounts with different emails and usernames")
def existing_accounts(context):
    context.accounts = new_account(), new_account()
    for account in context.accounts:
        response = register(account)
        assert response.status_code == 201, response.text


@when("a new request uses the email of one and the username of the other")
def cross_account_conflict(context):
    first, second = context.accounts
    context.response = register(dict(first, username=second["username"]))


@then('registration returns "{detail}" with status 409')
def registration_conflict(context, detail):
    conflict(context.response, detail)


@when("a new account registers, logs in, and requests its profile")
def account_endpoints(context):
    account = context.account = new_account()
    with TestClient(app) as client:
        registration = client.post(REGISTER, json=account)
        assert registration.status_code == 201, registration.text
        login = client.post(
            "/api/v1/auth/login",
            json={"email": account["email"], "password": account["password"]},
        )
        assert login.status_code == 200, login.text
        profile = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {login.json()['token']}"},
        )
        assert profile.status_code == 200, profile.text
    assert registration.json()["username"] == account["username"]
    assert registration.json()["id"] == login.json()["user"]["id"] == profile.json()["id"]
    context.account_responses = registration, login, profile


@then("its persisted password is a bcrypt hash of the submitted password")
def stored_hash(context):
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == context.account["email"])).one()
        context.password_hash = user.hashed_password
        assert user.username == context.account["username"]
    password = context.account["password"]
    assert context.password_hash != password
    assert bcrypt.checkpw(password.encode(), context.password_hash.encode())


@then("the register, login, and profile responses omit password material")
def omit_password(context):
    def keys(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield key
                yield from keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from keys(nested)

    for response in context.account_responses:
        assert not any("password" in key.lower() for key in keys(response.json()))
        assert context.account["password"] not in response.text
        assert context.password_hash not in response.text
