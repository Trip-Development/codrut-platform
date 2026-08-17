"""add role-scoped invitation and reminder template keys to company projects

Revision ID: 0058_project_invite_templates
Revises: 0057_icare_assignment_cohorts
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0058_project_invite_templates"
down_revision: str | None = "0057_icare_assignment_cohorts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "company_projects",
        sa.Column(
            "leadership_invitation_template_key",
            sa.String(length=120),
            nullable=True,
        ),
    )
    op.add_column(
        "company_projects",
        sa.Column(
            "member_invitation_template_key",
            sa.String(length=120),
            nullable=True,
        ),
    )
    op.add_column(
        "company_projects",
        sa.Column(
            "leadership_reminder_template_key",
            sa.String(length=120),
            nullable=True,
        ),
    )
    op.add_column(
        "company_projects",
        sa.Column(
            "member_reminder_template_key",
            sa.String(length=120),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("company_projects", "member_reminder_template_key")
    op.drop_column("company_projects", "leadership_reminder_template_key")
    op.drop_column("company_projects", "member_invitation_template_key")
    op.drop_column("company_projects", "leadership_invitation_template_key")
