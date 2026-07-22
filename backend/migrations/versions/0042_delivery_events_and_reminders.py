"""track provider events and bounded reminder rounds

Revision ID: 0042_delivery_events_reminders
Revises: 0041_assignment_rounds
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042_delivery_events_reminders"
down_revision: str | None = "0041_assignment_rounds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("alter type emaileventtype add value if not exists 'unsubscribed'")
        op.execute("alter type emaileventtype add value if not exists 'complained'")

    op.add_column(
        "questionnaire_assignments",
        sa.Column("reminder_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_questionnaire_assignments_reminder_count_bounds",
        "questionnaire_assignments",
        "reminder_count >= 0 and reminder_count <= 2",
    )
    op.create_index(
        "uq_email_events_provider_event_id",
        "email_events",
        ["provider_event_id"],
        unique=True,
        postgresql_where=sa.text("provider_event_id is not null"),
    )


def downgrade() -> None:
    op.drop_index("uq_email_events_provider_event_id", table_name="email_events")
    op.drop_constraint(
        "ck_questionnaire_assignments_reminder_count_bounds",
        "questionnaire_assignments",
        type_="check",
    )
    op.drop_column("questionnaire_assignments", "reminder_count")
