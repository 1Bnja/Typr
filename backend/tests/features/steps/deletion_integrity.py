from behave import given, then, when
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Game, GameParticipant, Room, Text, User, room_members
from app.services.race import ideal_time_ms

IDEAL_TIME_MS = 18000


def insert_id(db, model, **values):
    return db.scalar(insert(model).values(**values).returning(model.id))


def participants(context):
    return set(context.db.scalars(
        select(GameParticipant.user_id).where(GameParticipant.game_id == context.match_id)
    ))


def text_state(context, text_id):
    return context.db.execute(select(Text.__table__).where(Text.id == text_id)).one()


def match_state(context):
    return context.db.execute(select(Game.__table__).where(Game.id == context.match_id)).one()


@given("a record holder hosts a room and has played a match with another user")
def seed_deletion_fixture(context):
    db = context.db = SessionLocal()
    context.add_cleanup(db.close)  # Rolls back all fixture writes and successful deletes.
    context.holder_id, context.peer_id = [
        insert_id(db, User, username=name, email=f"{name}@typr.test", hashed_password="unused")
        for name in ("ri13_holder", "ri13_peer")
    ]
    context.room_id = insert_id(
        db, Room, host_id=context.holder_id, code="RITHRT", language="eng", difficulty="easy"
    )
    db.execute(insert(room_members), [
        {"room_id": context.room_id, "member_id": user_id}
        for user_id in (context.holder_id, context.peer_id)
    ])
    context.text_id = insert_id(
        db, Text, content="Synthetic text for the deletion integrity test.",
        language="eng", difficulty="easy", ideal_time_ms=IDEAL_TIME_MS,
        record_user_id=context.holder_id,
    )
    context.second_text_id = insert_id(
        db, Text, content="Another record by the same holder.",
        language="eng", difficulty="easy", ideal_time_ms=19000,
        record_user_id=context.holder_id,
    )
    unrelated_ids = [
        insert_id(
            db, Text, content=content, language="eng", difficulty="easy",
            ideal_time_ms=stored_time, record_user_id=holder,
        )
        for content, stored_time, holder in (
            ("A record by another user.", 20000, context.peer_id),
            ("A historical ideal time with no holder.", 21000, None),
        )
    ]
    context.unrelated_texts = {
        text_id: text_state(context, text_id) for text_id in unrelated_ids
    }
    context.match_id = insert_id(
        db, Game, room_id=context.room_id, text_id=context.text_id, mode="multiplayer"
    )
    db.execute(insert(GameParticipant), [
        {"game_id": context.match_id, "user_id": user_id}
        for user_id in (context.holder_id, context.peer_id)
    ])
    context.membership_query = select(room_members.c.member_id).where(
        room_members.c.room_id == context.room_id
    )
    assert set(db.scalars(context.membership_query)) == participants(context) == {
        context.holder_id, context.peer_id
    }
    context.original_text = text_state(context, context.text_id)
    context.original_match = match_state(context)
    assert context.original_text.record_user_id == context.holder_id
    assert context.original_text.ideal_time_ms == IDEAL_TIME_MS


@when("PostgreSQL deletes the record holder")
def delete_record_holder(context):
    result = context.db.execute(delete(User).where(User.id == context.holder_id))
    assert result.rowcount == 1


@then("the holder's participation, hosted room, and its memberships are gone")
def check_user_cascades(context):
    assert context.db.get(User, context.holder_id) is None
    assert context.db.get(User, context.peer_id) is not None
    assert context.db.get(Room, context.room_id) is None
    assert context.db.scalars(context.membership_query).all() == []
    assert participants(context) == {context.peer_id}


@then("all the holder's texts have no record and use the default ideal time")
def check_record_reference(context):
    for text_id in (context.text_id, context.second_text_id):
        stored_text = text_state(context, text_id)
        assert stored_text.record_user_id is None
        assert stored_text.ideal_time_ms is None, stored_text
        assert ideal_time_ms(stored_text.content, stored_text.ideal_time_ms) == (
            len(stored_text.content) * 1000 // 5
        )


@then("the other user's record and the holderless text are unchanged")
def check_unrelated_texts(context):
    for text_id, before in context.unrelated_texts.items():
        assert text_state(context, text_id) == before


@when("PostgreSQL attempts to delete the text within a savepoint")
def delete_referenced_text(context):
    try:
        with context.db.begin_nested():
            context.db.execute(delete(Text).where(Text.id == context.text_id))
    except IntegrityError as error:
        assert error.orig.sqlstate == "23503", error
        assert error.orig.diag.constraint_name == "games_text_id_fkey", error
    else:
        raise AssertionError("PostgreSQL deleted a text referenced by a match")


@then("the text and its match retain their original state after rollback")
def check_restricted_delete_rollback(context):
    assert text_state(context, context.text_id) == context.original_text
    assert match_state(context) == context.original_match
    assert participants(context) == {context.holder_id, context.peer_id}
