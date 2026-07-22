"""add longitudinal assessment cycles and multi-profile accounts

Revision ID: 0045_assessment_cycles
Revises: 0044_communications_hardening
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0045_assessment_cycles"
down_revision: str | None = "0044_communications_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("alter type assignmentstatus add value if not exists 'cancelled'")

    cycle_status = postgresql.ENUM(
        "draft",
        "active",
        "closed",
        name="assessmentcyclestatus",
        create_type=False,
    )
    cycle_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assessment_cycles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", cycle_status, nullable=False),
        sa.Column("source_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint("sequence > 0", name="ck_assessment_cycles_sequence_positive"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["company_projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_cycle_id"], ["assessment_cycles.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assessment_cycles"),
        sa.UniqueConstraint(
            "project_id", "sequence", name="uq_assessment_cycles_project_sequence"
        ),
    )
    for column_name in ("company_id", "project_id", "source_cycle_id", "created_by_user_id"):
        op.create_index(
            op.f(f"ix_assessment_cycles_{column_name}"),
            "assessment_cycles",
            [column_name],
        )
    op.create_index(
        "uq_assessment_cycles_open_project",
        "assessment_cycles",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status in ('draft', 'active')"),
    )

    op.create_table(
        "assessment_cycle_questionnaires",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_definition_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_key", sa.String(length=120), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
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
            ["assessment_cycle_id"], ["assessment_cycles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["questionnaire_definition_id"],
            ["questionnaire_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assessment_cycle_questionnaires"),
        sa.UniqueConstraint(
            "assessment_cycle_id",
            "questionnaire_key",
            name="uq_assessment_cycle_questionnaires_cycle_key",
        ),
    )
    op.create_index(
        op.f("ix_assessment_cycle_questionnaires_assessment_cycle_id"),
        "assessment_cycle_questionnaires",
        ["assessment_cycle_id"],
    )
    op.create_index(
        op.f("ix_assessment_cycle_questionnaires_questionnaire_definition_id"),
        "assessment_cycle_questionnaires",
        ["questionnaire_definition_id"],
    )

    op.add_column(
        "questionnaire_assignments",
        sa.Column("assessment_cycle_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_questionnaire_assignments_assessment_cycle_id_assessment_cycles"),
        "questionnaire_assignments",
        "assessment_cycles",
        ["assessment_cycle_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_questionnaire_assignments_assessment_cycle_id"),
        "questionnaire_assignments",
        ["assessment_cycle_id"],
    )

    op.add_column(
        "result_publications",
        sa.Column("assessment_cycle_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_result_publications_assessment_cycle_id_assessment_cycles"),
        "result_publications",
        "assessment_cycles",
        ["assessment_cycle_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_result_publications_assessment_cycle_id"),
        "result_publications",
        ["assessment_cycle_id"],
    )

    # One product cycle groups the current project history without changing the
    # immutable round IDs used by legacy privacy aggregation.
    op.execute(
        """
        insert into assessment_cycles (
            id, company_id, project_id, sequence, name, status,
            starts_at, due_at, closed_at, created_at, updated_at
        )
        select
            gen_random_uuid(), project.company_id, project.id, 1, 'Evaluare inițială',
            case
                when project.status::text in ('completed', 'archived')
                    then 'closed'::assessmentcyclestatus
                when exists (
                    select 1 from questionnaire_assignments assignment
                    where assignment.project_id = project.id
                ) then 'active'::assessmentcyclestatus
                else 'draft'::assessmentcyclestatus
            end,
            project.starts_at, project.due_at,
            case when project.status::text in ('completed', 'archived') then now() else null end,
            now(), now()
        from company_projects project
        """
    )
    op.execute(
        """
        update questionnaire_assignments assignment
        set assessment_cycle_id = cycle.id
        from assessment_cycles cycle
        where assignment.project_id = cycle.project_id
          and cycle.sequence = 1
        """
    )
    op.execute(
        """
        with ranked_questionnaires as (
            select
                assignment.assessment_cycle_id,
                assignment.questionnaire_definition_id,
                assignment.questionnaire_key,
                assignment.created_at,
                row_number() over (
                    partition by assignment.assessment_cycle_id, assignment.questionnaire_key
                    order by assignment.created_at desc, assignment.id desc
                ) as definition_rank
            from questionnaire_assignments assignment
            where assignment.assessment_cycle_id is not null
              and assignment.questionnaire_definition_id is not null
        )
        insert into assessment_cycle_questionnaires (
            id, assessment_cycle_id, questionnaire_definition_id,
            questionnaire_key, display_order, created_at, updated_at
        )
        select
            gen_random_uuid(), questionnaire.assessment_cycle_id,
            questionnaire.questionnaire_definition_id, questionnaire.questionnaire_key,
            row_number() over (
                partition by questionnaire.assessment_cycle_id
                order by questionnaire.created_at, questionnaire.questionnaire_key
            ) - 1,
            now(), now()
        from ranked_questionnaires questionnaire
        where questionnaire.definition_rank = 1
        """
    )
    op.execute(
        """
        update result_publications publication
        set assessment_cycle_id = assignment.assessment_cycle_id
        from questionnaire_assignments assignment
        where publication.source_assignment_id = assignment.id
          and assignment.assessment_cycle_id is not null
        """
    )
    op.execute(
        """
        update result_publications publication
        set assessment_cycle_id = cycle.id
        from assessment_cycles cycle
        where publication.assessment_cycle_id is null
          and publication.project_id = cycle.project_id
          and cycle.sequence = 1
        """
    )
    # Alembic runs the statements below in its migration transaction. Rebuild only
    # the exact legacy aggregate shape so a partially-applied migration remains
    # idempotent and an already cycle-aware publication is left untouched.
    op.execute(
        """
        do $$
        begin
            if exists (
                select 1
                from result_publications publication
                join result_publications conflicting
                  on conflicting.publication_key = concat_ws(
                      ':',
                      'aggregate-360',
                      publication.participant_profile_id::text,
                      coalesce(publication.project_id::text, 'none'),
                      coalesce(publication.assessment_cycle_id::text, 'legacy'),
                      publication.assignment_round_id::text,
                      coalesce(
                          publication.questionnaire_definition_id::text,
                          publication.questionnaire_key
                      )
                  )
                 and conflicting.id <> publication.id
                where publication.kind = 'aggregate_360'
                  and publication.publication_key = concat_ws(
                      ':',
                      'aggregate-360',
                      publication.participant_profile_id::text,
                      coalesce(publication.project_id::text, 'none'),
                      publication.assignment_round_id::text,
                      coalesce(
                          publication.questionnaire_definition_id::text,
                          publication.questionnaire_key
                      )
                  )
            ) then
                raise exception using message =
                    'Cannot migrate legacy aggregate result publications: '
                    || 'cycle-aware publication_key already exists';
            end if;
        end $$;
        """
    )
    op.execute(
        """
        update result_publications publication
        set publication_key = concat_ws(
            ':',
            'aggregate-360',
            publication.participant_profile_id::text,
            coalesce(publication.project_id::text, 'none'),
            coalesce(publication.assessment_cycle_id::text, 'legacy'),
            publication.assignment_round_id::text,
            coalesce(
                publication.questionnaire_definition_id::text,
                publication.questionnaire_key
            )
        )
        where publication.kind = 'aggregate_360'
          and publication.publication_key = concat_ws(
              ':',
              'aggregate-360',
              publication.participant_profile_id::text,
              coalesce(publication.project_id::text, 'none'),
              publication.assignment_round_id::text,
              coalesce(
                  publication.questionnaire_definition_id::text,
                  publication.questionnaire_key
              )
          )
        """
    )

    op.drop_constraint(
        "uq_participant_profiles_user_id",
        "participant_profiles",
        type_="unique",
    )


def downgrade() -> None:
    # The preflight deliberately refuses a destructive downgrade. The 0044
    # schema permits one profile per user and one aggregate key per legacy
    # round, whereas 0045 permits multiple profiles and cycles.
    op.execute(
        """
        do $$
        begin
            if exists (
                select 1
                from participant_profiles
                where user_id is not null
                group by user_id
                having count(*) > 1
            ) then
                raise exception
                    'Cannot downgrade 0045_assessment_cycles: multi-profile accounts exist';
            end if;

            if exists (
                select 1
                from result_publications publication
                where publication.kind = 'aggregate_360'
                group by
                    publication.participant_profile_id,
                    publication.project_id,
                    publication.assignment_round_id,
                    coalesce(
                        publication.questionnaire_definition_id::text,
                        publication.questionnaire_key
                    )
                having count(*) > 1
            ) then
                raise exception using message =
                    'Cannot downgrade 0045_assessment_cycles: multiple aggregate '
                    || 'publications would collapse to one legacy publication_key';
            end if;
        end $$;
        """
    )
    op.execute(
        """
        update result_publications publication
        set publication_key = concat_ws(
            ':',
            'aggregate-360',
            publication.participant_profile_id::text,
            coalesce(publication.project_id::text, 'none'),
            publication.assignment_round_id::text,
            coalesce(
                publication.questionnaire_definition_id::text,
                publication.questionnaire_key
            )
        )
        where publication.kind = 'aggregate_360'
          and publication.publication_key = concat_ws(
              ':',
              'aggregate-360',
              publication.participant_profile_id::text,
              coalesce(publication.project_id::text, 'none'),
              coalesce(publication.assessment_cycle_id::text, 'legacy'),
              publication.assignment_round_id::text,
              coalesce(
                  publication.questionnaire_definition_id::text,
                  publication.questionnaire_key
              )
          )
        """
    )
    op.create_unique_constraint(
        "uq_participant_profiles_user_id",
        "participant_profiles",
        ["user_id"],
    )
    op.drop_index(
        op.f("ix_result_publications_assessment_cycle_id"),
        table_name="result_publications",
    )
    op.drop_constraint(
        op.f("fk_result_publications_assessment_cycle_id_assessment_cycles"),
        "result_publications",
        type_="foreignkey",
    )
    op.drop_column("result_publications", "assessment_cycle_id")
    op.drop_index(
        op.f("ix_questionnaire_assignments_assessment_cycle_id"),
        table_name="questionnaire_assignments",
    )
    op.drop_constraint(
        op.f("fk_questionnaire_assignments_assessment_cycle_id_assessment_cycles"),
        "questionnaire_assignments",
        type_="foreignkey",
    )
    op.drop_column("questionnaire_assignments", "assessment_cycle_id")
    op.drop_table("assessment_cycle_questionnaires")
    op.drop_table("assessment_cycles")
    postgresql.ENUM(name="assessmentcyclestatus").drop(op.get_bind(), checkfirst=True)
    # PostgreSQL assignment enum values are intentionally retained.
