"""Escenarios Gherkin de HU-06 (administración) y HU-07 (ingreso) sobre la API."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "rooms-api-tests-only-secret-not-for-production")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import Room, RoomStatus, User, room_members
from app.security import create_access_token

CONFIG = {"language": "spa", "difficulty": "medium", "rounds": 3, "timeLimitS": 90}


class RoomsApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            users = [
                User(username=f"user{n}", email=f"user{n}@example.test", hashed_password="x")
                for n in range(12)
            ]
            db.add_all(users)
            db.commit()
            self.ids = [user.id for user in users]

        def test_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(app.dependency_overrides.pop, get_db)
        self.addCleanup(self.client.close)

    def call(self, method, path, user, **kwargs):
        headers = {"Authorization": f"Bearer {create_access_token(self.ids[user])}"}
        return self.client.request(method, f"/api/v1/rooms{path}", headers=headers, **kwargs)

    def create(self, user=0, **overrides):
        response = self.call("POST", "", user, json={**CONFIG, **overrides})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def join(self, code, user):
        return self.call("POST", f"/{code}/join", user)

    def my_room(self, user):
        return self.call("GET", "/me", user).json()

    def assert_rejected(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json()["detail"]["code"], code)

    def set_status(self, code, status):
        with self.sessions() as db:
            db.execute(update(Room).where(Room.code == code).values(status=status))
            db.commit()

    # --- HU-06: administración de salas ---

    def test_creates_a_waiting_room_with_the_creator_as_host_and_member(self):
        room = self.create(type="quick")
        self.assertEqual(room["status"], "waiting")
        self.assertEqual(room["hostId"], self.ids[0])
        self.assertRegex(room["code"], r"^[A-Z0-9]{6}$")
        self.assertEqual(
            {key: room[key] for key in ("type", "language", "difficulty", "rounds", "timeLimitS")},
            {"type": "quick", "language": "spa", "difficulty": "medium", "rounds": 3, "timeLimitS": 90},
        )
        self.assertEqual(
            room["members"],
            [{"id": self.ids[0], "username": "user0", "isHost": True, "isReady": False}],
        )
        self.assertEqual(self.my_room(0)["code"], room["code"])
        self.assertNotEqual(self.create(user=1)["code"], room["code"])

    def test_defaults_to_a_private_single_round_room_with_automatic_time_limit(self):
        room = self.call("POST", "", 0, json={"language": "eng", "difficulty": "easy"}).json()
        self.assertEqual((room["type"], room["rounds"], room["timeLimitS"]), ("private", 1, None))

    def test_rejects_creating_a_room_while_belonging_to_another(self):
        mine = self.create()
        self.assert_rejected(self.call("POST", "", 0, json=CONFIG), 409, "already_in_room")
        other = self.create(user=1)
        self.assertEqual(self.join(other["code"], 2).status_code, 200)
        self.assert_rejected(self.call("POST", "", 2, json=CONFIG), 409, "already_in_room")
        self.assertEqual(self.my_room(0)["code"], mine["code"])
        self.assertEqual(self.my_room(2)["code"], other["code"])

    def test_host_updates_the_configuration(self):
        code = self.create()["code"]
        response = self.call(
            "PATCH", f"/{code}", 0,
            json={"language": "eng", "difficulty": "advanced", "rounds": 5, "timeLimitS": None},
        )
        self.assertEqual(response.status_code, 200, response.text)
        room = response.json()
        self.assertEqual(
            (room["language"], room["difficulty"], room["rounds"], room["timeLimitS"]),
            ("eng", "advanced", 5, None),
        )
        partial = self.call("PATCH", f"/{code}", 0, json={"rounds": 2}).json()
        self.assertEqual((partial["rounds"], partial["language"]), (2, "eng"))

    def test_member_cannot_update_the_configuration(self):
        code = self.create()["code"]
        self.join(code, 1)
        self.assert_rejected(self.call("PATCH", f"/{code}", 1, json={"rounds": 5}), 403, "not_host")
        self.assert_rejected(self.call("PATCH", f"/{code}", 2, json={"rounds": 5}), 403, "not_member")
        self.assertEqual(self.my_room(0)["rounds"], 3)

    def test_configuration_is_locked_while_a_match_is_running(self):
        code = self.create()["code"]
        self.set_status(code, RoomStatus.IN_PROGRESS)
        self.assert_rejected(self.call("PATCH", f"/{code}", 0, json={"rounds": 5}), 409, "room_in_progress")

    def test_host_kicks_a_player(self):
        code = self.create()["code"]
        self.join(code, 1)
        self.join(code, 2)
        response = self.call("DELETE", f"/{code}/members/{self.ids[1]}", 0)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([member["id"] for member in response.json()["members"]], [self.ids[0], self.ids[2]])
        self.assertIsNone(self.my_room(1))
        self.assert_rejected(self.call("GET", f"/{code}", 1), 403, "not_member")

    def test_only_the_host_kicks_and_only_real_members(self):
        code = self.create()["code"]
        self.join(code, 1)
        self.join(code, 2)
        self.assert_rejected(self.call("DELETE", f"/{code}/members/{self.ids[2]}", 1), 403, "not_host")
        self.assert_rejected(self.call("DELETE", f"/{code}/members/{self.ids[0]}", 0), 422, "cannot_kick_host")
        self.assert_rejected(self.call("DELETE", f"/{code}/members/{self.ids[5]}", 0), 404, "member_not_found")
        self.assertEqual(len(self.my_room(0)["members"]), 3)

    def test_host_closes_the_room_and_everyone_stops_belonging(self):
        code = self.create()["code"]
        self.join(code, 1)
        self.assert_rejected(self.call("DELETE", f"/{code}", 1), 403, "not_host")
        self.assertEqual(self.call("DELETE", f"/{code}", 0).status_code, 204)
        self.assertIsNone(self.my_room(0))
        self.assertIsNone(self.my_room(1))
        self.assert_rejected(self.join(code, 2), 404, "room_not_found")
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Room.status).where(Room.code == code)), RoomStatus.FINISHED)
        self.create(user=0)

    def test_room_is_deleted_when_the_host_leaves(self):
        code = self.create()["code"]
        self.join(code, 1)
        self.assertEqual(self.call("POST", f"/{code}/leave", 0).status_code, 204)
        self.assertIsNone(self.my_room(0))
        self.assertIsNone(self.my_room(1))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Room)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(room_members)), 0)

    def test_member_leaves_without_affecting_the_room(self):
        code = self.create()["code"]
        self.join(code, 1)
        self.assertEqual(self.call("POST", f"/{code}/leave", 1).status_code, 204)
        self.assertIsNone(self.my_room(1))
        self.assertEqual([member["id"] for member in self.my_room(0)["members"]], [self.ids[0]])
        self.assert_rejected(self.call("POST", f"/{code}/leave", 1), 403, "not_member")

    def test_rejects_invalid_configuration_and_unauthenticated_requests(self):
        for invalid in (
            {"rounds": 0}, {"rounds": 11}, {"timeLimitS": 29}, {"timeLimitS": 601},
            {"language": "fr"}, {"difficulty": "impossible"}, {"type": "public"},
            {"hostId": self.ids[1]}, {"code": "AAAAAA"}, {"status": "in progress"},
        ):
            with self.subTest(invalid=invalid):
                response = self.call("POST", "", 0, json={**CONFIG, **invalid})
                self.assertEqual(response.status_code, 422, response.text)
        self.assertIsNone(self.my_room(0))
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            response = self.client.post("/api/v1/rooms", json=CONFIG, headers=headers)
            self.assertIn(response.status_code, (401, 403))

    # --- HU-07: ingreso a una sala ---

    def test_joins_by_code_as_a_plain_member_and_sees_the_room(self):
        created = self.create()
        response = self.join(created["code"].lower(), 1)
        self.assertEqual(response.status_code, 200, response.text)
        room = response.json()
        self.assertEqual(room["hostId"], self.ids[0])
        self.assertEqual(
            room["members"],
            [
                {"id": self.ids[0], "username": "user0", "isHost": True, "isReady": False},
                {"id": self.ids[1], "username": "user1", "isHost": False, "isReady": False},
            ],
        )
        self.assertEqual((room["language"], room["rounds"], room["timeLimitS"]), ("spa", 3, 90))
        self.assertEqual(self.call("GET", f"/{created['code']}", 1).json(), room)
        # Reingresar a la propia sala no duplica la membresía.
        self.assertEqual(len(self.join(created["code"], 1).json()["members"]), 2)

    def test_rejects_an_invalid_code(self):
        self.create()
        response = self.join("ZZZZZZ", 1)
        self.assert_rejected(response, 404, "room_not_found")
        self.assertEqual(response.json()["detail"]["message"], "El código de sala no es válido.")
        self.assertEqual(self.join("no", 1).status_code, 422)
        self.assertIsNone(self.my_room(1))

    def test_room_accepts_ten_players_and_rejects_the_eleventh(self):
        code = self.create()["code"]
        for user in range(1, 9):
            self.assertEqual(self.join(code, user).status_code, 200)
        self.assertEqual(len(self.my_room(0)["members"]), 9)
        self.assertEqual(self.join(code, 9).status_code, 200)
        response = self.join(code, 10)
        self.assert_rejected(response, 409, "room_full")
        self.assertEqual(response.json()["detail"]["message"], "La sala está llena.")
        self.assertEqual(len(self.my_room(0)["members"]), 10)
        self.assertIsNone(self.my_room(10))

    def test_rejects_joining_while_a_match_is_running(self):
        code = self.create()["code"]
        self.set_status(code, RoomStatus.IN_PROGRESS)
        self.assert_rejected(self.join(code, 1), 409, "room_in_progress")
        self.assertIsNone(self.my_room(1))
        self.set_status(code, RoomStatus.WAITING)
        self.assertEqual(self.join(code, 1).status_code, 200)

    def test_rejects_belonging_to_two_rooms_at_once(self):
        first = self.create(user=0)["code"]
        second = self.create(user=1)["code"]
        self.join(first, 2)
        self.assert_rejected(self.join(second, 2), 409, "already_in_room")
        self.assert_rejected(self.join(second, 0), 409, "already_in_room")
        self.assertEqual(self.my_room(2)["code"], first)
        self.assertEqual(len(self.my_room(1)["members"]), 1)


if __name__ == "__main__":
    unittest.main()
