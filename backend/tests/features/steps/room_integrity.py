from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from behave import given, then, when
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.main import app
from app.models import Room, room_members
from room_sessions import member, request_ok
from sessions import bearer

ROOMS = "/api/v1/rooms"


def create_room(context):
    host = member(context)
    return request_ok(context.client.post(
        ROOMS, headers=bearer(host[1]), json={"language": "eng", "difficulty": "easy"}
    ), 201).json()


def join(client, room, player):
    return client.post(f"{ROOMS}/{room['code']}/join", headers=bearer(player[1]))


def concurrent_joins(pairs):
    ready = Barrier(len(pairs), timeout=5)

    def join_as(pair):
        with TestClient(app) as client:
            ready.wait()
            return join(client, *pair)

    with ThreadPoolExecutor(max_workers=len(pairs)) as pool:
        return list(pool.map(join_as, pairs))


def reject(response, status, code):
    assert request_ok(response, status).json()["detail"]["code"] == code, response.text


def assert_unique_violation(db, statement, constraint):
    try:
        with db.begin_nested():
            db.execute(statement)
    except IntegrityError as error:
        assert error.orig.sqlstate == "23505", error
        assert error.orig.diag.constraint_name == constraint, error
    else:
        raise AssertionError(f"PostgreSQL did not enforce {constraint}")


@given("two waiting rooms with different hosts")
def two_rooms(context):
    context.client = TestClient(app)
    context.add_cleanup(context.client.close)
    context.rooms = [create_room(context), create_room(context)]


@when("one new player requests admission to both rooms concurrently")
def compete_for_rooms(context):
    context.player = member(context)
    context.responses = concurrent_joins([(room, context.player) for room in context.rooms])


@then("one admission succeeds and PostgreSQL stores only one membership for that player")
def exactly_one_membership(context):
    winner, loser = sorted(context.responses, key=lambda response: response.status_code)
    room_id = request_ok(winner).json()["id"]
    reject(loser, 409, "already_in_room")
    other = next(room["id"] for room in context.rooms if room["id"] != room_id)
    with SessionLocal() as db:
        membership = select(room_members.c.room_id).where(
            room_members.c.member_id == context.player[0]
        )
        assert db.scalars(membership).all() == [room_id]
        assert_unique_violation(db, insert(room_members).values(
            room_id=other, member_id=context.player[0]
        ), "uq_room_members_member_id")
        assert db.scalars(membership).all() == [room_id]


@then("PostgreSQL rejects changing one room code to the other room's code")
def duplicate_code(context):
    first, second = context.rooms
    assert first["code"] != second["code"]
    with SessionLocal() as db:
        assert_unique_violation(db, update(Room).where(Room.id == second["id"]).values(
            code=first["code"]
        ), "uq_rooms_code")
        assert db.get(Room, second["id"]).code == second["code"]


@given("a waiting room with nine members")
def nearly_full_room(context):
    context.client = TestClient(app)
    context.add_cleanup(context.client.close)
    context.room = create_room(context)
    for _ in range(8):
        response = request_ok(join(context.client, context.room, member(context)))
    assert len(response.json()["members"]) == 9


@when("two new players request admission to the room concurrently")
def compete_for_seat(context):
    context.contenders = [member(context), member(context)]
    context.responses = concurrent_joins([(context.room, player) for player in context.contenders])


@then("one admission succeeds and the room has exactly ten members")
def exactly_ten_members(context):
    winner, loser = sorted(range(2), key=lambda index: context.responses[index].status_code)
    assert len(request_ok(context.responses[winner]).json()["members"]) == 10
    reject(context.responses[loser], 409, "room_full")
    with SessionLocal() as db:
        members = db.scalars(select(room_members.c.member_id).where(
            room_members.c.room_id == context.room["id"]
        )).all()
    assert len(members) == 10
    assert context.contenders[winner][0] in members
    assert context.contenders[loser][0] not in members


@then("a new player's admission is refused and the live roster is unchanged")
def reject_live_join(context):
    code = context.ws_path.rsplit("/", 1)[-1]
    reject(join(context.client, {"code": code}, member(context)), 409, "room_in_progress")
    live = request_ok(context.client.get(f"{ROOMS}/{code}", headers=context.headers)).json()
    assert live["status"] == "in progress"
    assert {row["id"] for row in live["members"]} == {context.host[0], context.peer[0]}


@when("the member requests to close the room")
def member_close(context):
    context.room_path = context.join_path.removesuffix("/join")
    context.before_close = request_ok(
        context.client.get(context.room_path, headers=context.headers)
    ).json()
    context.response = context.client.delete(context.room_path, headers=bearer(context.peer[1]))


@then("the request is forbidden and the waiting room is unchanged")
def forbidden_close(context):
    reject(context.response, 403, "not_host")
    after = request_ok(context.client.get(context.room_path, headers=context.headers)).json()
    assert after == context.before_close and after["status"] == "waiting"


def membership_count(db, room_id):
    return db.scalar(select(func.count()).select_from(room_members).where(
        room_members.c.room_id == room_id
    ))


@then("PostgreSQL cascades a room deletion to its memberships")
def cascade_memberships(context):
    room_id = context.before_close["id"]
    # Roll back the direct deletion so the host can still leave through the API.
    with SessionLocal() as db:
        assert membership_count(db, room_id) == 2
        db.execute(delete(Room).where(Room.id == room_id))
        assert membership_count(db, room_id) == 0
        db.rollback()
        assert membership_count(db, room_id) == 2


@when("the host leaves the room")
def host_leaves(context):
    request_ok(context.client.post(f"{context.room_path}/leave", headers=context.headers), 204)


@then("the room and its memberships are gone")
def room_gone(context):
    reject(context.client.get(context.room_path, headers=bearer(context.peer[1])),
           404, "room_not_found")
    room_id = context.before_close["id"]
    with SessionLocal() as db:
        assert db.get(Room, room_id) is None
        assert membership_count(db, room_id) == 0
