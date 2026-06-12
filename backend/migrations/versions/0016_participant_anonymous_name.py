"""add participant anonymous display name

Revision ID: 0016_participant_anonymous_name
Revises: 0015_assignment_projects
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_participant_anonymous_name"
down_revision: str | None = "0015_assignment_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "participant_profiles",
        sa.Column("anonymous_name", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("participant_profiles", "anonymous_name")
