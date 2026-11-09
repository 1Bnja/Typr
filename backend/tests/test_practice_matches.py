import os
import unittest
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "practice-tests-only-secret-not-for-production")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import Difficulty, Game, GameParticipant, Language, Text, User
from app.security import create_access_token


class PracticeMatchTests(unittest.TestCase):
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
                User(
                    username=name,
                    email=f"{name}@example.test",
                    hashed_password="test-only",
                )
                for name in ("first", "second")
            ]
            stored_text = Text(
                content="Hello world.",
                language=Language.ENG,
                difficulty=Difficulty.EASY,
            )
            db.add_all([*users, stored_text])
            db.commit()
            self.user_ids = [user.id for user in users]
            self.text_id = stored_text.id

        def test_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        self.headers = {
            "Authorization": f"Bearer {create_access_token(self.user_ids[0])}"
        }
        self.other_headers = {
            "Authorization": f"Bearer {create_access_token(self.user_ids[1])}"
        }
        self.payload = {
            "textId": self.text_id,
            "timeMs": 30000,
            "ppm": 40,
            "precisionPct": 95,
            "progress": 1,
        }
        self.addCleanup(self.engine.dispose)
        self.addCleanup(app.dependency_overrides.pop, get_db)
        self.addCleanup(self.client.close)

    def save(self, payload=None, headers=None):
        return self.client.post(
            "/api/v1/matches/practice",
            json=self.payload if payload is None else payload,
            headers=self.headers if headers is None else headers,
        )

    def count(self, model):
        with self.sessions() as db:
            return db.scalar(select(func.count()).select_from(model))

    def test_saves_authenticated_user_and_returns_persisted_result(self):
        response = self.save()
        self.assertEqual(response.status_code, 201, response.text)
        saved = response.json()
        self.assertEqual(saved["score"], 38)
        self.assertEqual(saved["textId"], self.text_id)
        self.assertEqual(saved["timeMs"], 30000)
        self.assertEqual(saved["ppm"], 40)
        self.assertEqual(saved["precisionPct"], 95)
        self.assertEqual(saved["language"], "eng")
        self.assertAlmostEqual(
            (
                datetime.fromisoformat(saved["finishedAt"])
                - datetime.fromisoformat(saved["startedAt"])
            ).total_seconds(),
            30,
        )
        with self.sessions() as db:
            game = db.get(Game, saved["id"])
            participant = db.scalar(select(GameParticipant))
            self.assertEqual(game.mode.value, "singleplayer")
            self.assertIsNone(game.room_id)
            self.assertEqual(participant.game_id, game.id)
            self.assertEqual(participant.user_id, self.user_ids[0])
            self.assertEqual(participant.score, 38)
            self.assertEqual(participant.position, 1)

    def test_local_text_is_normalized_classified_and_reused(self):
        payload = {key: value for key, value in self.payload.items() if key != "textId"}
        payload["text"] = {"content": "  casa   mesa gato  ", "language": "spa"}
        first = self.save(payload)
        self.assertEqual(first.status_code, 201, first.text)
        second = self.save(payload)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.json()["textId"], second.json()["textId"])
        self.assertNotEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(self.count(Text), 2)
        self.assertEqual(self.count(Game), 2)
        with self.sessions() as db:
            stored = db.get(Text, first.json()["textId"])
            self.assertEqual(stored.content, "casa mesa gato")
            self.assertEqual(stored.language.value, "spa")
            self.assertIn(
                stored.difficulty.value, [level.value for level in Difficulty]
            )

    def test_rejects_missing_or_invalid_authentication(self):
        for headers in ({}, {"Authorization": "Bearer invalid-token"}):
            with self.subTest(headers=headers):
                self.assertIn(self.save(headers=headers).status_code, (401, 403))
                response = self.client.get("/api/v1/matches/practice", headers=headers)
                self.assertIn(response.status_code, (401, 403))
        self.assertEqual(self.count(Game), 0)

    def test_rejects_unknown_text_and_invalid_requests(self):
        self.assertEqual(self.save({**self.payload, "textId": 999999}).status_code, 404)
        invalid = [
            {"timeMs": 0},
            {"timeMs": 2_147_483_648},
            {"ppm": -1},
            {"ppm": 2_147_483_648},
            {"precisionPct": 101},
            {"precisionPct": -1},
            {"progress": 2},
            {"textId": None},
            {"text": {"content": "Hola", "language": "spa"}},
            {"userId": self.user_ids[1]},
            {"score": 9999},
        ]
        for update in invalid:
            with self.subTest(update=update):
                response = self.save({**self.payload, **update})
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.count(Game), 0)
        self.assertEqual(self.count(GameParticipant), 0)

    def test_local_text_uses_existing_character_validation(self):
        base = {key: value for key, value in self.payload.items() if key != "textId"}
        for content, language in (
            ("   ", "spa"),
            ("Hola 😀", "spa"),
            ("pingüino", "eng"),
        ):
            with self.subTest(content=content):
                response = self.save(
                    {**base, "text": {"content": content, "language": language}}
                )
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.count(Text), 1)
        self.assertEqual(self.count(Game), 0)

    def test_history_is_private_newest_first_and_paginated(self):
        saved = [self.save().json() for _ in range(3)]
        other = self.save(headers=self.other_headers)
        self.assertEqual(other.status_code, 201)
        response = self.client.get(
            "/api/v1/matches/practice?limit=2&offset=1", headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [row["id"] for row in response.json()], [saved[1]["id"], saved[0]["id"]]
        )
        response = self.client.get(
            "/api/v1/matches/practice", headers=self.other_headers
        )
        self.assertEqual([row["id"] for row in response.json()], [other.json()["id"]])
        for query in ("limit=0", "limit=101", "offset=-1"):
            self.assertEqual(
                self.client.get(
                    f"/api/v1/matches/practice?{query}", headers=self.headers
                ).status_code,
                422,
            )

    def test_history_is_empty_for_a_new_user(self):
        response = self.client.get("/api/v1/matches/practice", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_rounds_score_like_the_frontend(self):
        response = self.save({**self.payload, "ppm": 1, "precisionPct": 50})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["score"], 1)

    def test_database_failure_rolls_back_text_game_and_participant(self):
        with self.engine.begin() as connection:
            connection.execute(
                text("""CREATE TRIGGER reject_participant BEFORE INSERT ON game_participants
                BEGIN SELECT RAISE(ABORT, 'deliberate test failure'); END""")
            )
        payload = {key: value for key, value in self.payload.items() if key != "textId"}
        payload["text"] = {"content": "Rollback probe.", "language": "eng"}
        response = self.save(payload)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertNotIn("deliberate test failure", response.text)
        self.assertEqual(self.count(Text), 1)
        self.assertEqual(self.count(Game), 0)
        self.assertEqual(self.count(GameParticipant), 0)
        with self.engine.begin() as connection:
            connection.execute(text("DROP TRIGGER reject_participant"))
        self.assertEqual(self.save(payload).status_code, 201)


if __name__ == "__main__":
    unittest.main()
