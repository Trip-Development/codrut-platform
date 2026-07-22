"""convert email sends into a durable delivery outbox

Revision ID: 0038_durable_email_outbox
Revises: 0037_protected_content_boundary
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038_durable_email_outbox"
down_revision: str | None = "0037_protected_content_boundary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL requires enum additions to be committed before the values can be
    # referenced by constraints or DML in the same migration.
    with op.get_context().autocommit_block():
        op.execute("alter type emailsendstatus add value if not exists 'dispatching'")
        op.execute("alter type emailsendstatus add value if not exists 'cancelled'")
        op.execute("alter type emaileventtype add value if not exists 'queued'")
        op.execute("alter type emaileventtype add value if not exists 'claimed'")
        op.execute("alter type emaileventtype add value if not exists 'retry_scheduled'")
        op.execute("alter type emaileventtype add value if not exists 'cancelled'")

    op.add_column(
        "email_sends",
        sa.Column(
            "message_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "email_sends",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "email_sends",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "email_sends",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "email_sends",
        sa.Column("lease_token", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "email_sends",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Legacy queued rows contain no rendered message and therefore cannot be
    # retried safely. Fail them explicitly instead of reconstructing mutable data.
    op.execute(
        """
        update email_sends
        set status = 'failed',
            error_details = coalesce(
                error_details,
                'Legacy queued delivery has no immutable outbox payload.'
            ),
            lease_expires_at = null,
            last_event_at = now()
        where status = 'queued'
          and message_payload is null
        """
    )

    op.create_check_constraint(
        "ck_email_sends_outbox_payload_present",
        "email_sends",
        "status not in ('queued', 'dispatching') or message_payload is not null",
    )
    op.create_check_constraint(
        "ck_email_sends_outbox_attempt_bounds",
        "email_sends",
        "attempt_count >= 0 and max_attempts > 0 and attempt_count <= max_attempts",
    )
    op.create_check_constraint(
        "ck_email_sends_outbox_next_attempt_present",
        "email_sends",
        "status <> 'queued' or next_attempt_at is not null",
    )
    op.create_index(
        "ix_email_sends_outbox_due",
        "email_sends",
        ["status", "next_attempt_at", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_sends_outbox_due", table_name="email_sends")
    op.drop_constraint(
        "ck_email_sends_outbox_next_attempt_present",
        "email_sends",
        type_="check",
    )
    op.drop_constraint(
        "ck_email_sends_outbox_attempt_bounds",
        "email_sends",
        type_="check",
    )
    op.drop_constraint(
        "ck_email_sends_outbox_payload_present",
        "email_sends",
        type_="check",
    )
    op.drop_column("email_sends", "cancelled_at")
    op.drop_column("email_sends", "lease_token")
    op.drop_column("email_sends", "next_attempt_at")
    op.drop_column("email_sends", "max_attempts")
    op.drop_column("email_sends", "attempt_count")
    op.drop_column("email_sends", "message_payload")

    # PostgreSQL enum values are intentionally retained on downgrade. Removing
    # enum values requires rebuilding each type and every dependent column.
