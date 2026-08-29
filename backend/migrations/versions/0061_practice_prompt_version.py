"""add prompt_version to practice_sessions

Revision ID: 0061_practice_prompt_version
Revises: 0060_practice_schema
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061_practice_prompt_version"
down_revision: str | None = "0060_practice_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_sessions",
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("practice_sessions", "prompt_version")
