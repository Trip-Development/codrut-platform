"""enforce assessment cycle assignment integrity

Revision ID: 0046_assessment_cycle_integrity
Revises: 0045_assessment_cycles
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0046_assessment_cycle_integrity"
down_revision: str | None = "0045_assessment_cycles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessment_cycle_team_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(name="teammembershiprole", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assessment_cycle_id"],
            ["assessment_cycles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["participant_profile_id"],
            ["participant_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assessment_cycle_team_memberships"),
        sa.UniqueConstraint(
            "assessment_cycle_id",
            "team_id",
            "participant_profile_id",
            name="uq_assessment_cycle_team_memberships_member",
        ),
    )
    for column_name in ("assessment_cycle_id", "team_id", "participant_profile_id"):
        op.create_index(
            op.f(f"ix_assessment_cycle_team_memberships_{column_name}"),
            "assessment_cycle_team_memberships",
            [column_name],
        )

    op.execute(
        """
        insert into assessment_cycle_team_memberships (
            id,
            assessment_cycle_id,
            team_id,
            participant_profile_id,
            role,
            created_at,
            updated_at
        )
        select
            gen_random_uuid(),
            snapshot.assessment_cycle_id,
            snapshot.team_id,
            snapshot.participant_profile_id,
            snapshot.role,
            now(),
            now()
        from (
            select distinct
                assignment.assessment_cycle_id,
                membership.team_id,
                membership.participant_profile_id,
                membership.role
            from questionnaire_assignments assignment
            join team_memberships membership on membership.team_id = assignment.target_team_id
            where assignment.assessment_cycle_id is not null
              and assignment.target_type = 'team'
        ) snapshot
        """
    )

    op.add_column(
        "questionnaire_assignments",
        sa.Column("cycle_shape_guard", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_assignments_cycle_shape_guard",
        "questionnaire_assignments",
        "assessment_cycles",
        ["cycle_shape_guard"],
        ["id"],
        ondelete="SET NULL",
    )

    # Preserve legitimate legacy duplicate rounds. New application writes always
    # set the guard; unique legacy shapes can safely opt into the same invariant.
    op.execute(
        """
        with shape_counts as (
            select
                assessment_cycle_id,
                respondent_profile_id,
                questionnaire_key,
                target_type,
                target_person_id,
                target_team_id,
                count(*) as row_count
            from questionnaire_assignments
            where assessment_cycle_id is not null
            group by
                assessment_cycle_id,
                respondent_profile_id,
                questionnaire_key,
                target_type,
                target_person_id,
                target_team_id
        )
        update questionnaire_assignments assignment
        set cycle_shape_guard = assignment.assessment_cycle_id
        from shape_counts shape
        where assignment.assessment_cycle_id = shape.assessment_cycle_id
          and assignment.respondent_profile_id = shape.respondent_profile_id
          and assignment.questionnaire_key = shape.questionnaire_key
          and assignment.target_type = shape.target_type
          and assignment.target_person_id is not distinct from shape.target_person_id
          and assignment.target_team_id is not distinct from shape.target_team_id
          and shape.row_count = 1
        """
    )
    op.execute(
        """
        create unique index uq_questionnaire_assignments_cycle_shape
        on questionnaire_assignments (
            cycle_shape_guard,
            respondent_profile_id,
            questionnaire_key,
            target_type,
            coalesce(target_person_id, '00000000-0000-0000-0000-000000000000'::uuid),
            coalesce(target_team_id, '00000000-0000-0000-0000-000000000000'::uuid)
        )
        where cycle_shape_guard is not null
        """
    )


def downgrade() -> None:
    op.drop_index(
        "uq_questionnaire_assignments_cycle_shape",
        table_name="questionnaire_assignments",
    )
    op.drop_constraint(
        "fk_assignments_cycle_shape_guard",
        "questionnaire_assignments",
        type_="foreignkey",
    )
    op.drop_column("questionnaire_assignments", "cycle_shape_guard")
    op.drop_table("assessment_cycle_team_memberships")
