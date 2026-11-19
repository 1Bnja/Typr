"""Escenarios Gherkin de HU-05 (analítica personal) sobre la API."""

import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "user-stats-tests-only-secret-not-for-production")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import (
    Difficulty,
    Game,
    GameMode,
    GameParticipant,
    Language,
    Room,
    Text,
    User,
)
from app.services.sessions import issue_session

START = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


class UserStatsTests(unittest.TestCase):
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
                User(username=name, email=f"{name}@example.test", hashed_password="x")
                for name in ("ana", "beto", "nuevo")
            ]
            text = Text(content="hola mundo", language=Language.ENG, difficulty=Difficulty.MEDIUM)
            db.add_all([*users, text])
            db.flush()
            room = Room(
                code="ROOM01", host_id=users[0].id,
                language=Language.ENG, difficulty=Difficulty.MEDIUM,
            )
            db.add(room)
            db.commit()
            self.ids = {user.username: user.id for user in users}
            self.text_id, self.room_id = text.id, room.id
            self.tokens = {name: issue_session(db, user_id) for name, user_id in self.ids.items()}

        def test_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(app.dependency_overrides.pop, get_db)
        self.addCleanup(self.client.close)

    def play(self, username, minutes, ppm, precision, *, multiplayer=False,
             position=None, progress=1.0, finished=True):
        """Guarda una partida terminada `minutes` minutos después de START."""
        with self.sessions() as db:
            finished_at = START + timedelta(minutes=minutes)
            game = Game(
                text_id=self.text_id,
                room_id=self.room_id if multiplayer else None,
                mode=GameMode.MULTIPLAYER if multiplayer else GameMode.SINGLEPLAYER,
                started_at=finished_at - timedelta(seconds=30),
                finished_at=finished_at if finished else None,
            )
            db.add(game)
            db.flush()
            db.add(GameParticipant(
                game_id=game.id, user_id=self.ids[username], time_ms=30_000, ppm=ppm,
                precision_pct=precision, progress=progress, position=position,
                score=ppm,
            ))
            db.commit()
            return game.id

    def stats(self, username="ana", query=""):
        token = self.tokens[username]
        response = self.client.get(
            f"/api/v1/users/me/stats{query}", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_trend_shows_the_last_30_matches_in_chronological_order(self):
        # Escenario: Visualización de tendencia de PPM reciente.
        ids = [self.play("ana", minute, ppm=40 + minute, precision=90) for minute in range(35)]
        trend = self.stats()["trend"]
        self.assertEqual(len(trend), 30)
        self.assertEqual([point["gameId"] for point in trend], ids[5:])
        self.assertEqual([point["ppm"] for point in trend], list(range(45, 75)))
        self.assertEqual(set(trend[0]), {"gameId", "finishedAt", "mode", "ppm", "precisionPct"})

    def test_trend_appears_with_a_single_match(self):
        self.play("ana", 0, ppm=50, precision=97.5)
        data = self.stats()
        self.assertEqual(len(data["trend"]), 1)
        self.assertEqual(data["trend"][0]["precisionPct"], 97.5)

    def test_history_shows_date_mode_speed_accuracy_and_score_for_both_modes(self):
        # Escenario: Detalle del historial de partidas.
        self.play("ana", 0, ppm=50, precision=95)
        self.play("ana", 1, ppm=62, precision=88, multiplayer=True, position=2, progress=0.8)
        first, second = self.stats()["history"]
        self.assertEqual(
            (first["mode"], first["ppm"], first["precisionPct"], first["score"], first["position"]),
            ("multiplayer", 62, 88, 62, 2),
        )
        self.assertEqual(first["progress"], 0.8)
        self.assertEqual((second["mode"], second["position"]), ("singleplayer", None))
        self.assertEqual(
            datetime.fromisoformat(first["finishedAt"]).replace(tzinfo=timezone.utc),
            START + timedelta(minutes=1),
        )
        self.assertEqual((first["language"], first["difficulty"]), ("eng", "medium"))

    def test_summary_averages_both_modes_and_ignores_unfinished_games(self):
        self.play("ana", 0, ppm=40, precision=90)
        self.play("ana", 1, ppm=60, precision=100, multiplayer=True, position=1)
        self.play("ana", 2, ppm=200, precision=10, finished=False)
        self.play("beto", 3, ppm=999, precision=100)
        summary = self.stats()["summary"]
        self.assertEqual(summary, {
            "totalMatches": 2, "practiceMatches": 1, "multiplayerMatches": 1,
            "averagePpm": 50.0, "averagePrecisionPct": 95.0, "bestPpm": 60,
        })

    def test_new_user_gets_an_empty_payload_without_chart_data(self):
        # Escenario: Usuario nuevo sin partidas registradas.
        self.play("ana", 0, ppm=50, precision=95)
        data = self.stats("nuevo")
        self.assertEqual(data["trend"], [])
        self.assertEqual(data["history"], [])
        self.assertFalse(data["hasMore"])
        self.assertEqual(data["summary"], {
            "totalMatches": 0, "practiceMatches": 0, "multiplayerMatches": 0,
            "averagePpm": None, "averagePrecisionPct": None, "bestPpm": None,
        })

    def test_history_is_paginated_newest_first(self):
        ids = [self.play("ana", minute, ppm=40, precision=90) for minute in range(5)]
        first = self.stats(query="?limit=2")
        self.assertEqual([entry["gameId"] for entry in first["history"]], ids[:2:-1][:2])
        self.assertTrue(first["hasMore"])
        last = self.stats(query="?limit=2&offset=4")
        self.assertEqual([entry["gameId"] for entry in last["history"]], [ids[0]])
        self.assertFalse(last["hasMore"])
        # La paginación no cambia el resumen ni la evolución.
        self.assertEqual(last["summary"]["totalMatches"], 5)
        self.assertEqual(len(last["trend"]), 5)

    def test_rejects_invalid_pages_and_missing_authentication(self):
        token = self.tokens["ana"]
        for query in ("?limit=0", "?limit=51", "?offset=-1"):
            response = self.client.get(
                f"/api/v1/users/me/stats{query}", headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(response.status_code, 422, query)
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            response = self.client.get("/api/v1/users/me/stats", headers=headers)
            self.assertIn(response.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
