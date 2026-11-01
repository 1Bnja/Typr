"""Prevent duplicate canonical phrases without touching existing rows.

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    duplicate = op.get_bind().execute(
        text("SELECT content FROM texts GROUP BY content HAVING count(*) > 1 LIMIT 1")
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "texts contains duplicate content; resolve those rows before applying 0002."
        )
    op.create_index("uq_texts_content", "texts", ["content"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_texts_content", table_name="texts")
