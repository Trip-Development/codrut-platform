"""create assignment domain

Revision ID: 0005_assignment_domain
Revises: 0004_company_access_codes
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_assignment_domain"
down_revision: str | None = "0004_company_access_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


team_type = postgresql.ENUM("leadership", "functional", name="teamtype", create_type=False)
team_membership_role = postgresql.ENUM(
    "leader",
    "member",
    name="teammembershiprole",
    create_type=False,
)
assignment_target_type = postgresql.ENUM(
    "self",
    "person",
    "team",
    name="assignmenttargettype",
    create_type=False,
)
assignment_access_mode = postgresql.ENUM(
    "account_link",
    name="assignmentaccessmode",
    create_type=False,
)
assignment_status = postgresql.ENUM(
    "assigned",
    "invited",
    "started",
    "submitted",
    "validated",
    "scored",
    name="assignmentstatus",
    create_type=False,
)
response_visibility_policy = postgresql.ENUM(
    "trainer_raw_review",
    "reviewed_anonymized",
    name="responsevisibilitypolicy",
    create_type=False,
)


def upgrade() -> None:
    team_type.create(op.get_bind(), checkfirst=True)
    team_membership_role.create(op.get_bind(), checkfirst=True)
    assignment_target_type.create(op.get_bind(), checkfirst=True)
    assignment_access_mode.create(op.get_bind(), checkfirst=True)
    assignment_status.create(op.get_bind(), checkfirst=True)
    response_visibility_policy.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", team_type, nullable=False),
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
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_teams_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
        sa.UniqueConstraint("company_id", "name", name=op.f("uq_teams_company_id")),
    )
    op.create_index(op.f("ix_teams_company_id"), "teams", ["company_id"])

    op.create_table(
        "team_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column("role", team_membership_role, nullable=False),
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
        sa.ForeignKeyConstraint(
            ["participant_profile_id"],
            ["participant_profiles.id"],
            name=op.f("fk_team_memberships_participant_profile_id_participant_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name=op.f("fk_team_memberships_team_id_teams"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_memberships")),
        sa.UniqueConstraint(
            "team_id",
            "participant_profile_id",
            name=op.f("uq_team_memberships_team_id"),
        ),
    )
    op.create_index(
        op.f("ix_team_memberships_participant_profile_id"),
        "team_memberships",
        ["participant_profile_id"],
    )
    op.create_index(op.f("ix_team_memberships_team_id"), "team_memberships", ["team_id"])

    op.create_table(
        "questionnaire_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("respondent_profile_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_key", sa.String(length=120), nullable=False),
        sa.Column("target_type", assignment_target_type, nullable=False),
        sa.Column("target_person_id", sa.Uuid(), nullable=True),
        sa.Column("target_team_id", sa.Uuid(), nullable=True),
        sa.Column("access_mode", assignment_access_mode, nullable=False),
        sa.Column("status", assignment_status, nullable=False),
        sa.Column("visibility_policy", response_visibility_policy, nullable=False),
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
        sa.CheckConstraint(
            """
            (
              target_type = 'self'
              and target_person_id is null
              and target_team_id is null
            )
            or (
              target_type = 'person'
              and target_person_id is not null
              and target_team_id is null
            )
            or (
              target_type = 'team'
              and target_team_id is not null
              and target_person_id is null
            )
            """,
            name=op.f("ck_questionnaire_assignments_assignment_target_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_questionnaire_assignments_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["respondent_profile_id"],
            ["participant_profiles.id"],
            name=op.f("fk_questionnaire_assignments_respondent_profile_id_participant_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_person_id"],
            ["participant_profiles.id"],
            name=op.f("fk_questionnaire_assignments_target_person_id_participant_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_team_id"],
            ["teams.id"],
            name=op.f("fk_questionnaire_assignments_target_team_id_teams"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questionnaire_assignments")),
    )
    op.create_index(
        op.f("ix_questionnaire_assignments_company_id"),
        "questionnaire_assignments",
        ["company_id"],
    )
    op.create_index(
        op.f("ix_questionnaire_assignments_respondent_profile_id"),
        "questionnaire_assignments",
        ["respondent_profile_id"],
    )
    op.create_index(
        op.f("ix_questionnaire_assignments_target_person_id"),
        "questionnaire_assignments",
        ["target_person_id"],
    )
    op.create_index(
        op.f("ix_questionnaire_assignments_target_team_id"),
        "questionnaire_assignments",
        ["target_team_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_questionnaire_assignments_target_team_id"),
        table_name="questionnaire_assignments",
    )
    op.drop_index(
        op.f("ix_questionnaire_assignments_target_person_id"),
        table_name="questionnaire_assignments",
    )
    op.drop_index(
        op.f("ix_questionnaire_assignments_respondent_profile_id"),
        table_name="questionnaire_assignments",
    )
    op.drop_index(
        op.f("ix_questionnaire_assignments_company_id"),
        table_name="questionnaire_assignments",
    )
    op.drop_table("questionnaire_assignments")
    op.drop_index(op.f("ix_team_memberships_team_id"), table_name="team_memberships")
    op.drop_index(
        op.f("ix_team_memberships_participant_profile_id"),
        table_name="team_memberships",
    )
    op.drop_table("team_memberships")
    op.drop_index(op.f("ix_teams_company_id"), table_name="teams")
    op.drop_table("teams")
    response_visibility_policy.drop(op.get_bind(), checkfirst=True)
    assignment_status.drop(op.get_bind(), checkfirst=True)
    assignment_access_mode.drop(op.get_bind(), checkfirst=True)
    assignment_target_type.drop(op.get_bind(), checkfirst=True)
    team_membership_role.drop(op.get_bind(), checkfirst=True)
    team_type.drop(op.get_bind(), checkfirst=True)
