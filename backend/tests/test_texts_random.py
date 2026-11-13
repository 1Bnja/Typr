import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "texts-random-tests-only-secret-not-for-production")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import Difficulty, Language, Text, User
from app.security import create_access_token


class TextsRandomTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            user = User(
                username="reader", email="reader@example.test", hashed_password="x"
            )
            db.add(user)
            db.add_all(
                [
                    Text(content="spa fácil", language=Language.SPA, difficulty=Difficulty.EASY),
                    Text(content="spa experta", language=Language.SPA, difficulty=Difficulty.EXPERT),
                    Text(content="eng easy", language=Language.ENG, difficulty=Difficulty.EASY),
                ]
            )
            db.commit()
            self.user_id = user.id

        def test_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        self.headers = {"Authorization": f"Bearer {create_access_token(self.user_id)}"}
        self.addCleanup(self.engine.dispose)
        self.addCleanup(app.dependency_overrides.pop, get_db)
        self.addCleanup(self.client.close)

    def get(self, query="", headers=None):
        suffix = f"?{query}" if query else ""
        return self.client.get(
            f"/api/v1/texts/random{suffix}",
            headers=self.headers if headers is None else headers,
        )

    def test_returns_a_stored_text(self):
        response = self.get()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn(body["content"], {"spa fácil", "spa experta", "eng easy"})
        self.assertIsNotNone(body["id"])

    def test_filters_by_language(self):
        for _ in range(15):
            body = self.get("language=eng").json()
            self.assertEqual(body["language"], "eng")
            self.assertEqual(body["content"], "eng easy")

    def test_filters_by_difficulty(self):
        for _ in range(15):
            body = self.get("difficulty=expert").json()
            self.assertEqual(body["difficulty"], "expert")
            self.assertEqual(body["content"], "spa experta")

    def test_filters_by_language_and_difficulty(self):
        for _ in range(10):
            body = self.get("language=spa&difficulty=easy").json()
            self.assertEqual(body["content"], "spa fácil")

    def test_404_when_no_text_matches(self):
        # No hay un texto inglés experto sembrado.
        self.assertEqual(self.get("language=eng&difficulty=expert").status_code, 404)

    def test_rejects_invalid_filter_values(self):
        self.assertEqual(self.get("language=fr").status_code, 422)
        self.assertEqual(self.get("difficulty=impossible").status_code, 422)

    def test_requires_authentication(self):
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            with self.subTest(headers=headers):
                self.assertIn(self.get(headers=headers).status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
