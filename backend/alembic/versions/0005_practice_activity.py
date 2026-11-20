"""Track the last practice activity notice per HTTP session."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("last_practice_notice", sa.BigInteger()))


def downgrade() -> None:
    op.drop_column("auth_sessions", "last_practice_notice")
