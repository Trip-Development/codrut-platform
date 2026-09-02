"""add show_participant_results column to company_projects

Revision ID: 0060_show_participant_results
Revises: 0059_participant_view_audits
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0060_show_participant_results"
down_revision: str | None = "0059_participant_view_audits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "company_projects",
        sa.Column(
            "show_participant_results",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("company_projects", "show_participant_results")
