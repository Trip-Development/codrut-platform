"""Add project memberships for project-scoped rosters.

Revision ID: 0019_project_memberships
Revises: 0018_user_terms_acceptance
Create Date: 2026-06-12 22:05:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0019_project_memberships"
down_revision: str | None = "0018_user_terms_acceptance"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "project_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column("reports_to_name", sa.String(length=255), nullable=True),
        sa.Column("position", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("role_group", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["company_id", "participant_profile_id"],
            ["participant_profiles.company_id", "participant_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "participant_profile_id"),
    )
    op.create_index(
        op.f("ix_project_memberships_company_id"),
        "project_memberships",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_memberships_participant_profile_id"),
        "project_memberships",
        ["participant_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_memberships_project_id"),
        "project_memberships",
        ["project_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO project_memberships (
            id,
            company_id,
            project_id,
            participant_profile_id,
            reports_to_name,
            position,
            location,
            role_group,
            active,
            notes,
            created_at,
            updated_at
        )
        SELECT
            md5(random()::text || clock_timestamp()::text)::uuid,
            qa.company_id,
            qa.project_id,
            qa.respondent_profile_id,
            pp.reports_to_name,
            pp.position,
            pp.location,
            pp.role_group,
            true,
            null,
            now(),
            now()
        FROM questionnaire_assignments qa
        JOIN participant_profiles pp
            ON pp.id = qa.respondent_profile_id
            AND pp.company_id = qa.company_id
        WHERE qa.project_id IS NOT NULL
        GROUP BY
            qa.company_id,
            qa.project_id,
            qa.respondent_profile_id,
            pp.reports_to_name,
            pp.position,
            pp.location,
            pp.role_group
        ON CONFLICT (project_id, participant_profile_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_memberships_project_id"), table_name="project_memberships")
    op.drop_index(
        op.f("ix_project_memberships_participant_profile_id"),
        table_name="project_memberships",
    )
    op.drop_index(op.f("ix_project_memberships_company_id"), table_name="project_memberships")
    op.drop_table("project_memberships")
