"""Check the populated 0003 upgrade and Alembic model drift in test Compose."""

import os

import psycopg
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from backend.tests.integration.test_text_postgresql import require_local_fixture


def snapshot(connection, projections):
    return {
        table: connection.exec_driver_sql(f"SELECT {columns} FROM {table}").all()
        for table, columns in projections.items()
    }


def main():
    require_local_fixture()
    url = os.environ["DATABASE_URL"]
    # Keep the legacy bootstrap and integration fixtures in their original database.
    with psycopg.connect(url.replace("+psycopg", "", 1), autocommit=True) as admin:
        admin.execute("CREATE DATABASE typr_migration_test TEMPLATE template0")
    os.environ["DATABASE_URL"] = url.rsplit("/", 1)[0] + "/typr_migration_test"

    from app.commands.migrate import alembic_config, current_revision, main as migrate
    from app.database import engine

    config = alembic_config()
    command.upgrade(config, "0003")
    assert current_revision() == "0003"

    # One linked row in each pre-session table; use generated IDs as the app does.
    with engine.begin() as connection:
        user_id = connection.exec_driver_sql(
            "INSERT INTO users (username, email, hashed_password) "
            "VALUES ('migration-user', 'migration@example.test', 'fixture-hash') "
            "RETURNING id"
        ).scalar_one()
        text_id = connection.exec_driver_sql(
            "INSERT INTO texts (content, language, difficulty, ideal_time_ms, record_user_id) "
            "VALUES ('Migration fixture text', 'eng', 'easy', 32000, %s) RETURNING id",
            (user_id,),
        ).scalar_one()
        room_id = connection.exec_driver_sql(
            "INSERT INTO rooms (host_id, language, difficulty, code, rounds, time_limit_s) "
            "VALUES (%s, 'eng', 'easy', 'ABC123', 3, 90) RETURNING id",
            (user_id,),
        ).scalar_one()
        connection.exec_driver_sql(
            "INSERT INTO room_members (room_id, member_id, is_ready) VALUES (%s, %s, true)",
            (room_id, user_id),
        )
        game_id = connection.exec_driver_sql(
            "INSERT INTO games (room_id, text_id, mode, finished_at) "
            "VALUES (%s, %s, 'multiplayer', now()) RETURNING id",
            (room_id, text_id),
        ).scalar_one()
        connection.exec_driver_sql(
            "INSERT INTO game_participants (game_id, user_id, time_ms, ppm, precision_pct, score) "
            "VALUES (%s, %s, 28000, 93, 98.5, 110)",
            (game_id, user_id),
        )
        # Compare only 0003 columns so future additive migrations can still pass.
        inspector = inspect(connection)
        quote = connection.dialect.identifier_preparer.quote
        projections = {
            quote(table): ", ".join(quote(col["name"]) for col in inspector.get_columns(table))
            for table in ("users", "texts", "rooms", "room_members", "games", "game_participants")
        }
        before = snapshot(connection, projections)
        assert all(len(rows) == 1 for rows in before.values()), before

    # Exercise the same entry point as deploy, not a test-only upgrade implementation.
    migrate()
    head = ScriptDirectory.from_config(config).get_current_head()
    assert current_revision() == head
    with engine.begin() as connection:
        after = snapshot(connection, projections)
        for table, rows in before.items():
            assert after[table] == rows, f"0003 data changed in {table}"

        notice = connection.exec_driver_sql(
            "INSERT INTO auth_sessions (id, user_id, idle_expires_at, absolute_expires_at) "
            "VALUES ('00000000-0000-4000-8000-000000000001', %s, "
            "now() + interval '1 hour', now() + interval '1 day') "
            "RETURNING last_practice_notice",
            (user_id,),
        ).scalar_one()
        assert notice is None
        notice = connection.exec_driver_sql(
            "UPDATE auth_sessions SET last_practice_notice = 3000000000 "
            "WHERE user_id = %s RETURNING last_practice_notice",
            (user_id,),
        ).scalar_one()
        assert notice == 3000000000

    print(f"Populated 0003 upgraded to {head}; all six legacy rows preserved.")
    command.check(config)


if __name__ == "__main__":
    main()
