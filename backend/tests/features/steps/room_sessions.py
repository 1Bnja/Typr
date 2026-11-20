import faulthandler
import sys
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from behave import given, then, when
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.main import app
from app.models import AuthSession, Difficulty, Game, Language, Text
from app.services import sessions
from app.ws import rooms
from registration import REGISTER, new_account
from sessions import PROFILE, bearer, login


def request_ok(response, status=200):
    assert response.status_code == status, response.text
    return response


def member(context, lifetime=1440):
    account = new_account()
    user_id = request_ok(context.client.post(REGISTER, json=account), 201).json()["id"]
    with patch.object(sessions.settings, "jwt_expire_minutes", lifetime):
        return user_id, login(context.client, account)


def at(context, minutes=0, seconds=0):
    context.clock.return_value = context.start + timedelta(minutes=minutes, seconds=seconds)


def expect(socket, kind):
    while True:
        message = socket.receive_json()
        if message["type"] == kind:
            return message


def open_socket(context, member):
    socket = context.stack.enter_context(context.client.websocket_connect(context.ws_path))
    socket.send_json({"type": "auth", "token": member[1]})
    return socket


def assert_closed(socket):
    message = socket.receive()
    assert (message["type"], message.get("code")) == ("websocket.close", 4401), message


@given("a room with two signed-in members")
def room(context, lifetime=1440):
    context.stack = ExitStack()
    faulthandler.dump_traceback_later(15, file=sys.__stderr__, exit=True)
    context.add_cleanup(faulthandler.cancel_dump_traceback_later)
    context.add_cleanup(context.stack.close)
    context.start = datetime.now(timezone.utc).replace(microsecond=0)
    context.clock = context.stack.enter_context(patch.object(sessions, "utc_now"))
    at(context)
    context.stack.enter_context(patch.object(rooms, "SESSION_CHECK_INTERVAL_S", 0.05, create=True))
    context.stack.enter_context(patch.object(rooms, "COUNTDOWN_S", 0))
    context.client = context.stack.enter_context(TestClient(app))
    context.host = member(context, lifetime)
    context.peer = member(context)
    context.headers = bearer(context.host[1])
    response = request_ok(context.client.post("/api/v1/rooms", headers=context.headers, json={
        "language": "eng", "difficulty": "easy", "timeLimitS": 90,
    }), 201)
    code = response.json()["code"]
    context.ws_path = f"/api/v1/ws/rooms/{code}"
    context.join_path = f"/api/v1/rooms/{code}/join"
    request_ok(context.client.post(context.join_path, headers=bearer(context.peer[1])))


@given("both members are connected")
def connect_members(context):
    context.host_socket = open_socket(context, context.host)
    expect(context.host_socket, "room_state")
    context.peer_socket = open_socket(context, context.peer)
    expect(context.peer_socket, "room_state")
    expect(context.host_socket, "room_state")


@when("the host session ends by {reason} before connecting")
def end_session(context, reason):
    if reason == "logout":
        logout(context)
    else:
        at(context, minutes=15 if reason == "idle expiry" else 1440)


@then("the room handshake closes as unauthorized")
def rejected_handshake(context):
    assert_closed(open_socket(context, context.host))


@when("the host polls and sends a ping just before idle expiry")
def poll_and_ping(context):
    at(context, minutes=14, seconds=59)
    request_ok(context.client.get(PROFILE, headers=context.headers))
    ping(context)
    renew_peer(context)


def ping(context):
    context.host_socket.send_json({"type": "ping"})
    assert expect(context.host_socket, "error")["code"] == "invalid_message"


def renew_peer(context):
    practice_activity(context, bearer(context.peer[1]))


def practice_activity(context, headers):
    request_ok(context.client.post("/api/v1/auth/practice-activity", headers=headers, json={
        "noticeId": int(context.clock.return_value.timestamp() * 1000),
    }))


@when("the host reaches idle expiry while silent")
def expire_idle(context):
    at(context, minutes=15)


@when("the host logs out without sending another frame")
def logout(context):
    request_ok(context.client.post("/api/v1/auth/logout", headers=context.headers), 204)


