"""Verifica que el esquema PostgreSQL desplegable soporta multiplayer."""

import unittest

from test_text_postgresql import ENABLED, require_local_fixture


@unittest.skipUnless(ENABLED, "Requires the isolated docker-compose.test.yml fixture.")
class PostgreSQLRoomsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_local_fixture()
        from alembic.script import ScriptDirectory
        from fastapi.testclient import TestClient
        from sqlalchemy import text

        from app.commands.migrate import alembic_config
        from app.database import SessionLocal
        from app.main import app
        cls.SessionLocal = staticmethod(SessionLocal)
        cls.client = TestClient(app)
        cls.addClassCleanup(cls.client.close)
        cls.head = ScriptDirectory.from_config(alembic_config()).get_current_head()
        with cls.SessionLocal() as db:
            cls.revision = db.scalar(text("SELECT version_num FROM alembic_version"))

    def setUp(self):
        from app.models import User
        from app.services.sessions import issue_session

        with self.SessionLocal() as db:
            user = User(
                username="rooms_postgres",
                email="rooms-postgres@example.test",
                hashed_password="test-only",
            )
            db.add(user)
            db.commit()
            self.user_id = user.id
            self.addCleanup(self.clean_up_host)
            self.headers = {"Authorization": f"Bearer {issue_session(db, self.user_id)}"}

    def clean_up_host(self):
        from sqlalchemy import delete

        from app.models import Room, User

        with self.SessionLocal() as db:
            db.execute(delete(Room).where(Room.host_id == self.user_id))
            db.execute(delete(User).where(User.id == self.user_id))
            db.commit()

    def test_creates_room_on_migrated_postgresql_schema(self):
        self.assertEqual(self.revision, self.head)
        room = self.create_room()
        self.assertRegex(room["code"], r"^[A-Z0-9]{6}$")
        self.assertEqual(room["rounds"], 3)
        self.assertEqual(room["timeLimitS"], 90)
        self.assertFalse(room["members"][0]["isReady"])

    def create_room(self):
        response = self.client.post(
            "/api/v1/rooms",
            headers=self.headers,
            json={
                "language": "spa",
                "difficulty": "easy",
                "rounds": 3,
                "timeLimitS": 90,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_each_player_reads_their_persisted_result_from_the_same_race(self):
        from fastapi.testclient import TestClient
        from sqlalchemy import delete, select

        from app.models import Game, Room, Text, User
        from app.services.sessions import issue_session

        self.assertEqual(self.revision, self.head)
        with self.SessionLocal() as db:
            players = [
                User(username=name, email=f"{name}@example.test", hashed_password="test-only")
                for name in ("race_stats_host", "race_stats_guest")
            ]
            text = Text(content="Cada jugador tiene su propio resultado.", language="spa", difficulty="easy")
            db.add_all([*players, text])
            db.commit()
            player_ids = [player.id for player in players]
            text_id = text.id

        def clean_up_race():
            with self.SessionLocal() as db:
                room_ids = select(Room.id).where(Room.host_id == player_ids[0])
                db.execute(delete(Game).where(Game.room_id.in_(room_ids)))
                db.execute(delete(Room).where(Room.host_id == player_ids[0]))
                db.execute(delete(Text).where(Text.id == text_id))
                db.execute(delete(User).where(User.id.in_(player_ids)))
                db.commit()

        self.addCleanup(clean_up_race)
        with self.SessionLocal() as db:
            tokens = [issue_session(db, player_id) for player_id in player_ids]
        headers = [{"Authorization": f"Bearer {token}"} for token in tokens]

        def receive(socket, kind):
            while True:
                message = socket.receive_json()
                if message["type"] == kind:
                    return message
                self.assertNotEqual(message["type"], "error", message)

        with TestClient(self.client.app) as client:
            room = client.post(
                "/api/v1/rooms", headers=headers[0],
                json={"language": "spa", "difficulty": "easy", "rounds": 1, "timeLimitS": 90},
            )
            self.assertEqual(room.status_code, 201, room.text)
            code = room.json()["code"]
            joined = client.post(f"/api/v1/rooms/{code}/join", headers=headers[1])
            self.assertEqual(joined.status_code, 200, joined.text)

            path = f"/api/v1/ws/rooms/{code}"
            with client.websocket_connect(path) as host, client.websocket_connect(path) as guest:
                for socket, token in zip((host, guest), tokens, strict=True):
                    socket.send_json({"type": "auth", "token": token})
                    receive(socket, "room_state")
                guest.send_json({"type": "ready", "ready": True})
                receive(guest, "room_state")
                host.send_json({"type": "start"})
                length = len(receive(host, "race_start")["text"]["content"])
                receive(guest, "race_start")
                host.send_json({"type": "progress", "typed": length, "errors": 0})
                self.assertTrue(receive(guest, "progress_update")["finished"])
                guest.send_json({"type": "progress", "typed": length, "errors": 2})
                finished = receive(host, "race_end")
                self.assertIsNone(finished["nextRoundInS"])

                with self.SessionLocal() as db:
                    game = db.scalars(select(Game).join(Room).where(Room.code == code)).one()
                    self.assertIsNotNone(game.finished_at)
                    game_id = game.id

                results = {result["userId"]: result for result in finished["results"]}
                self.assertEqual(set(results), set(player_ids))
                self.assertEqual([results[user_id]["position"] for user_id in player_ids], [1, 2])
                self.assertEqual(results[player_ids[0]]["precisionPct"], 100)
                self.assertLess(results[player_ids[1]]["precisionPct"], 100)
                for player_id, auth in zip(player_ids, headers, strict=True):
                    with self.subTest(player_id=player_id):
                        response = client.get("/api/v1/users/me/stats", headers=auth)
                        self.assertEqual(response.status_code, 200, response.text)
                        entries = [entry for entry in response.json()["history"] if entry["gameId"] == game_id]
                        self.assertEqual(len(entries), 1)
                        entry, result = entries[0], results[player_id]
                        self.assertEqual(entry["mode"], "multiplayer")
                        for metric in ("position", "ppm", "score", "timeMs", "progress"):
                            self.assertEqual(entry[metric], result[metric], metric)
                        self.assertAlmostEqual(entry["precisionPct"], result["precisionPct"], places=4)

    def test_multiplayer_record_must_beat_baseline_and_then_the_stored_mark(self):
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import delete, select

        from app.models import Game, Room, Text, User
        from app.services.race import Racer, build_results
        from app.services.rooms import pick_text, save_race
        from app.text_enums import Difficulty, Language

        self.assertEqual(self.revision, self.head)
        room_code = self.create_room()["code"]
        content = "Este texto es una prueba local."
        with self.SessionLocal() as db:
            room_id = db.scalar(select(Room.id).where(Room.code == room_code))
            challenger = User(
                username="rooms_challenger",
                email="rooms-record-challenger@example.test",
                hashed_password="test-only",
            )
            text = Text(content=content, language="spa", difficulty="easy")
            db.add_all([challenger, text])
            db.commit()
            text_id, challenger_id = text.id, challenger.id
            excluded_ids = list(db.scalars(select(Text.id).where(Text.id != text_id)))

        def clean_up_record_fixture():
            with self.SessionLocal() as db:
                db.execute(delete(Game).where(Game.room_id == room_id))
                db.execute(delete(Text).where(Text.id == text_id))
                db.execute(delete(User).where(User.id == challenger_id))
                db.commit()

        self.addCleanup(clean_up_record_fixture)
        baseline = 6200  # 31 characters at five characters per second.
        host_id = self.user_id
        cases = (
            ("slower than baseline", baseline, 6201, host_id, False, (None, None)),
            ("equal to baseline", baseline, 6200, host_id, False, (None, None)),
            ("faster than baseline", baseline, 6199, host_id, True, (6199, host_id)),
            ("slower than stored mark", 6199, 6200, challenger_id, False, (6199, host_id)),
            ("equal to stored mark", 6199, 6199, challenger_id, False, (6199, host_id)),
            ("faster than stored mark", 6199, 6198, challenger_id, True, (6198, challenger_id)),
        )
        for label, ideal, elapsed, winner, is_record, expected in cases:
            with self.subTest(case=label):
                runner_up = challenger_id if winner == host_id else host_id
                started_at = datetime.now(timezone.utc)
                with self.SessionLocal() as db:
                    race_text = pick_text(db, Language.SPA, Difficulty.EASY, excluded_ids)
                    self.assertIsNotNone(race_text)
                    self.assertEqual(race_text.id, text_id)
                    self.assertEqual(race_text.ideal_time_ms, ideal)
                    duration = elapsed + 100
                    results = build_results(
                        race_text,
                        duration,
                        [
                            Racer(runner_up, "Runner-up", len(content), finished_ms=duration),
                            Racer(winner, "Winner", len(content), finished_ms=elapsed),
                        ],
                    )
                    self.assertEqual(
                        [(r.user_id, r.time_ms, r.is_record) for r in results],
                        [(winner, elapsed, is_record), (runner_up, duration, False)],
                    )
                    save_race(
                        db, room_id, race_text, started_at,
                        started_at + timedelta(milliseconds=duration), results,
                    )

                with self.SessionLocal() as db:
                    saved = db.get(Text, text_id)
                    self.assertEqual((saved.ideal_time_ms, saved.record_user_id), expected)


if __name__ == "__main__":
    unittest.main()
