"""Revocation and renewal edge cases of the session service."""

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "sessions-service-tests-only-secret-not-for-production")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AuthSession, User
from app.security import create_access_token, decode_session_token
from app.services import sessions as svc

# JWT expiry is checked against the real clock, so the fake clock starts at the real now.
START = datetime.now(timezone.utc).replace(microsecond=0)


class SessionServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.addCleanup(self.db.close)
        for name in ("ana", "beto"):
            self.db.add(User(username=name, email=f"{name}@example.test", hashed_password="x"))
        self.db.commit()
        self.ana, self.beto = self.db.query(User).order_by(User.id).all()
        self.clock = START
        patcher = mock.patch.object(svc, "utc_now", lambda: self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _issue(self, user=None) -> tuple[str, AuthSession]:
        token = svc.issue_session(self.db, (user or self.ana).id)
        _, session_id = decode_session_token(token)
        return token, self.db.get(AuthSession, session_id)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        # SQLite returns naive datetimes for columns that store UTC.
        return value.replace(tzinfo=value.tzinfo or timezone.utc)

    def _token_for(self, user, session) -> str:
        return create_access_token(user.id, session.id, self._aware(session.absolute_expires_at))

    def _unknown_session_token(self, session) -> str:
        return create_access_token(self.ana.id, uuid4(), self._aware(session.absolute_expires_at))

    def _idle(self, session) -> datetime:
        self.db.refresh(session)
        return self._aware(session.idle_expires_at)

    def test_revoke_invalidates_session_once(self):
        token, session = self._issue()
        self.assertTrue(svc.revoke_session(self.db, token))
        self.assertIsNotNone(self.db.get(AuthSession, session.id).revoked_at)
        self.assertIsNone(svc.session_user(self.db, token))
        self.assertFalse(svc.revoke_session(self.db, token))

    def test_revoke_rejects_malformed_token(self):
        self.assertFalse(svc.revoke_session(self.db, "not-a-token"))

    def test_revoke_rejects_token_of_another_user(self):
        _, session = self._issue()
        self.assertFalse(svc.revoke_session(self.db, self._token_for(self.beto, session)))
        self.assertIsNone(self.db.get(AuthSession, session.id).revoked_at)

    def test_revoke_rejects_idle_expired_session(self):
        token, session = self._issue()
        self.clock = START + svc.IDLE_TIMEOUT
        self.assertFalse(svc.revoke_session(self.db, token))
        self.assertIsNone(self.db.get(AuthSession, session.id).revoked_at)

    def test_revoke_rejects_unknown_session(self):
        _, session = self._issue()
        self.assertFalse(svc.revoke_session(self.db, self._unknown_session_token(session)))

    def test_session_user_rejects_subject_mismatch(self):
        _, session = self._issue()
        self.assertIsNone(svc.session_user(self.db, self._token_for(self.beto, session)))

    def test_validate_race_session_rejects_invalid_token(self):
        self.assertIsNone(svc.validate_race_session(self.db, "not-a-token"))

    def test_validate_race_session_returns_aware_deadlines(self):
        token, _ = self._issue()
        check = svc.validate_race_session(self.db, token)
        self.assertIsNotNone(check.idle.tzinfo)
        self.assertEqual(check.idle, START + svc.IDLE_TIMEOUT)
        self.assertEqual(check.absolute - START, svc.ABSOLUTE_TIMEOUT)

    def test_renewal_not_due_flips_at_cadence_boundary(self):
        token, _ = self._issue()
        check = svc.validate_race_session(self.db, token)
        self.clock = START + svc.RENEWAL_INTERVAL - timedelta(seconds=1)
        self.assertTrue(check.renewal_not_due())
        self.clock = START + svc.RENEWAL_INTERVAL
        self.assertFalse(check.renewal_not_due())

    def test_renewal_not_due_is_false_near_absolute_expiry(self):
        check = svc.RaceSessionCheck(
            idle=START + svc.IDLE_TIMEOUT, absolute=START + timedelta(seconds=10),
        )
        self.clock = START + timedelta(seconds=10)
        self.assertFalse(check.renewal_not_due())

    def test_race_renewal_is_noop_before_cadence(self):
        token, session = self._issue()
        before = self._idle(session)
        self.clock = START + svc.RENEWAL_INTERVAL - timedelta(seconds=1)
        self.assertTrue(svc.renew_from_race(self.db, token))
        self.assertEqual(self._idle(session), before)

    def test_race_renewal_extends_idle_when_due(self):
        token, session = self._issue()
        self.clock = START + svc.RENEWAL_INTERVAL
        self.assertTrue(svc.renew_from_race(self.db, token))
        self.assertEqual(self._idle(session), self.clock + svc.IDLE_TIMEOUT)

    def test_renewal_never_exceeds_absolute_expiry(self):
        token, session = self._issue()
        absolute = self._aware(session.absolute_expires_at)
        session.idle_expires_at = absolute - timedelta(minutes=1)
        self.db.commit()
        self.clock = absolute - timedelta(minutes=2)
        self.assertTrue(svc.renew_from_race(self.db, token))
        self.assertEqual(self._idle(session), absolute)

    def test_renewal_rejects_malformed_and_unknown_tokens(self):
        _, session = self._issue()
        self.assertFalse(svc.renew_from_race(self.db, "not-a-token"))
        self.assertFalse(svc.renew_from_race(self.db, self._unknown_session_token(session)))

    def test_renewal_rejects_token_of_another_user(self):
        _, session = self._issue()
        self.assertFalse(svc.renew_from_race(self.db, self._token_for(self.beto, session)))

    def test_renewal_rejects_revoked_session(self):
        token, _ = self._issue()
        svc.revoke_session(self.db, token)
        self.assertFalse(svc.renew_from_race(self.db, token))

    def test_renewal_rejects_idle_expired_session_without_resurrecting_it(self):
        token, session = self._issue()
        stored = self._idle(session)
        self.clock = stored
        self.assertFalse(svc.renew_from_race(self.db, token))
        self.assertEqual(self._idle(session), stored)

    def test_renewal_rejects_session_past_absolute_expiry(self):
        token, session = self._issue()
        session.idle_expires_at = START + timedelta(days=2)
        self.db.commit()
        self.clock = self._aware(session.absolute_expires_at)
        self.assertFalse(svc.renew_from_race(self.db, token))

    def test_renewal_rejects_token_that_stops_decoding_after_lock(self):
        token, _ = self._issue()
        claims = decode_session_token(token)
        with mock.patch.object(svc, "decode_session_token", side_effect=[claims, None]):
            self.assertFalse(svc.renew_from_race(self.db, token))

    def test_practice_notices_renew_only_when_newer(self):
        token, session = self._issue()
        self.clock = START + svc.RENEWAL_INTERVAL
        first = svc.renew_from_practice(self.db, token, 5)
        self.assertEqual(first[0], self.clock + svc.IDLE_TIMEOUT)
        self.assertEqual(session.last_practice_notice, 5)

        self.clock += svc.RENEWAL_INTERVAL
        self.assertEqual(svc.renew_from_practice(self.db, token, 5)[0], first[0])
        self.assertEqual(svc.renew_from_practice(self.db, token, 4)[0], first[0])
        self.assertEqual(session.last_practice_notice, 5)

        newer = svc.renew_from_practice(self.db, token, 6)
        self.assertEqual(newer[0], self.clock + svc.IDLE_TIMEOUT)
        self.assertEqual(session.last_practice_notice, 6)

    def test_practice_renewal_returns_none_for_invalid_session(self):
        self.assertIsNone(svc.renew_from_practice(self.db, "not-a-token", 1))


if __name__ == "__main__":
    unittest.main()
