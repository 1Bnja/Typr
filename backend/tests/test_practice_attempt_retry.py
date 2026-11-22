import os
import unittest
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "practice-attempt-tests-only-secret")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.deps import get_db
from app.models import Difficulty, Game, GameParticipant, Language, Text, User
from app.routers.matches import router
from app.services.sessions import issue_session


class PracticeAttemptRetryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.sessions = sessionmaker(engine)

        with self.sessions() as db:
            users = [
                User(
                    username=name,
                    email=f"{name}@example.test",
                    hashed_password="fixture",
                )
                for name in ("retry_first", "retry_second")
            ]
            text = Text(
                content="Hello world.",
                language=Language.ENG,
                difficulty=Difficulty.EASY,
            )
            db.add_all([*users, text])
            db.commit()
            self.payload = {
                "attemptId": str(uuid4()),
                "textId": text.id,
                "timeMs": 1300,
                "typed": "Hello",
                "keystrokes": 7,
                "errors": 1,
            }
            self.headers, self.other_headers = [
                {"Authorization": f"Bearer {issue_session(db, user.id)}"}
                for user in users
            ]

        def isolated_db():
            with self.sessions() as db:
                yield db

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = isolated_db
        self.client = self.enterContext(TestClient(app))

    def save(self, headers=None, **changes):
        return self.client.post(
            "/practice",
            json={**self.payload, **changes},
            headers=self.headers if headers is None else headers,
        )

    def assert_counts(self, count):
        with self.sessions() as db:
            for model in (Game, GameParticipant):
                self.assertEqual(
                    db.scalar(select(func.count()).select_from(model)), count
                )

    def test_replays_committed_attempt_and_rejects_changed_payload(self):
        first = self.save()
        self.assertEqual(first.status_code, 201, first.text)
        replay = self.save()
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json(), first.json())
        conflict = self.save(timeMs=1000)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assert_counts(1)

    def test_attempt_key_is_scoped_to_authenticated_user(self):
        first = self.save()
        other = self.save(headers=self.other_headers)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(other.status_code, 201, other.text)
        self.assertNotEqual(first.json()["id"], other.json()["id"])
        self.assertEqual(self.save(headers={}).status_code, 401)
        self.assert_counts(2)

    def test_new_attempt_with_identical_signals_is_not_a_replay(self):
        first = self.save()
        second = self.save(attemptId=str(uuid4()))
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertNotEqual(first.json()["id"], second.json()["id"])
        self.assert_counts(2)
