"""Unit tests for registration and login in app.services.auth (HU-01)."""

import os
import unittest
from unittest import mock

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "auth-service-tests-only-secret-not-for-production")

from psycopg.errors import UniqueViolation
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import User
from app.schemas.auth import RegisterRequest
from app.security import verify_password
from app.services.auth import UserAlreadyExists, authenticate, register_user

PASSWORD = "fixture-password-01"


def request(username="ana", email="ana@example.com", password=PASSWORD):
    return RegisterRequest(username=username, email=email, password=password)


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.addCleanup(engine.dispose)
        self.addCleanup(self.db.close)

    def test_registration_persists_a_hashed_account_with_lowercase_email(self):
        user = register_user(self.db, request(email="Ana@Example.COM"))

        stored = self.db.scalars(select(User)).one()
        self.assertEqual(stored.id, user.id)
        self.assertEqual(stored.username, "ana")
        self.assertEqual(stored.email, "ana@example.com")
        self.assertNotEqual(stored.hashed_password, PASSWORD)
        self.assertTrue(verify_password(PASSWORD, stored.hashed_password))

    def test_username_collision_is_reported_and_creates_nothing(self):
        register_user(self.db, request())

        with self.assertRaises(UserAlreadyExists) as raised:
            register_user(self.db, request(email="other@example.com"))

        self.assertEqual(raised.exception.field, "username")
        self.assertEqual(len(self.db.scalars(select(User)).all()), 1)

    def test_email_collision_is_case_insensitive_and_creates_nothing(self):
        register_user(self.db, request())

        with self.assertRaises(UserAlreadyExists) as raised:
            register_user(self.db, request(username="beto", email="ANA@example.com"))

        self.assertEqual(raised.exception.field, "email")
        self.assertEqual(len(self.db.scalars(select(User)).all()), 1)

    def test_email_takes_precedence_when_both_fields_collide(self):
        register_user(self.db, request())

        with self.assertRaises(UserAlreadyExists) as raised:
            register_user(self.db, request())

        self.assertEqual(raised.exception.field, "email")

    def test_unique_violation_race_is_translated_into_a_conflict(self):
        register_user(self.db, request())
        racing = IntegrityError("insert", {}, UniqueViolation())
        with (
            mock.patch("app.services.auth.registration_conflict") as lookup,
            mock.patch.object(self.db, "commit", side_effect=racing),
        ):
            lookup.side_effect = [None, UserAlreadyExists("email")]
            with self.assertRaises(UserAlreadyExists) as raised:
                register_user(self.db, request(username="beto", email="beto@example.com"))

        self.assertEqual(raised.exception.field, "email")

    def test_other_integrity_errors_are_not_swallowed(self):
        failure = IntegrityError("insert", {}, Exception("not null"))
        with mock.patch.object(self.db, "commit", side_effect=failure):
            with self.assertRaises(IntegrityError):
                register_user(self.db, request())

    def test_login_succeeds_with_correct_credentials_and_any_email_case(self):
        user = register_user(self.db, request())

        self.assertEqual(authenticate(self.db, "ana@example.com", PASSWORD).id, user.id)
        self.assertEqual(authenticate(self.db, "ANA@Example.Com", PASSWORD).id, user.id)

    def test_login_fails_with_wrong_password(self):
        register_user(self.db, request())

        self.assertIsNone(authenticate(self.db, "ana@example.com", "wrong-password-01"))

    def test_login_fails_for_unknown_user(self):
        self.assertIsNone(authenticate(self.db, "nobody@example.com", PASSWORD))


if __name__ == "__main__":
    unittest.main()
