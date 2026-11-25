"""Make completed practice submissions replayable per user."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    op.add_column("game_participants", sa.Column("practice_attempt_id", sa.Uuid()))
    op.add_column(
        "game_participants", sa.Column("practice_request_hash", sa.String(64))
    )
    op.create_unique_constraint(
        "uq_participants_practice_attempt",
        "game_participants",
        ["user_id", "practice_attempt_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_participants_practice_attempt", "game_participants", type_="unique"
    )
    op.drop_column("game_participants", "practice_request_hash")
    op.drop_column("game_participants", "practice_attempt_id")
