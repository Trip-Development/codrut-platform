"""add project scope to assignments

Revision ID: 0015_assignment_projects
Revises: 0014_company_projects
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_assignment_projects"
down_revision: str | None = "0014_company_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "questionnaire_assignments",
        sa.Column("project_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_questionnaire_assignments_project_id"),
        "questionnaire_assignments",
        ["project_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_questionnaire_assignments_project_id_company_projects"),
        "questionnaire_assignments",
        "company_projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_questionnaire_assignments_project_id_company_projects"),
        "questionnaire_assignments",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_questionnaire_assignments_project_id"),
        table_name="questionnaire_assignments",
    )
    op.drop_column("questionnaire_assignments", "project_id")
