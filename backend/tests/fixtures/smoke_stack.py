"""Seed and verify the disposable database without polluting the suite."""

from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.commands.migrate import alembic_config, current_revision
from app.database import SessionLocal
from app.main import app


def main():
    assert current_revision() == ScriptDirectory.from_config(alembic_config()).get_current_head()
    with SessionLocal() as db, TestClient(app) as client:
        assert db.scalar(text("SHOW server_version_num")).startswith("16")
        user = db.scalar(text("""
            INSERT INTO users (username, email, hashed_password)
            VALUES ('qa_smoke', 'qa-smoke@typr.test', 'not-a-login-hash') RETURNING id
        """))
        assert db.scalar(text("""
            INSERT INTO texts (content, language, difficulty, record_user_id)
            VALUES ('Synthetic typing practice for the disposable test stack.', 'eng', 'easy', :user)
            RETURNING record_user_id
        """), {"user": user}) == user
        assert db.scalar(text("""
            INSERT INTO rooms (host_id, code, language, difficulty)
            VALUES (:user, 'QATEST', 'eng', 'easy') RETURNING host_id
        """), {"user": user}) == user
        response = client.get("/api/v1/health")
        assert response.status_code == 200 and response.json() == {"status": "ok"}
        db.rollback()


if __name__ == "__main__":
    main()
