"""add icare questionnaire key

Revision ID: 7f6d8f0c9b21
Revises: d60b3aab2766
Create Date: 2026-06-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "7f6d8f0c9b21"
down_revision: str | None = "d60b3aab2766"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE questionnairekey ADD VALUE IF NOT EXISTS 'icare'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely in ordinary downgrades.
    pass
