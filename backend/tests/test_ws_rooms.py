import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "ws-rooms-tests-only-secret-not-for-production")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import User
from app.security import create_access_token
from app.ws import rooms as rooms_ws


class RoomSocketTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            users = [
                User(username=name, email=f"{name}@example.test", hashed_password="x")
                for name in ("ana", "beto", "caro")
            ]
            db.add_all(users)
            db.commit()
            self.ids = {user.username: user.id for user in users}

        def test_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(app.dependency_overrides.pop, get_db)
        self.addCleanup(self.client.close)
        self.addCleanup(rooms_ws.hub.rooms.clear)

    def connect(self, username, code="SALA1"):
        socket = self.client.websocket_connect(f"/api/v1/ws/rooms/{code}")
        socket.__enter__()
        self.addCleanup(socket.__exit__, None, None, None)
        socket.send_json(
            {"type": "auth", "token": create_access_token(self.ids[username])}
        )
        return socket

    def test_progress_is_synchronized_between_two_players(self):
        ana = self.connect("ana")
        state = ana.receive_json()
        self.assertEqual(state["type"], "room_state")
        self.assertEqual([p["username"] for p in state["players"]], ["ana"])

        beto = self.connect("beto")
        self.assertEqual(
            [p["username"] for p in beto.receive_json()["players"]], ["ana", "beto"]
        )
        joined = ana.receive_json()
        self.assertEqual(joined["type"], "player_joined")
        self.assertEqual(joined["player"]["userId"], self.ids["beto"])

        beto.send_json({"type": "progress", "progress": 0.25})
        self.assertEqual(
            ana.receive_json(),
            {"type": "progress_update", "userId": self.ids["beto"], "progress": 0.25},
        )
        ana.send_json({"type": "progress", "progress": 1})
        self.assertEqual(
            beto.receive_json(),
            {"type": "progress_update", "userId": self.ids["ana"], "progress": 1.0},
        )

        beto.close()
        self.assertEqual(
            ana.receive_json(), {"type": "player_left", "userId": self.ids["beto"]}
        )

    def test_late_joiner_sees_current_progress(self):
        ana = self.connect("ana")
        ana.receive_json()
        ana.send_json({"type": "progress", "progress": 0.6})
        # El eco de error confirma que el servidor ya procesó el avance previo.
        ana.send_json({"type": "ping"})
        self.assertEqual(ana.receive_json()["type"], "error")

        state = self.connect("beto").receive_json()
        self.assertEqual(state["players"][0]["progress"], 0.6)

    def test_rooms_are_isolated(self):
        ana = self.connect("ana", "SALA1")
        ana.receive_json()
        caro = self.connect("caro", "SALA2")
        caro.receive_json()
        beto = self.connect("beto", "SALA1")
        beto.receive_json()
        self.assertEqual(ana.receive_json()["type"], "player_joined")

        caro.send_json({"type": "progress", "progress": 0.9})
        beto.send_json({"type": "progress", "progress": 0.1})
        # A Ana solo le llega lo de su sala, nunca el avance de Caro.
        self.assertEqual(ana.receive_json()["userId"], self.ids["beto"])

    def test_invalid_messages_are_rejected_without_broadcast(self):
        ana = self.connect("ana")
        ana.receive_json()
        beto = self.connect("beto")
        beto.receive_json()
        ana.receive_json()

        for message in (
            {"type": "progress", "progress": 2},
            {"type": "progress", "progress": -0.1},
            {"type": "progress", "progress": "0.5"},
            {"type": "progress", "progress": True},
            {"type": "progress"},
            {"type": "otro"},
            [1, 2],
        ):
            with self.subTest(message=message):
                beto.send_json(message)
                self.assertEqual(beto.receive_json()["type"], "error")
        beto.send_text("no es json")
        self.assertEqual(beto.receive_json()["type"], "error")

        beto.send_json({"type": "progress", "progress": 0.5})
        # Lo primero que recibe Ana es el avance válido: nada inválido se reenvió.
        self.assertEqual(ana.receive_json()["progress"], 0.5)

    def test_rejects_connections_without_a_valid_token(self):
        for first_message in (
            {"type": "auth", "token": "invalid"},
            {"type": "auth"},
            {"type": "progress", "progress": 0.5},
        ):
            with self.subTest(first_message=first_message):
                with self.client.websocket_connect("/api/v1/ws/rooms/SALA1") as socket:
                    socket.send_json(first_message)
                    with self.assertRaises(WebSocketDisconnect) as closed:
                        socket.receive_json()
                    self.assertEqual(closed.exception.code, rooms_ws.CLOSE_UNAUTHORIZED)
        self.assertEqual(rooms_ws.hub.rooms, {})

    def test_reconnection_replaces_the_previous_socket_and_keeps_progress(self):
        first = self.connect("ana")
        first.receive_json()
        beto = self.connect("beto")
        beto.receive_json()
        first.receive_json()
        first.send_json({"type": "progress", "progress": 0.4})
        beto.receive_json()

        second = self.connect("ana")
        state = second.receive_json()
        self.assertEqual(
            {p["username"]: p["progress"] for p in state["players"]},
            {"ana": 0.4, "beto": 0.0},
        )
        with self.assertRaises(WebSocketDisconnect) as closed:
            first.receive_json()
        self.assertEqual(closed.exception.code, rooms_ws.CLOSE_REPLACED)

        # Para Beto, Ana nunca salió: no hay player_left ni player_joined.
        second.send_json({"type": "progress", "progress": 0.5})
        self.assertEqual(beto.receive_json()["type"], "progress_update")

    def test_room_is_full_after_the_player_limit(self):
        original = rooms_ws.MAX_PLAYERS
        rooms_ws.MAX_PLAYERS = 2
        self.addCleanup(setattr, rooms_ws, "MAX_PLAYERS", original)
        self.connect("ana").receive_json()
        self.connect("beto").receive_json()
        caro = self.connect("caro")
        with self.assertRaises(WebSocketDisconnect) as closed:
            caro.receive_json()
        self.assertEqual(closed.exception.code, rooms_ws.CLOSE_ROOM_FULL)

    def test_rejects_malformed_room_codes(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/api/v1/ws/rooms/a!"):
                pass


if __name__ == "__main__":
    unittest.main()
