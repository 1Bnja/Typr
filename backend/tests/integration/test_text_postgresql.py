"""Real PostgreSQL tests, permitted only in the disposable Compose fixture."""

import json
import os
from pathlib import Path
import platform
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "backend/tests/fixtures/text_calibration.json"
ENABLED = os.environ.get("TYPR_POSTGRES_INTEGRATION") == "1"


def require_local_fixture():
    url = urlsplit(os.environ.get("DATABASE_URL", ""))
    expected = (
        url.scheme == "postgresql+psycopg",
        url.hostname == "postgres",
        url.port == 5432,
        url.path == "/typr_texts_test",
        url.username == "typr_test",
        url.password == "local_test_only",
        os.environ.get("JWT_SECRET") == "local-integration-test-only",
        not url.query,
    )
    if not ENABLED or not all(expected):
        raise RuntimeError(
            "Refusing integration tests outside the local Compose fixture."
        )


@unittest.skipUnless(ENABLED, "Requires the isolated docker-compose.test.yml fixture.")
class PostgreSQLTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_local_fixture()
        import psycopg
        import sqlalchemy
        from app.database import SessionLocal, execute_sql
        from app.services.texts_handler import TextFacade
        from app.services.texts_handler.errors import (
            TextDatabaseError,
            TextValidationError,
        )

        cls.SessionLocal = staticmethod(SessionLocal)
        cls.execute_sql = staticmethod(execute_sql)
        cls.TextFacade = TextFacade
        cls.TextDatabaseError = TextDatabaseError
        cls.TextValidationError = TextValidationError
        cls.samples = json.loads(REFERENCE.read_text())["results"]
        with cls.SessionLocal() as db:
            server = cls.execute_sql(db, "SHOW server_version", {}).scalar_one()
            database = cls.execute_sql(db, "SELECT current_database()", {}).scalar_one()
            if database != "typr_texts_test":
                raise RuntimeError("Unexpected database; refusing fixture writes.")
            if cls.execute_sql(db, "SELECT count(*) FROM texts", {}).scalar_one() != 0:
                raise RuntimeError(
                    "Fixture must start empty; refusing to overwrite data."
                )
            cls.records = []
            facade = cls.TextFacade(db)
            for sample in cls.samples:
                cls.records.append(facade.create(sample["content"], sample["language"]))
        print(
            f"LIVE_VERSIONS PostgreSQL={server} Python={platform.python_version()} "
            f"SQLAlchemy={sqlalchemy.__version__} psycopg={psycopg.__version__}",
            flush=True,
        )

    def count_texts(self, db):
        return self.execute_sql(db, "SELECT count(*) FROM texts", {}).scalar_one()

    def test_all_sixteen_samples_are_committed_and_match_reference(self):
        self.assertEqual(len(self.records), 16)
        self.assertEqual(len({record.id for record in self.records}), 16)
        with self.SessionLocal() as db:
            rows = (
                self.execute_sql(
                    db,
                    "SELECT id, content, language, difficulty, ideal_time_ms, record_user_id FROM texts ORDER BY id",
                    {},
                )
                .mappings()
                .all()
            )
            self.assertEqual(len(rows), 16)
            for row, record, sample in zip(
                rows, self.records, self.samples, strict=True
            ):
                with self.subTest(identifier=sample["id"]):
                    measured = self.TextFacade().process(
                        sample["content"], sample["language"]
                    )
                    self.assertAlmostEqual(
                        measured.classification.score, sample["score"], places=11
                    )
                    self.assertGreater(row["id"], 0)
                    self.assertEqual(row["id"], record.id)
                    self.assertEqual(row["content"], sample["content"])
                    self.assertEqual(row["language"], sample["language"])
                    self.assertEqual(row["difficulty"], sample["actual"])
                    self.assertEqual(record.language.value, sample["language"])
                    self.assertEqual(record.difficulty.value, sample["actual"])
                    self.assertIsNone(row["ideal_time_ms"])
                    self.assertIsNone(row["record_user_id"])
        print("LIVE_SAMPLES committed=16 medium=8 advanced=8", flush=True)

    def test_duplicates_after_normalization_do_not_add_rows(self):
        with self.SessionLocal() as db:
            facade = self.TextFacade(db)
            for sample in self.samples:
                with self.subTest(identifier=sample["id"]):
                    content = "\t " + sample["content"].replace(" ", "  \n") + " \r"
                    with self.assertRaises(self.TextValidationError) as caught:
                        facade.create(content, sample["language"])
                    self.assertEqual(caught.exception.code, "duplicate_content")
            quoted = next(sample for sample in self.samples if sample["id"] == "SPA-06")
            content = quoted["content"].replace("'", "‘", 1)
            content = content.replace("'", "’", 1)
            with self.assertRaises(self.TextValidationError) as caught:
                facade.create(content, "spa")
            self.assertEqual(caught.exception.code, "duplicate_content")
            self.assertEqual(self.count_texts(db), 16)

    def test_invalid_input_does_not_add_rows(self):
        with self.SessionLocal() as db:
            facade = self.TextFacade(db)
            for content, language in (
                ("Hola 😀", "spa"),
                ("pingüino", "eng"),
                ("don't", "spa"),
            ):
                with self.subTest(content=content):
                    with self.assertRaises(self.TextValidationError):
                        facade.create(content, language)
            self.assertEqual(self.count_texts(db), 16)

    def test_postgresql_failure_rolls_back_and_session_recovers(self):
        with self.SessionLocal() as db:
            self.execute_sql(
                db,
                """CREATE FUNCTION reject_integration_probe() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                  IF NEW.content = 'Rollback probe.' THEN
                    RAISE EXCEPTION 'Deliberate local integration failure';
                  END IF;
                  RETURN NEW;
                END $$""",
                {},
            )
            self.execute_sql(
                db,
                "CREATE TRIGGER reject_integration_probe BEFORE INSERT ON texts FOR EACH ROW EXECUTE FUNCTION reject_integration_probe()",
                {},
            )
            db.commit()
            try:
                facade = self.TextFacade(db)
                with self.assertRaises(self.TextDatabaseError) as caught:
                    facade.create("Rollback probe.", "eng")
                self.assertEqual(caught.exception.operation, "write")
                self.assertEqual(self.count_texts(db), 16)
                record = facade.create("Recovery probe.", "eng")
                self.assertGreater(record.id, 0)
                self.assertEqual(self.count_texts(db), 17)
                self.execute_sql(
                    db, "DELETE FROM texts WHERE id = %(id)s", {"id": record.id}
                )
                db.commit()
            finally:
                db.rollback()
                self.execute_sql(
                    db, "DROP TRIGGER reject_integration_probe ON texts", {}
                )
                self.execute_sql(db, "DROP FUNCTION reject_integration_probe()", {})
                db.commit()
            self.assertEqual(self.count_texts(db), 16)
        print(
            "LIVE_ROLLBACK forced_insert_error=handled session_recovery=verified",
            flush=True,
        )


if __name__ == "__main__":
    unittest.main()
