from behave import given, then, when
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.main import app
from app.models import Difficulty, Game, GameMode, GameParticipant, Language, Text
from app.services.metrics import calculate_precision
from registration import REGISTER, new_account
from sessions import bearer, login

PRACTICE = "/api/v1/matches/practice"
CONTENT = "Steady practice builds speed."


def sign_up(context):
    account = new_account()
    response = context.client.post(REGISTER, json=account)
    assert response.status_code == 201, response.text
    return response.json()["id"], bearer(login(context.client, account))


@given("a registered player with a practice text")
def practice_player(context):
    context.client = TestClient(app)
    context.add_cleanup(context.client.close)
    context.user_id, context.headers = sign_up(context)
    with SessionLocal.begin() as db:
        text = Text(content=CONTENT, language=Language.ENG, difficulty=Difficulty.EASY)
        db.add(text)
        db.flush()
        context.text_id = text.id

    def cleanup():
        with SessionLocal.begin() as db:
            game_ids = select(Game.id).where(Game.text_id == context.text_id)
            db.execute(delete(GameParticipant).where(GameParticipant.game_id.in_(game_ids)))
            db.execute(delete(Game).where(Game.text_id == context.text_id))
            db.execute(delete(Text).where(Text.id == context.text_id))

    context.add_cleanup(cleanup)


@given("another registered player")
def other_player(context):
    context.other_id, context.other_headers = sign_up(context)


@when("the player finishes the practice text with {mistakes:d} mistake")
@when("the player finishes the practice text with {mistakes:d} mistakes")
def finish_practice(context, mistakes):
    context.mistakes = mistakes
    context.keystrokes = len(CONTENT) + mistakes
    context.response = context.client.post(PRACTICE, headers=context.headers, json={
        "textId": context.text_id,
        "timeMs": 12_000,
        "typed": CONTENT,
        "keystrokes": context.keystrokes,
        "errors": mistakes,
    })
    assert context.response.status_code == 201, context.response.text
    context.match = context.response.json()


@then("the response reports the speed, accuracy and score")
def check_metrics(context):
    match = context.match
    assert match["progress"] == 1, match
    assert match["ppm"] > 0, match
    assert 0 < match["precisionPct"] < 100, match
    assert match["precisionPct"] == calculate_precision(context.keystrokes, context.mistakes), match
    assert match["score"] > 0, match
    assert match["timeMs"] == 12_000, match


@then("the match appears in the player's practice history")
def check_history(context):
    response = context.client.get(PRACTICE, headers=context.headers)
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [context.match["id"]]


@then("the match is stored as an individual game without a room")
def check_individual(context):
    with SessionLocal() as db:
        game = db.get(Game, context.match["id"])
        assert game.mode == GameMode.SINGLEPLAYER
        assert game.room_id is None


@then("it is linked only to the authenticated player")
def check_owner(context):
    with SessionLocal() as db:
        owners = db.scalars(select(GameParticipant.user_id).where(
            GameParticipant.game_id == context.match["id"])).all()
    assert owners == [context.user_id], owners


@then("it does not appear in the other player's history")
def check_other_history(context):
    response = context.client.get(PRACTICE, headers=context.other_headers)
    assert response.status_code == 200, response.text
    assert response.json() == []
