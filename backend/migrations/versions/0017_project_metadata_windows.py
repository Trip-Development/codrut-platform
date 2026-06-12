"""add project metadata and form windows

Revision ID: 0017_project_metadata_windows
Revises: 0016_participant_anonymous_name
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_project_metadata_windows"
down_revision: str | None = "0016_participant_anonymous_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "company_projects",
        sa.Column("project_type", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "company_projects",
        sa.Column("form_opens_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "company_projects",
        sa.Column("form_closes_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_projects", "form_closes_at")
    op.drop_column("company_projects", "form_opens_at")
    op.drop_column("company_projects", "project_type")
