"""Repair project membership timestamp defaults.

Revision ID: 0020_project_member_timestamps
Revises: 0019_project_memberships
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_project_member_timestamps"
down_revision: str | None = "0019_project_memberships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE project_memberships
        SET
            created_at = COALESCE(created_at, now()),
            updated_at = COALESCE(updated_at, now())
        WHERE created_at IS NULL OR updated_at IS NULL
        """
    )
    op.alter_column(
        "project_memberships",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        existing_nullable=False,
    )
    op.alter_column(
        "project_memberships",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "project_memberships",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "project_memberships",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
