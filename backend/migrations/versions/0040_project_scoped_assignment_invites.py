"""scope assignment invitations to a project

Revision ID: 0040_project_scoped_invites
Revises: 0039_consent_acceptance_audit
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_project_scoped_invites"
down_revision: str | None = "0039_consent_acceptance_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assignment_invites",
        sa.Column("project_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_assignment_invites_project_id_company_projects"),
        "assignment_invites",
        "company_projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_assignment_invites_project_id"),
        "assignment_invites",
        ["project_id"],
        unique=False,
    )

    # Preserve a legacy session when its participant has exactly one active
    # invitation. Multiple active invitations are ambiguous and cannot be
    # restricted safely without a new link exchange.
    op.execute(
        sa.text(
            """
            WITH unique_invites AS (
                SELECT
                    session.id AS session_id,
                    min(invite.id::text)::uuid AS invite_id
                FROM sessions session
                JOIN users app_user ON app_user.id = session.user_id
                JOIN participant_profiles profile ON profile.user_id = app_user.id
                JOIN assignment_invites invite
                  ON invite.respondent_profile_id = profile.id
                 AND invite.company_id = profile.company_id
                 AND invite.status = 'active'
                 AND invite.expires_at > now()
                WHERE session.assignment_invite_id IS NULL
                  AND app_user.password_hash = 'shadow_account_no_password'
                GROUP BY session.id
                HAVING count(*) = 1
            )
            UPDATE sessions session
            SET assignment_invite_id = unique_invites.invite_id
            FROM unique_invites
            WHERE session.id = unique_invites.session_id
            """
        )
    )

    # Remaining legacy shadow sessions have no unique authorization scope.
    # Their signed links remain valid and create a correctly scoped session on reuse.
    op.execute(
        sa.text(
            """
            DELETE FROM sessions
            WHERE assignment_invite_id IS NULL
              AND user_id IN (
                SELECT id FROM users WHERE password_hash = 'shadow_account_no_password'
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_assignment_invites_project_id"), table_name="assignment_invites")
    op.drop_constraint(
        op.f("fk_assignment_invites_project_id_company_projects"),
        "assignment_invites",
        type_="foreignkey",
    )
    op.drop_column("assignment_invites", "project_id")
