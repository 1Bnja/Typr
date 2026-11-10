import os
import unittest
from datetime import datetime, timezone

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
            "typed": "Hello world.",
            "keystrokes": 14,
            "errors": 2,
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
        self.assertEqual(saved["score"], 4)
        self.assertEqual(saved["textId"], self.text_id)
        self.assertEqual(saved["timeMs"], 30000)
        self.assertEqual(saved["ppm"], 5)
        self.assertEqual(saved["precisionPct"], 85.7)
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
            self.assertEqual(participant.score, 4)
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
            {"typed": ""},
            {"keystrokes": 0},
            {"errors": -1},
            {"errors": 20, "keystrokes": 10},
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
        # ppm=1, precisión=50% ⇒ score=0.5, que debe redondear a 1 (no a 0).
        response = self.save(
            {**self.payload, "timeMs": 144000, "keystrokes": 24, "errors": 12}
        )
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

    def test_selected_level_is_saved_and_history_filters_it(self):
        payload = {key: value for key, value in self.payload.items() if key != "textId"}
        payload["text"] = {"content": "casa mesa gato", "language": "spa"}
        easy = self.save({**payload, "difficulty": "easy"})
        medium = self.save({**payload, "difficulty": "medium"})
        self.assertEqual(easy.status_code, 201, easy.text)
        self.assertEqual(medium.status_code, 201, medium.text)
        self.assertEqual(easy.json()["difficulty"], "easy")
        self.assertEqual(medium.json()["difficulty"], "medium")
        self.assertNotEqual(easy.json()["textId"], medium.json()["textId"])
        rows = self.client.get(
            "/api/v1/matches/practice?difficulty=easy&language=spa",
            headers=self.headers,
        ).json()
        self.assertEqual([row["id"] for row in rows], [easy.json()["id"]])
        wrong = self.save(
            {**self.payload, "textId": easy.json()["textId"], "difficulty": "advanced"}
        )
        self.assertEqual(wrong.status_code, 422)
        retry = self.save(
            {**self.payload, "textId": easy.json()["textId"], "difficulty": "easy"}
        )
        self.assertEqual(retry.status_code, 201, retry.text)

    def add_ranked_match(
        self,
        user_id,
        finished_at,
        score=50,
        accuracy=95,
        time_ms=30000,
        difficulty=Difficulty.EASY,
        language=Language.SPA,
        progress=1,
    ):
        with self.sessions() as db:
            stored_text = Text(
                content="ranking words", language=language, difficulty=difficulty
            )
            game = Game(
                text=stored_text,
                mode="singleplayer",
                finished_at=finished_at,
                started_at=finished_at,
            )
            db.add(game)
            db.flush()
            db.add(
                GameParticipant(
                    game_id=game.id,
                    user_id=user_id,
                    ppm=55,
                    precision_pct=accuracy,
                    time_ms=time_ms,
                    progress=progress,
                    score=score,
                )
            )
            db.commit()
            return game.id

    def test_monthly_ranking_keeps_one_best_result_per_person(self):
        date = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
        self.add_ranked_match(self.user_ids[0], date, score=10)
        self.add_ranked_match(self.user_ids[0], date, score=90)
        self.add_ranked_match(self.user_ids[1], date, score=70)
        response = self.client.get(
            "/api/v1/matches/leaderboard?month=2026-11&difficulty=easy",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["timezone"], "America/Santiago")
        self.assertEqual([row["userId"] for row in result["entries"]], self.user_ids)
        self.assertEqual([row["score"] for row in result["entries"]], [90, 70])
        self.assertEqual([row["position"] for row in result["entries"]], [1, 2])
        self.assertNotIn("email", response.text)
        self.assertNotIn("hashedPassword", response.text)

    def test_monthly_ranking_uses_santiago_boundaries_and_filters(self):
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        zone = ZoneInfo("America/Santiago")
        start = datetime(2026, 11, 1, tzinfo=zone).astimezone(timezone.utc)
        end = datetime(2026, 12, 1, tzinfo=zone).astimezone(timezone.utc)
        self.add_ranked_match(
            self.user_ids[0], start - timedelta(microseconds=1), score=999
        )
        self.add_ranked_match(self.user_ids[0], start, score=30)
        self.add_ranked_match(self.user_ids[0], end, score=888)
        self.add_ranked_match(
            self.user_ids[1], start, score=777, difficulty=Difficulty.ADVANCED
        )
        self.add_ranked_match(self.user_ids[1], start, score=666, language=Language.ENG)
        self.add_ranked_match(self.user_ids[1], start, score=555, progress=0.5)
        response = self.client.get(
            "/api/v1/matches/leaderboard?month=2026-11&difficulty=easy&language=spa",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([row["score"] for row in response.json()["entries"]], [30])
        empty = self.client.get(
            "/api/v1/matches/leaderboard?month=2026-11&difficulty=expert",
            headers=self.headers,
        )
        self.assertEqual(empty.json()["entries"], [])

    def test_monthly_ranking_breaks_ties_by_accuracy_time_and_earliest_finish(self):
        from datetime import timedelta

        date = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
        self.add_ranked_match(
            self.user_ids[0], date, score=50, accuracy=96, time_ms=30000
        )
        self.add_ranked_match(
            self.user_ids[1], date, score=50, accuracy=97, time_ms=40000
        )
        path = "/api/v1/matches/leaderboard?month=2026-11&difficulty=easy"
        rows = self.client.get(path, headers=self.headers).json()["entries"]
        self.assertEqual(rows[0]["userId"], self.user_ids[1])
        self.add_ranked_match(
            self.user_ids[0], date, score=50, accuracy=97, time_ms=20000
        )
        rows = self.client.get(path, headers=self.headers).json()["entries"]
        self.assertEqual(rows[0]["userId"], self.user_ids[0])
        self.add_ranked_match(
            self.user_ids[1],
            date - timedelta(seconds=1),
            score=50,
            accuracy=97,
            time_ms=20000,
        )
        rows = self.client.get(path, headers=self.headers).json()["entries"]
        self.assertEqual(rows[0]["userId"], self.user_ids[1])

    def test_monthly_ranking_validates_queries_and_requires_auth(self):
        path = "/api/v1/matches/leaderboard"
        self.assertIn(self.client.get(path).status_code, (401, 403))
        for query in (
            "month=2026-13",
            "month=0000-01",
            "month=9999-12",
            "month=bad",
            "difficulty=invalid",
            "limit=101",
        ):
            with self.subTest(query=query):
                response = self.client.get(f"{path}?{query}", headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)
        response = self.client.get(path, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["entries"], [])


if __name__ == "__main__":
    unittest.main()
