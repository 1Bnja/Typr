"""esquema inicial (supabase/db/init.sql)

Revision ID: 0001
Revises:
Create Date: 2026-10-04

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ponytail: la base sale de init.sql para no duplicar el esquema. Desde aca
# init.sql queda congelado: cualquier cambio va en una migracion nueva.
INIT_SQL = Path(__file__).resolve().parents[3] / "supabase" / "db" / "init.sql"

TABLES = ["users", "texts", "rooms", "room_members", "games", "game_participants"]
ENUMS = ["room_type", "game_mode", "room_status", "text_language", "difficulty"]


def upgrade() -> None:
    op.get_bind().exec_driver_sql(INIT_SQL.read_text(encoding="utf-8"))
    # Supabase expone el schema public por su API REST: RLS sin policies la
    # bloquea. El backend se conecta como postgres y no le afecta.
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for enum in ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
