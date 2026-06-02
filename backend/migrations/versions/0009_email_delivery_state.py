"""create email delivery state

Revision ID: 0009_email_delivery_state
Revises: 0008_questionnaire_responses
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_email_delivery_state"
down_revision: str | None = "0008_questionnaire_responses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


email_send_status = postgresql.ENUM(
    "queued",
    "accepted",
    "failed",
    "delivered",
    "bounced",
    name="emailsendstatus",
    create_type=False,
)
email_event_type = postgresql.ENUM(
    "accepted",
    "failed",
    "delivered",
    "bounced",
    "opened",
    "clicked",
    name="emaileventtype",
    create_type=False,
)


def upgrade() -> None:
    email_send_status.create(op.get_bind(), checkfirst=True)
    email_event_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "email_sends",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("template_key", sa.String(length=120), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("status", email_send_status, nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
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
            ["assignment_id"],
            ["questionnaire_assignments.id"],
            name=op.f("fk_email_sends_assignment_id_questionnaire_assignments"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_sends")),
    )
    op.create_index(op.f("ix_email_sends_assignment_id"), "email_sends", ["assignment_id"])
    op.create_index(
        op.f("ix_email_sends_provider_message_id"),
        "email_sends",
        ["provider_message_id"],
    )
    op.create_index(op.f("ix_email_sends_recipient_email"), "email_sends", ["recipient_email"])
    op.create_table(
        "email_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_send_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", email_event_type, nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
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
            ["email_send_id"],
            ["email_sends.id"],
            name=op.f("fk_email_events_email_send_id_email_sends"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_events")),
    )
    op.create_index(op.f("ix_email_events_email_send_id"), "email_events", ["email_send_id"])
    op.create_index(
        op.f("ix_email_events_provider_event_id"),
        "email_events",
        ["provider_event_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_events_provider_event_id"), table_name="email_events")
    op.drop_index(op.f("ix_email_events_email_send_id"), table_name="email_events")
    op.drop_table("email_events")
    op.drop_index(op.f("ix_email_sends_recipient_email"), table_name="email_sends")
    op.drop_index(op.f("ix_email_sends_provider_message_id"), table_name="email_sends")
    op.drop_index(op.f("ix_email_sends_assignment_id"), table_name="email_sends")
    op.drop_table("email_sends")
    email_event_type.drop(op.get_bind(), checkfirst=True)
    email_send_status.drop(op.get_bind(), checkfirst=True)
