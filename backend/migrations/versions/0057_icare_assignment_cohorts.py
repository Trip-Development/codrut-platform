"""persist iCARE assignment cohorts

Revision ID: 0057_icare_assignment_cohorts
Revises: 0056_email_send_sandbox_scope
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0057_icare_assignment_cohorts"
down_revision: str | None = "0056_email_send_sandbox_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def _backfill_self(bind: sa.Connection) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE questionnaire_assignments
            SET icare_cohort = 'self'
            WHERE icare_cohort IS NULL
              AND questionnaire_key IN ('boss_360', 'boss_360_en', 'icare')
              AND (
                target_type = 'self'
                OR (target_type = 'person' AND respondent_profile_id = target_person_id)
              )
            """
        )
    )


def _backfill_leadership_peers(bind: sa.Connection) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE questionnaire_assignments AS assignment
            SET icare_cohort = 'leadership_peers'
            WHERE assignment.icare_cohort IS NULL
              AND assignment.assessment_cycle_id IS NOT NULL
              AND assignment.questionnaire_key IN ('boss_360', 'boss_360_en', 'icare')
              AND assignment.target_type = 'person'
              AND assignment.respondent_profile_id <> assignment.target_person_id
              AND EXISTS (
                SELECT 1
                FROM assessment_cycle_team_memberships AS target_membership
                JOIN teams AS target_team ON target_team.id = target_membership.team_id
                WHERE target_membership.assessment_cycle_id = assignment.assessment_cycle_id
                  AND target_membership.participant_profile_id = assignment.target_person_id
                  AND target_team.type = 'leadership'
              )
              AND EXISTS (
                SELECT 1
                FROM assessment_cycle_team_memberships AS respondent_membership
                JOIN teams AS respondent_team ON respondent_team.id = respondent_membership.team_id
                WHERE respondent_membership.assessment_cycle_id = assignment.assessment_cycle_id
                  AND respondent_membership.participant_profile_id =
                      assignment.respondent_profile_id
                  AND respondent_team.type = 'leadership'
              )
            """
        )
    )


def _backfill_direct_team(bind: sa.Connection) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE questionnaire_assignments AS assignment
            SET icare_cohort = 'direct_team'
            WHERE assignment.icare_cohort IS NULL
              AND assignment.assessment_cycle_id IS NOT NULL
              AND assignment.questionnaire_key IN ('boss_360', 'boss_360_en', 'icare')
              AND assignment.target_type = 'person'
              AND EXISTS (
                SELECT 1
                FROM assessment_cycle_team_memberships AS target_membership
                JOIN teams AS team ON team.id = target_membership.team_id
                JOIN assessment_cycle_team_memberships AS respondent_membership
                  ON respondent_membership.assessment_cycle_id =
                     target_membership.assessment_cycle_id
                 AND respondent_membership.team_id = target_membership.team_id
                WHERE target_membership.assessment_cycle_id = assignment.assessment_cycle_id
                  AND target_membership.participant_profile_id = assignment.target_person_id
                  AND target_membership.role = 'leader'
                  AND team.type = 'functional'
                  AND respondent_membership.participant_profile_id =
                      assignment.respondent_profile_id
              )
              AND NOT EXISTS (
                SELECT 1
                FROM assessment_cycle_team_memberships AS leadership_membership
                JOIN teams AS leadership_team ON leadership_team.id = leadership_membership.team_id
                WHERE leadership_membership.assessment_cycle_id = assignment.assessment_cycle_id
                  AND leadership_membership.participant_profile_id =
                      assignment.respondent_profile_id
                  AND leadership_team.type = 'leadership'
              )
            """
        )
    )


def upgrade() -> None:
    op.add_column(
        "questionnaire_assignments",
        sa.Column("icare_cohort", sa.String(length=32), nullable=True),
    )
    bind = op.get_bind()
    _backfill_self(bind)
    _backfill_leadership_peers(bind)
    _backfill_direct_team(bind)
    op.create_check_constraint(
        "questionnaire_assignment_icare_cohort",
        "questionnaire_assignments",
        "icare_cohort is null or icare_cohort in "
        "('direct_team', 'leadership_peers', 'self')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "questionnaire_assignment_icare_cohort",
        "questionnaire_assignments",
        type_="check",
    )
    op.drop_column("questionnaire_assignments", "icare_cohort")
