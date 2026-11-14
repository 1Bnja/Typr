"""Aplica migraciones y adopta de forma segura bases creadas con init.sql.

Las primeras instalaciones de Typr cargaban ``supabase/db/init.sql`` fuera de
Alembic. Esas bases no tienen ``alembic_version`` aunque equivalen a la revision
0001 (o a 0002 si el indice unico de textos se aplico manualmente). El deploy
usa este comando para registrar ese punto de partida una sola vez y luego
actualizar normalmente hasta ``head``.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.database import engine

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BASE_TABLES = {
    "users",
    "texts",
    "rooms",
    "room_members",
    "games",
    "game_participants",
}
MULTIPLAYER_ROOM_COLUMNS = {"code", "rounds", "time_limit_s"}


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    # Mantiene el comando independiente del directorio desde donde se invoque.
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def current_revision() -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def has_unique_index(inspector, table: str, name: str) -> bool:
    return any(
        index["name"] == name and index.get("unique", False)
        for index in inspector.get_indexes(table)
    )


def baseline_legacy_database(config: Config) -> str | None:
    """Marca una base legacy completa; rechaza esquemas parciales o ambiguos."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    existing_base = tables & BASE_TABLES
    if not existing_base:
        return None  # Base vacia: Alembic ejecutara 0001 normalmente.
    if existing_base != BASE_TABLES:
        missing = ", ".join(sorted(BASE_TABLES - existing_base))
        raise RuntimeError(
            "La base no tiene historial de Alembic y su esquema esta incompleto; "
            f"faltan las tablas: {missing}. No se aplicaron cambios."
        )

    room_columns = {column["name"] for column in inspector.get_columns("rooms")}
    member_columns = {
        column["name"] for column in inspector.get_columns("room_members")
    }
    multiplayer_columns = (room_columns & MULTIPLAYER_ROOM_COLUMNS) | (
        {"is_ready"} if "is_ready" in member_columns else set()
    )
    if multiplayer_columns:
        found = ", ".join(sorted(multiplayer_columns))
        raise RuntimeError(
            "La base no tiene historial de Alembic pero contiene cambios parciales "
            f"de multiplayer ({found}). No se aplicaron cambios; revisala manualmente."
        )

    revision = (
        "0002"
        if has_unique_index(inspector, "texts", "uq_texts_content")
        else "0001"
    )
    command.stamp(config, revision)
    return revision


def main() -> None:
    config = alembic_config()
    revision = current_revision()
    if revision is None:
        revision = baseline_legacy_database(config)
        if revision is not None:
            print(f"Base existente registrada en Alembic como {revision}.")
    command.upgrade(config, "head")
    print(f"Migraciones aplicadas. Revision actual: {current_revision()}.")


if __name__ == "__main__":
    main()