@then("only the host socket closes as unauthorized")
def host_departure(context):
    assert_closed(context.host_socket)
    assert expect(context.peer_socket, "player_left")["userId"] == context.host[0]
    members = expect(context.peer_socket, "room_state")["room"]["members"]
    assert {m["id"]: m["connected"] for m in members} == {
        context.host[0]: False, context.peer[0]: True,
    }


@then("the peer can still change readiness")
def peer_ready(context):
    context.peer_socket.send_json({"type": "ready", "ready": True})
    members = expect(context.peer_socket, "room_state")["room"]["members"]
    assert next(member for member in members if member["id"] == context.peer[0])["isReady"]


def seed_race_text(context):
    with SessionLocal.begin() as db:
        text = Text(content=f"Synthetic race text {context.host[0]}.",
                    language=Language.ENG, difficulty=Difficulty.EASY)
        db.add(text)
        db.flush()
        text_id = text.id

    def cleanup():
        with SessionLocal.begin() as db:
            db.execute(delete(Game).where(Game.text_id == text_id))
            db.execute(delete(Text).where(Text.id == text_id))

    context.stack.callback(cleanup)


@given("a live race with two signed-in members")
def live_race(context, lifetime=1440):
    room(context, lifetime)
    seed_race_text(context)
    connect_members(context)
    peer_ready(context)
    expect(context.host_socket, "room_state")
    context.host_socket.send_json({"type": "start"})
    expect(context.host_socket, "race_start")
    context.length = len(expect(context.peer_socket, "race_start")["text"]["content"])


@given("a live race with a sixteen-minute host session")
def short_race(context):
    live_race(context, 16)


def advance(context, typed, errors=0):
    context.host_socket.send_json({"type": "progress", "typed": typed, "errors": errors})
    progress = expect(context.peer_socket, "progress_update")
    assert progress["userId"] == context.host[0]
    assert progress["progress"] == typed / context.length
    # The listener processes frames serially; a reply confirms renewal has settled.
    ping(context)


def assert_deadline(context, minutes):
    with SessionLocal() as db:
        row = db.scalars(select(AuthSession).where(AuthSession.user_id == context.host[0])).one()
        assert row.idle_expires_at == context.start + timedelta(minutes=minutes), row.idle_expires_at


@when("the host advances near idle expiry")
def first_advance(context):
    at(context, minutes=14)
    renew_peer(context)
    advance(context, 1)


@then("its idle deadline moves by fifteen minutes from receipt")
def initial_renewal(context):
    assert_deadline(context, 29)


@then("further advances respect the one-minute cadence")
def cadence(context):
    at(context, minutes=14, seconds=30)
    with patch.object(sessions, "renew_from_race", wraps=sessions.renew_from_race) as renew:
        advance(context, 2)
        renew.assert_not_called()
    assert_deadline(context, 29)
    practice_activity(context, context.headers)
    assert_deadline(context, 29)
    at(context, minutes=15)
    with patch.object(sessions, "renew_from_race", wraps=sessions.renew_from_race) as renew:
        advance(context, 3)
        renew.assert_called_once()
    assert_deadline(context, 30)


@then("repeated progress does not renew")
def repeated_progress(context):
    at(context, minutes=16)
    with patch.object(sessions, "renew_from_race", wraps=sessions.renew_from_race) as renew:
        advance(context, 3, errors=1)
        renew.assert_not_called()
    assert_deadline(context, 30)


@then("its renewal is capped by absolute expiry")
def capped_renewal(context):
    assert_deadline(context, 16)


@then("its socket closes at absolute expiry while the peer stays connected")
def absolute_expiry(context):
    at(context, minutes=16)
    host_departure(context)


@then("the peer can finish the race after the host disconnects")
def finish_race(context):
    context.peer_socket.send_json({"type": "progress", "typed": context.length, "errors": 0})
    results = expect(context.peer_socket, "race_end")["results"]
    assert {result["userId"]: result["finished"] for result in results} == {
        context.peer[0]: True, context.host[0]: False,
    }
