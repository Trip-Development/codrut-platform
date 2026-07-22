"""link invite-derived sessions to their assignment invite

Revision ID: 0034_invite_session_link
Revises: 0033_email_send_idempotency
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_invite_session_link"
down_revision: str | None = "0033_email_send_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("assignment_invite_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_sessions_assignment_invite_id_assignment_invites"),
        "sessions",
        "assignment_invites",
        ["assignment_invite_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_sessions_assignment_invite_id"),
        "sessions",
        ["assignment_invite_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sessions_assignment_invite_id"), table_name="sessions")
    op.drop_constraint(
        op.f("fk_sessions_assignment_invite_id_assignment_invites"),
        "sessions",
        type_="foreignkey",
    )
    op.drop_column("sessions", "assignment_invite_id")
