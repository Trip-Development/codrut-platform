"""add campaign recipient events

Revision ID: 0022_campaign_recipient_events
Revises: 0021_password_reset_tokens
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_campaign_recipient_events"
down_revision: str | None = "0021_password_reset_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_recipient_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("variant_key", sa.String(length=120), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
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
            ["recipient_id"],
            ["campaign_recipients.id"],
            name=op.f("fk_campaign_recipient_events_recipient_id_campaign_recipients"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_recipient_events")),
    )
    op.create_index(
        op.f("ix_campaign_recipient_events_event_type"),
        "campaign_recipient_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_recipient_events_recipient_id"),
        "campaign_recipient_events",
        ["recipient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_recipient_events_variant_key"),
        "campaign_recipient_events",
        ["variant_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_campaign_recipient_events_variant_key"),
        table_name="campaign_recipient_events",
    )
    op.drop_index(
        op.f("ix_campaign_recipient_events_recipient_id"),
        table_name="campaign_recipient_events",
    )
    op.drop_index(
        op.f("ix_campaign_recipient_events_event_type"),
        table_name="campaign_recipient_events",
    )
    op.drop_table("campaign_recipient_events")
