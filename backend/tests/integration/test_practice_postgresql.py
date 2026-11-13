import unittest
from pathlib import Path

from test_text_postgresql import ENABLED, require_local_fixture

SPANISH_PHRASE = "La práctica diaria mejora la velocidad al escribir con cuidado."
ENGLISH_ROLLBACK_PHRASE = "PostgreSQL rollback probe. Daily typing practice improves speed and accuracy."


@unittest.skipUnless(ENABLED, "Requires the isolated docker-compose.test.yml fixture.")
class PostgreSQLPracticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_local_fixture()
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.config import settings

        cls.engine = create_engine(
            settings.database_url,
            connect_args={"options": "-csearch_path=practice_results_test"},
        )
        schema = Path(__file__).resolve().parents[3] / "supabase/db/init.sql"
        with cls.engine.begin() as connection:
            connection.exec_driver_sql("CREATE SCHEMA practice_results_test")
            connection.exec_driver_sql(schema.read_text(encoding="utf-8"))
        cls.sessions = sessionmaker(bind=cls.engine)
        from app.models import User
        from app.security import create_access_token

        with cls.sessions() as db:
            user = User(
                username="practice_test",
                email="practice@example.test",
                hashed_password="test-only",
            )
            db.add(user)
            db.commit()
            cls.user_id = user.id
            cls.headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}

    @classmethod
    def tearDownClass(cls):
        try:
            with cls.engine.begin() as connection:
                connection.exec_driver_sql("DROP SCHEMA practice_results_test CASCADE")
        finally:
            cls.engine.dispose()

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.deps import get_db
        from app.main import app

        def test_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.pop, get_db)
        self.addCleanup(self.client.close)
        self.payload = {
            "text": {"content": SPANISH_PHRASE, "language": "spa"},
            "timeMs": 12000,
            "typed": "casa mesa gato",
            "keystrokes": 14,
            "errors": 0,
        }

    def test_api_persists_local_text_metrics_and_history_in_postgresql(self):
        from app.models import Game, GameParticipant, Text

        first = self.client.post(
            "/api/v1/matches/practice", json=self.payload, headers=self.headers
        )
        self.assertEqual(first.status_code, 201, first.text)
        saved = first.json()
        self.assertEqual(saved["score"], 14)
        with self.sessions() as db:
            game = db.get(Game, saved["id"])
            self.assertEqual(game.text_id, saved["textId"])
            self.assertEqual(game.mode.value, "singleplayer")
            self.assertEqual(db.get(Text, game.text_id).content, SPANISH_PHRASE)
            self.assertEqual(game.participants[0].user_id, self.user_id)
            self.assertIsInstance(game.participants[0], GameParticipant)
            self.assertEqual(game.participants[0].ppm, 14)
            self.assertAlmostEqual(game.participants[0].precision_pct, 100)

        retry = {key: value for key, value in self.payload.items() if key != "text"}
        retry["textId"] = saved["textId"]
        second = self.client.post(
            "/api/v1/matches/practice", json=retry, headers=self.headers
        )
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["textId"], saved["textId"])
        history = self.client.get(
            "/api/v1/matches/practice?limit=1", headers=self.headers
        )
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]["id"], second.json()["id"])

    def test_selected_level_and_monthly_ranking_on_postgresql(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from app.models import Game

        payload = {**self.payload, "difficulty": "easy"}
        first = self.client.post(
            "/api/v1/matches/practice", json=payload, headers=self.headers
        )
        self.assertEqual(first.status_code, 201, first.text)
        second = self.client.post(
            "/api/v1/matches/practice",
            json={**payload, "timeMs": 6000},
            headers=self.headers,
        )
        self.assertEqual(second.status_code, 201, second.text)
        with self.sessions() as db:
            for saved in (first.json(), second.json()):
                db.get(Game, saved["id"]).finished_at = datetime(
                    2026, 11, 10, 12, tzinfo=ZoneInfo("America/Santiago")
                )
            db.commit()
        ranking = self.client.get(
            "/api/v1/matches/leaderboard?month=2026-11&difficulty=easy&language=spa",
            headers=self.headers,
        )
        self.assertEqual(ranking.status_code, 200, ranking.text)
        entries = ranking.json()["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["userId"], self.user_id)
        self.assertEqual(entries[0]["score"], second.json()["score"])
        self.assertEqual(entries[0]["position"], 1)

    def test_participant_failure_rolls_back_new_text_and_game_in_postgresql(self):
        from sqlalchemy import func, select
        from app.models import Game, GameParticipant, Text

        def counts():
            with self.sessions() as db:
                return tuple(
                    db.scalar(select(func.count()).select_from(model))
                    for model in (Text, Game, GameParticipant)
                )

        before = counts()
        with self.engine.begin() as connection:
            connection.exec_driver_sql("""CREATE FUNCTION reject_practice_result() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'Deliberate practice test failure'; END $$""")
            connection.exec_driver_sql("""CREATE TRIGGER reject_practice_result BEFORE INSERT ON game_participants
                FOR EACH ROW EXECUTE FUNCTION reject_practice_result()""")
        try:
            payload = {
                **self.payload,
                "text": {"content": ENGLISH_ROLLBACK_PHRASE, "language": "eng"},
            }
            response = self.client.post(
                "/api/v1/matches/practice", json=payload, headers=self.headers
            )
            self.assertEqual(response.status_code, 503, response.text)
            self.assertEqual(counts(), before)
        finally:
            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    "DROP TRIGGER reject_practice_result ON game_participants"
                )
                connection.exec_driver_sql("DROP FUNCTION reject_practice_result()")
