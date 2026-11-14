"""Verifica que el esquema PostgreSQL desplegable soporta multiplayer."""

import unittest

from test_text_postgresql import ENABLED, require_local_fixture


@unittest.skipUnless(ENABLED, "Requires the isolated docker-compose.test.yml fixture.")
class PostgreSQLRoomsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_local_fixture()
        from fastapi.testclient import TestClient
        from sqlalchemy import text

        from app.database import SessionLocal
        from app.main import app
        from app.models import User
        from app.security import create_access_token

        cls.SessionLocal = staticmethod(SessionLocal)
        cls.client = TestClient(app)
        with cls.SessionLocal() as db:
            user = User(
                username="rooms_postgres",
                email="rooms-postgres@example.test",
                hashed_password="test-only",
            )
            db.add(user)
            db.commit()
            cls.user_id = user.id
        cls.headers = {
            "Authorization": f"Bearer {create_access_token(cls.user_id)}"
        }

        # La prueba debe ejecutarse sobre el head que usara el deploy.
        with cls.SessionLocal() as db:
            cls.revision = db.scalar(
                text("SELECT version_num FROM alembic_version")
            )

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import delete

        from app.models import Room, User

        try:
            with cls.SessionLocal() as db:
                db.execute(delete(Room).where(Room.host_id == cls.user_id))
                db.execute(delete(User).where(User.id == cls.user_id))
                db.commit()
        finally:
            cls.client.close()

    def test_creates_room_on_migrated_postgresql_schema(self):
        self.assertEqual(self.revision, "0003")
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
        room = response.json()
        self.assertRegex(room["code"], r"^[A-Z0-9]{6}$")
        self.assertEqual(room["rounds"], 3)
        self.assertEqual(room["timeLimitS"], 90)
        self.assertFalse(room["members"][0]["isReady"])


if __name__ == "__main__":
    unittest.main()
