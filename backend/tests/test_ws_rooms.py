"""Sala en vivo y carrera por WebSocket (HU-03 y el "listo" de HU-07)."""

import faulthandler
import os
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "ws-rooms-tests-only-secret-not-for-production")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import (
    Difficulty,
    Game,
    GameParticipant,
    Language,
    Room,
    RoomStatus,
    Text,
    User,
    room_members,
)
from app.security import create_access_token
from app.ws import rooms as rooms_ws

TEXTS = ("hola mundo", "casa mesa")


class RoomSocketTests(unittest.TestCase):
    def setUp(self):
        # Un mensaje que nunca llega dejaría el test esperando para siempre.
        faulthandler.dump_traceback_later(30, exit=True)
        self.addCleanup(faulthandler.cancel_dump_traceback_later)

        # Los sockets y los endpoints consultan la base a la vez desde varios
        # hilos, así que cada sesión necesita su propia conexión: un archivo
        # temporal en vez de la única conexión compartida de StaticPool.
        folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(folder.cleanup)
        self.engine = create_engine(
            f"sqlite+pysqlite:///{folder.name}/rooms.db",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            users = [
                User(username=name, email=f"{name}@example.test", hashed_password="x")
                for name in ("ana", "beto", "caro", "dani")
            ]
            db.add_all(users)
            db.add_all(
                Text(content=content, language=Language.SPA, difficulty=Difficulty.EASY)
                for content in TEXTS
            )
            db.commit()
            self.ids = {user.username: user.id for user in users}

        def test_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.addCleanup(self.release_database)
        self.addCleanup(app.dependency_overrides.pop, get_db)
        # Entrar al cliente deja todo en un mismo event loop, como en producción.
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.addCleanup(rooms_ws.hub.rooms.clear)
        for name in ("COUNTDOWN_S", "INTERMISSION_S"):
            patcher = mock.patch.object(rooms_ws, name, 0.05)
            patcher.start()
            self.addCleanup(patcher.stop)

    # --- utilidades ---

    def release_database(self):
        # Una partida cancelada puede seguir cerrando su sesión en otro hilo;
        # en Windows el archivo no se puede borrar mientras siga abierto.
        deadline = time.monotonic() + 5
        while self.engine.pool.checkedout() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.engine.dispose()

    def api(self, method, path, username, **kwargs):
        token = create_access_token(self.ids[username])
        return self.client.request(
            method,
            f"/api/v1/rooms{path}",
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )

    def room(self, host="ana", members=("beto",), **config):
        body = {"language": "spa", "difficulty": "easy", **config}
        response = self.api("POST", "", host, json=body)
        self.assertEqual(response.status_code, 201, response.text)
        code = response.json()["code"]
        for member in members:
            self.assertEqual(self.api("POST", f"/{code}/join", member).status_code, 200)
        return code

    def connect(self, username, code):
        socket = self.client.websocket_connect(f"/api/v1/ws/rooms/{code}")
        socket.__enter__()
        self.addCleanup(socket.__exit__, None, None, None)
        socket.send_json(
            {"type": "auth", "token": create_access_token(self.ids[username])}
        )
        return socket

    def expect(self, socket, kind):
        """Siguiente mensaje de ese tipo; lo que llegue antes se descarta."""
        while True:
            message = socket.receive_json()
            if message["type"] == kind:
                return message

    def state(self, socket):
        return self.expect(socket, "room_state")["room"]

    def lobby(self, code, *usernames):
        """Conecta a los jugadores en orden y consume los avisos de presencia."""
        sockets = []
        for username in usernames:
            socket = self.connect(username, code)
            self.state(socket)
            for other in sockets:
                self.assertEqual(self.expect(other, "player_joined")["username"], username)
                self.state(other)
            sockets.append(socket)
        return sockets

    def ready_lobby(self, code, host, *members):
        sockets = self.lobby(code, host, *members)
        for socket in sockets[1:]:
            socket.send_json({"type": "ready", "ready": True})
            for each in sockets:
                self.state(each)
        return sockets

    def start(self, sockets):
        """El anfitrión inicia; devuelve el race_start que recibe cada jugador."""
        sockets[0].send_json({"type": "start"})
        return [self.expect(socket, "race_start") for socket in sockets]

    def error(self, socket):
        return self.expect(socket, "error")["code"]

    def assert_closed(self, socket, code):
        with self.assertRaises(WebSocketDisconnect) as closed:
            while True:
                socket.receive_json()
        self.assertEqual(closed.exception.code, code)

    def room_status(self, code):
        with self.sessions() as db:
            return db.scalar(select(Room.status).where(Room.code == code))

    # --- conexión y presencia ---

    def test_only_authenticated_members_of_an_existing_room_connect(self):
        code = self.room()
        url = f"/api/v1/ws/rooms/{code}"
        for first_message in ({"type": "auth", "token": "invalid"}, {"type": "auth"}, {"type": "start"}):
            with self.subTest(first_message=first_message):
                with self.client.websocket_connect(url) as socket:
                    socket.send_json(first_message)
                    self.assert_closed(socket, rooms_ws.CLOSE_UNAUTHORIZED)
        self.assert_closed(self.connect("caro", code), rooms_ws.CLOSE_NOT_MEMBER)
        self.assert_closed(self.connect("ana", "ZZZZZZ"), rooms_ws.CLOSE_ROOM_GONE)
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/api/v1/ws/rooms/no"):
                pass
        self.assertEqual(rooms_ws.hub.rooms, {})

    def test_presence_is_announced_to_the_room(self):
        code = self.room()
        ana = self.connect("ana", code.lower())
        room = self.state(ana)
        self.assertEqual(room["code"], code)
        self.assertEqual(
            [(m["username"], m["isHost"], m["connected"]) for m in room["members"]],
            [("ana", True, True), ("beto", False, False)],
        )
        beto = self.connect("beto", code)
        self.assertEqual(
            self.expect(ana, "player_joined"),
            {"type": "player_joined", "userId": self.ids["beto"], "username": "beto"},
        )
        for socket in (ana, beto):
            self.assertEqual([m["connected"] for m in self.state(socket)["members"]], [True, True])
        beto.close()
        self.assertEqual(self.expect(ana, "player_left")["userId"], self.ids["beto"])
        self.assertEqual([m["connected"] for m in self.state(ana)["members"]], [True, False])

    def test_reconnecting_replaces_the_previous_socket(self):
        code = self.room()
        first, beto = self.lobby(code, "ana", "beto")
        second = self.connect("ana", code)
        self.state(second)
        self.assert_closed(first, rooms_ws.CLOSE_REPLACED)
        # Para Beto, Ana nunca salió: solo recibe el estado, sin player_left.
        self.assertEqual(beto.receive_json()["type"], "room_state")

    def test_rest_changes_reach_the_connected_sockets(self):
        code = self.room(members=())
        (ana,) = self.lobby(code, "ana")
        self.api("POST", f"/{code}/join", "beto")
        self.assertEqual(
            [(m["username"], m["connected"]) for m in self.state(ana)["members"]],
            [("ana", True), ("beto", False)],
        )
        self.api("PATCH", f"/{code}", "ana", json={"rounds": 4, "timeLimitS": 120})
        room = self.state(ana)
        self.assertEqual((room["rounds"], room["timeLimitS"]), (4, 120))

    # --- HU-07: jugador listo ---

    def test_ready_state_is_shown_to_every_member(self):
        code = self.room()
        ana, beto = self.lobby(code, "ana", "beto")
        beto.send_json({"type": "ready", "ready": True})
        for socket in (ana, beto):
            self.assertEqual([m["isReady"] for m in self.state(socket)["members"]], [False, True])
        beto.send_json({"type": "ready", "ready": False})
        self.assertEqual([m["isReady"] for m in self.state(ana)["members"]], [False, False])
        beto.send_json({"type": "ready", "ready": "yes"})
        self.assertEqual(self.error(beto), "invalid_message")

    # --- HU-03: inicio ---

    def test_only_the_host_starts_and_only_with_everyone_ready(self):
        code = self.room(members=())
        (ana,) = self.lobby(code, "ana")
        ana.send_json({"type": "start"})
        self.assertEqual(self.error(ana), "not_enough_players")

        self.api("POST", f"/{code}/join", "beto")
        self.state(ana)
        ana.send_json({"type": "start"})
        # Beto es miembro pero todavía no se conecta.
        self.assertEqual(self.error(ana), "players_not_ready")

        beto = self.connect("beto", code)
        self.state(beto)
        beto.send_json({"type": "start"})
        self.assertEqual(self.error(beto), "not_host")
        ana.send_json({"type": "start"})
        self.assertEqual(self.error(ana), "players_not_ready")
        self.assertEqual(self.room_status(code), RoomStatus.WAITING)

    def test_start_needs_texts_for_the_room_configuration(self):
        code = self.room(language="eng", difficulty="expert")
        ana, _ = self.ready_lobby(code, "ana", "beto")
        ana.send_json({"type": "start"})
        self.assertEqual(self.error(ana), "no_texts")
        self.assertEqual(self.room_status(code), RoomStatus.WAITING)

    def test_countdown_then_the_same_text_for_everyone(self):
        code = self.room()
        sockets = self.ready_lobby(code, "ana", "beto")
        sockets[0].send_json({"type": "start"})
        starts = []
        for socket in sockets:
            countdown = self.expect(socket, "countdown")
            self.assertEqual((countdown["round"], countdown["rounds"]), (1, 1))
            # El texto no viaja con la cuenta regresiva: llega recién después.
            self.assertNotIn("text", countdown)
            starts.append(self.expect(socket, "race_start"))
        self.assertEqual(starts[0]["text"], starts[1]["text"])
        self.assertIn(starts[0]["text"]["content"], TEXTS)
        self.assertEqual(starts[0]["timeLimitMs"], 2 * 200 * len(starts[0]["text"]["content"]))
        self.assertEqual(
            [(p["username"], p["progress"]) for p in starts[0]["players"]],
            [("ana", 0), ("beto", 0)],
        )
        self.assertEqual(self.room_status(code), RoomStatus.IN_PROGRESS)
        sockets[0].send_json({"type": "start"})
        self.assertEqual(self.error(sockets[0]), "room_in_progress")
        sockets[1].send_json({"type": "ready", "ready": False})
        self.assertEqual(self.error(sockets[1]), "room_in_progress")

    # --- HU-03: carrera y resultados ---

    def test_race_ends_when_everyone_finishes_and_saves_each_result(self):
        code = self.room()
        ana, beto = sockets = self.ready_lobby(code, "ana", "beto")
        text = self.start(sockets)[0]["text"]
        length = len(text["content"])

        beto.send_json({"type": "progress", "typed": 5, "errors": 1})
        self.assertEqual(
            self.expect(ana, "progress_update"),
            {"type": "progress_update", "userId": self.ids["beto"], "progress": 5 / length, "finished": False},
        )
        ana.send_json({"type": "progress", "typed": length, "errors": 0})
        self.assertTrue(self.expect(beto, "progress_update")["finished"])
        beto.send_json({"type": "progress", "typed": length, "errors": 2})

        ends = [self.expect(socket, "race_end") for socket in sockets]
        self.assertEqual(ends[0], ends[1])
        self.assertIsNone(ends[0]["nextRoundInS"])
        self.assertEqual(ends[0]["returnToRoomInS"], 15)
        first, second = ends[0]["results"]
        self.assertEqual([result["userId"] for result in ends[0]["matchResults"]],
                         [first["userId"], second["userId"]])
        self.assertEqual(ends[0]["matchResults"][0]["averageScore"], first["score"])
        self.assertEqual(ends[0]["matchResults"][0]["roundsPlayed"], 1)
        self.assertEqual((first["username"], first["position"], first["finished"]), ("ana", 1, True))
        self.assertEqual((second["username"], second["position"], second["finished"]), ("beto", 2, True))
        self.assertEqual((first["precisionPct"], first["progress"]), (100, 1))
        self.assertEqual(second["precisionPct"], round(length / (length + 2) * 1000) / 10)
        self.assertGreater(first["score"], second["score"])
        self.assertGreater(first["timeMs"], 0)

        with self.sessions() as db:
            game = db.scalar(select(Game))
            self.assertEqual(game.mode.value, "multiplayer")
            self.assertEqual(game.room.code, code)
            self.assertEqual(game.text_id, text["id"])
            self.assertIsNotNone(game.finished_at)
            saved = {
                p.user_id: p
                for p in db.scalars(select(GameParticipant).where(GameParticipant.game_id == game.id))
            }
            self.assertEqual(set(saved), {self.ids["ana"], self.ids["beto"]})
            for result in (first, second):
                row = saved[result["userId"]]
                self.assertEqual(
                    (row.position, row.score, row.ppm, row.time_ms, row.progress),
                    (result["position"], result["score"], result["ppm"], result["timeMs"], 1),
                )

    def test_room_returns_to_waiting_and_clears_ready_after_the_last_round(self):
        code = self.room()
        sockets = self.ready_lobby(code, "ana", "beto")
        length = len(self.start(sockets)[0]["text"]["content"])
        for socket in sockets:
            socket.send_json({"type": "progress", "typed": length, "errors": 0})
        for socket in sockets:
            self.expect(socket, "race_end")
            room = self.state(socket)
            self.assertEqual(room["status"], "waiting")
            self.assertEqual([m["isReady"] for m in room["members"]], [False, False])
        self.assertEqual(self.api("POST", f"/{code}/join", "caro").status_code, 200)

    def test_winner_faster_than_the_ideal_time_sets_the_text_record(self):
        code = self.room()
        sockets = self.ready_lobby(code, "ana", "beto")
        ana, beto = sockets
        text = self.start(sockets)[0]["text"]
        finish = {"type": "progress", "typed": len(text["content"]), "errors": 0}
        beto.send_json(finish)
        self.assertTrue(self.expect(ana, "progress_update")["finished"])
        ana.send_json(finish)
        winner, loser = self.expect(ana, "race_end")["results"]
        self.assertEqual((winner["username"], winner["isRecord"], loser["isRecord"]), ("beto", True, False))
        with self.sessions() as db:
            stored = db.get(Text, text["id"])
            self.assertEqual(stored.record_user_id, self.ids["beto"])
            self.assertEqual(stored.ideal_time_ms, winner["timeMs"])

    def test_race_ends_at_the_time_limit_with_proportional_scores(self):
        code = self.room()
        ana, beto = sockets = self.ready_lobby(code, "ana", "beto")
        with mock.patch.object(rooms_ws, "time_limit_ms", return_value=200):
            start = self.start(sockets)[0]
            self.assertEqual(start["timeLimitMs"], 200)
            length = len(start["text"]["content"])
            ana.send_json({"type": "progress", "typed": length, "errors": 0})
            beto.send_json({"type": "progress", "typed": length // 2, "errors": 0})
            began = time.monotonic()
            winner, unfinished = self.expect(beto, "race_end")["results"]
        self.assertGreater(time.monotonic() - began, 0.1)
        self.assertEqual((winner["username"], winner["finished"]), ("ana", True))
        self.assertEqual(
            (unfinished["username"], unfinished["finished"], unfinished["position"]),
            ("beto", False, 2),
        )
        self.assertEqual(
            (unfinished["timeMs"], unfinished["progress"]), (200, (length // 2) / length)
        )
        self.assertGreater(unfinished["score"], 0)
        self.assertEqual(self.state(beto)["status"], "waiting")
        self.assertEqual(self.room_status(code), RoomStatus.WAITING)

    def test_plays_every_round_with_a_different_text_before_reopening(self):
        code = self.room(rounds=2)
        sockets = self.ready_lobby(code, "ana", "beto")
        sockets[0].send_json({"type": "start"})
        played = []
        round_results = []
        for round_number in (1, 2):
            starts = [self.expect(socket, "race_start") for socket in sockets]
            self.assertEqual((starts[0]["round"], starts[0]["rounds"]), (round_number, 2))
            played.append(starts[0]["text"]["content"])
            # Con rondas pendientes la sala sigue en curso y no admite ingresos.
            response = self.api("POST", f"/{code}/join", "caro")
            self.assertEqual(response.json()["detail"]["code"], "room_in_progress")
            for socket in sockets:
                socket.send_json({"type": "progress", "typed": len(played[-1]), "errors": 0})
            end = [self.expect(socket, "race_end") for socket in sockets][0]
            self.assertEqual(end["nextRoundInS"], None if round_number == 2 else 0.05)
            round_results.append(end["results"])
            if round_number == 1:
                self.assertNotIn("matchResults", end)
            else:
                self.assertEqual(end["returnToRoomInS"], 15)
                final = end["matchResults"]
                self.assertEqual([item["position"] for item in final], [1, 2])
                self.assertEqual(
                    [item["averageScore"] for item in final],
                    sorted((item["averageScore"] for item in final), reverse=True),
                )
                for item in final:
                    played_by_user = [
                        result for results in round_results for result in results
                        if result["userId"] == item["userId"]
                    ]
                    self.assertEqual(item["roundsPlayed"], 2)
                    for key, source in (("averageScore", "score"), ("averagePpm", "ppm"),
                                        ("averagePrecisionPct", "precisionPct"), ("averageTimeMs", "timeMs"),
                                        ("averageProgress", "progress")):
                        self.assertAlmostEqual(
                            item[key], sum(result[source] for result in played_by_user) / 2,
                        )
        self.assertEqual(sorted(played), sorted(TEXTS))
        self.assertEqual(self.state(sockets[0])["status"], "waiting")
        with self.sessions() as db:
            games = db.scalars(select(Game)).all()
            self.assertEqual(len(games), 2)
            self.assertEqual({game.mode.value for game in games}, {"multiplayer"})
        self.assertEqual(self.api("POST", f"/{code}/join", "caro").status_code, 200)

    def test_invalid_progress_is_rejected_and_never_broadcast(self):
        code = self.room()
        ana, beto = sockets = self.ready_lobby(code, "ana", "beto")
        beto.send_json({"type": "progress", "typed": 1, "errors": 0})
        beto.send_json({"type": "otro"})
        # Fuera de una carrera el avance se ignora; solo responde el mensaje desconocido.
        self.assertEqual(beto.receive_json()["code"], "invalid_message")

        length = len(self.start(sockets)[0]["text"]["content"])
        beto.send_json({"type": "progress", "typed": 4, "errors": 2})
        self.expect(ana, "progress_update")
        for invalid in (
            {"typed": length + 1, "errors": 2},
            {"typed": 3, "errors": 2},
            {"typed": 5, "errors": 1},
            {"typed": 5.5, "errors": 2},
            {"typed": True, "errors": 2},
            {"typed": 5},
        ):
            with self.subTest(invalid=invalid):
                beto.send_json({"type": "progress", **invalid})
                self.assertEqual(self.error(beto), "invalid_message")
        beto.send_json({"type": "progress", "typed": 6, "errors": 2})
        # Lo siguiente que ve Ana es el avance válido: nada inválido se reenvió.
        self.assertEqual(ana.receive_json()["progress"], 6 / length)

    def test_reconnecting_mid_race_resumes_from_the_own_progress(self):
        code = self.room()
        ana, beto = sockets = self.ready_lobby(code, "ana", "beto")
        text = self.start(sockets)[0]["text"]
        ana.send_json({"type": "progress", "typed": 3, "errors": 1})
        self.expect(beto, "progress_update")

        again = self.connect("ana", code)
        resumed = self.expect(again, "race_start")
        self.assertEqual(resumed["text"], text)
        self.assertEqual(resumed["you"], {"typed": 3, "errors": 1})
        self.assertEqual(resumed["players"][0]["progress"], 3 / len(text["content"]))
        self.assertGreaterEqual(resumed["elapsedMs"], 0)

    def test_reconnecting_after_finishing_keeps_the_recorded_time(self):
        code = self.room()
        ana, beto = sockets = self.ready_lobby(code, "ana", "beto")
        length = len(self.start(sockets)[0]["text"]["content"])
        ana.send_json({"type": "progress", "typed": length, "errors": 0})
        self.assertTrue(self.expect(beto, "progress_update")["finished"])
        first = self.expect(self.connect("ana", code), "race_start")
        second = self.expect(self.connect("ana", code), "race_start")
        self.assertEqual(first["you"]["typed"], length)
        self.assertGreaterEqual(first["you"]["finishedMs"], 0)
        self.assertEqual(first["you"]["finishedMs"], second["you"]["finishedMs"])

    def test_match_is_abandoned_when_everyone_disconnects(self):
        code = self.room()
        sockets = self.ready_lobby(code, "ana", "beto")
        self.start(sockets)
        for socket in sockets:
            socket.close()
        deadline = time.monotonic() + 5
        while self.room_status(code) != RoomStatus.WAITING and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(self.room_status(code), RoomStatus.WAITING)
        self.assertEqual(rooms_ws.hub.rooms, {})

    def test_room_stuck_in_progress_recovers_on_the_next_connection(self):
        code = self.room()
        with self.sessions() as db:
            db.execute(update(Room).where(Room.code == code).values(status=RoomStatus.IN_PROGRESS))
            db.execute(update(room_members).values(is_ready=True))
            db.commit()
        room = self.state(self.connect("ana", code))
        self.assertEqual(room["status"], "waiting")
        self.assertEqual([m["isReady"] for m in room["members"]], [False, False])

    # --- HU-06: salidas, expulsión y cierre con sockets abiertos ---

    def test_kicked_player_is_disconnected_and_removed_for_everyone(self):
        code = self.room(members=("beto", "caro"))
        ana, beto, caro = self.lobby(code, "ana", "beto", "caro")
        self.api("DELETE", f"/{code}/members/{self.ids['beto']}", "ana")
        self.assert_closed(beto, rooms_ws.CLOSE_REMOVED)
        for socket in (ana, caro):
            self.assertEqual(self.expect(socket, "player_left")["userId"], self.ids["beto"])
            self.assertEqual([m["username"] for m in self.state(socket)["members"]], ["ana", "caro"])
        self.assert_closed(self.connect("beto", code), rooms_ws.CLOSE_NOT_MEMBER)

    def test_everyone_is_disconnected_when_the_host_leaves_or_closes(self):
        for action in (("POST", "/leave"), ("DELETE", "")):
            with self.subTest(action=action):
                code = self.room()
                ana, beto = self.lobby(code, "ana", "beto")
                method, path = action
                self.assertEqual(self.api(method, f"/{code}{path}", "ana").status_code, 204)
                for socket in (ana, beto):
                    self.assertEqual(self.expect(socket, "room_closed"), {"type": "room_closed"})
                    self.assert_closed(socket, rooms_ws.CLOSE_ROOM_GONE)
                self.assertNotIn(code, rooms_ws.hub.rooms)

    def test_player_leaving_mid_race_does_not_block_the_rest(self):
        code = self.room(members=("beto", "caro"))
        ana, beto, caro = sockets = self.ready_lobby(code, "ana", "beto", "caro")
        length = len(self.start(sockets)[0]["text"]["content"])
        ana.send_json({"type": "progress", "typed": length, "errors": 0})
        self.assertTrue(self.expect(beto, "progress_update")["finished"])
        beto.send_json({"type": "progress", "typed": length, "errors": 0})
        self.assertEqual(self.api("POST", f"/{code}/leave", "caro").status_code, 204)
        self.assert_closed(caro, rooms_ws.CLOSE_REMOVED)
        results = self.expect(ana, "race_end")["results"]
        self.assertEqual([result["username"] for result in results], ["ana", "beto"])


if __name__ == "__main__":
    unittest.main()
