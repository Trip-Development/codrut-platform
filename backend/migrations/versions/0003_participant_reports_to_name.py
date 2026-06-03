"""add participant reports to roster field

Revision ID: 0003_participant_reports_to_name
Revises: 0002_company_participant_admin
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_participant_reports_to_name"
down_revision: str | None = "0002_company_participant_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "participant_profiles",
        sa.Column("reports_to_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("participant_profiles", "reports_to_name")
