"""salas multijugador: codigo, rondas, tiempo limite y estado "listo"

Revision ID: 0003
Revises: 0002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    duplicate = op.get_bind().execute(
        sa.text(
            "SELECT member_id FROM room_members "
            "GROUP BY member_id HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "room_members tiene usuarios en mas de una sala; "
            "deja una sola membresia por usuario antes de aplicar 0003."
        )

    # Las salas que ya existan reciben un codigo derivado de su id, que es
    # unico por construccion; las nuevas lo generan en el servidor.
    op.add_column("rooms", sa.Column("code", sa.String(6), nullable=True))
    op.execute("UPDATE rooms SET code = lpad(upper(to_hex(id)), 6, '0')")
    op.alter_column("rooms", "code", nullable=False)
    op.create_unique_constraint("uq_rooms_code", "rooms", ["code"])

    op.add_column(
        "rooms",
        sa.Column("rounds", sa.Integer(), nullable=False, server_default="1"),
    )
    # NULL = tiempo limite automatico (2 veces el tiempo ideal del texto).
    op.add_column("rooms", sa.Column("time_limit_s", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_rooms_rounds", "rooms", "rounds BETWEEN 1 AND 10")
    op.create_check_constraint(
        "ck_rooms_time_limit_s", "rooms", "time_limit_s BETWEEN 30 AND 600"
    )

    op.add_column(
        "room_members",
        sa.Column(
            "is_ready", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    # Un usuario pertenece a una sola sala a la vez: el indice por miembro
    # pasa a ser unico (y reemplaza al anterior, que quedaria duplicado).
    op.drop_index("ix_room_members_member_id", table_name="room_members")
    op.create_index(
        "uq_room_members_member_id", "room_members", ["member_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_room_members_member_id", table_name="room_members")
    op.create_index("ix_room_members_member_id", "room_members", ["member_id"])
    op.drop_column("room_members", "is_ready")
    op.drop_constraint("ck_rooms_time_limit_s", "rooms", type_="check")
    op.drop_constraint("ck_rooms_rounds", "rooms", type_="check")
    op.drop_column("rooms", "time_limit_s")
    op.drop_column("rooms", "rounds")
    op.drop_constraint("uq_rooms_code", "rooms", type_="unique")
    op.drop_column("rooms", "code")
