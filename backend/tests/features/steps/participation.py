from behave import given, then, when
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.main import app
from app.models import Game, GameParticipant, Room
from room_sessions import expect, member, request_ok
from sessions import bearer

PRACTICE = "/api/v1/matches/practice"


@given("two signed-in practice players")
def practice_players(context):
    context.client = TestClient(app)
    context.add_cleanup(context.client.close)
    context.player, context.other = member(context), member(context)
    phrase = "La práctica diaria mejora la velocidad al escribir."
    context.payload = {
        "text": {"content": phrase, "language": "spa"},
        "typed": phrase,
        "timeMs": 12000,
        "keystrokes": len(phrase),
        "errors": 0,
    }


def submit(context, payload):
    return context.client.post(PRACTICE, json=payload, headers=bearer(context.player[1]))


@when("the first player submits practice with the second player's user ID")
def supplied_owner(context):
    with SessionLocal() as db:
        context.game_count = db.scalar(select(func.count()).select_from(Game))
    context.response = submit(context, {**context.payload, "userId": context.other[0]})


@then("the client-supplied owner is rejected without recording a match")
def rejected_owner(context):
    response = request_ok(context.response, 422)
    assert any(
        error["loc"] == ["body", "userId"] and error["type"] == "extra_forbidden"
        for error in response.json()["detail"]
    ), response.text
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Game)) == context.game_count


@when("the first player submits the same practice without an owner field")
def submit_practice(context):
    context.game_id = request_ok(submit(context, context.payload), 201).json()["id"]


@then("one solo participation exists for the signed-in player and has no room")
def solo_participation(context):
    with SessionLocal() as db:
        game = db.get(Game, context.game_id)
        assert game.mode.value == "singleplayer"
        assert game.room_id is None
        assert [row.user_id for row in game.participants] == [context.player[0]]


@when("both members complete the race")
def complete_race(context):
    for socket in (context.host_socket, context.peer_socket):
        socket.send_json({"type": "progress", "typed": context.length, "errors": 0})
    expect(context.peer_socket, "race_end")


@then("the game is linked to the live room and has one participation per player")
def race_participation(context):
    with SessionLocal() as db:
        code = context.ws_path.rsplit("/", 1)[-1]
        room_id = db.scalars(select(Room.id).where(Room.code == code)).one()
        game = db.scalars(select(Game).where(Game.room_id == room_id)).one()
        assert game.mode.value == "multiplayer"
        assert sorted(row.user_id for row in game.participants) == sorted(
            [context.host[0], context.peer[0]]
        )
        context.game_id = game.id


@then("PostgreSQL rejects a duplicate game and user pair without adding a row")
def duplicate_participation(context):
    pair = {"game_id": context.game_id, "user_id": context.host[0]}
    statement = select(GameParticipant.id).filter_by(**pair)
    with SessionLocal() as db:
        original = db.scalars(statement).one()
        try:
            with db.begin_nested():
                db.execute(insert(GameParticipant).values(**pair))
        except IntegrityError as error:
            assert error.orig.sqlstate == "23505"
            assert error.orig.diag.constraint_name == "game_participants_game_id_user_id_key"
        else:
            raise AssertionError("PostgreSQL accepted a duplicate participation")
        assert db.scalars(statement).all() == [original]
