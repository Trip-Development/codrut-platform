"""add assignment tracking timestamps

Revision ID: 0006_assignment_tracking
Revises: 0005_assignment_domain
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_assignment_tracking"
down_revision: str | None = "0005_assignment_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


columns = (
    "due_at",
    "invited_at",
    "started_at",
    "submitted_at",
    "validated_at",
    "scored_at",
    "reminder_due_at",
    "last_reminder_sent_at",
)


def upgrade() -> None:
    for column_name in columns:
        op.add_column(
            "questionnaire_assignments",
            sa.Column(column_name, sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    for column_name in reversed(columns):
        op.drop_column("questionnaire_assignments", column_name)
