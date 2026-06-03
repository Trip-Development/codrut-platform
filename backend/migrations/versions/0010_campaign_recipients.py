"""create campaign recipients

Revision ID: 0010_campaign_recipients
Revises: 0009_email_delivery_state
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_campaign_recipients"
down_revision: str | None = "0009_email_delivery_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


campaign_recipient_segment = postgresql.ENUM(
    "past_customer",
    "potential_customer",
    name="campaignrecipientsegment",
    create_type=False,
)
campaign_recipient_status = postgresql.ENUM(
    "active",
    "suppressed",
    "unsubscribed",
    name="campaignrecipientstatus",
    create_type=False,
)


def upgrade() -> None:
    campaign_recipient_segment.create(op.get_bind(), checkfirst=True)
    campaign_recipient_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "campaign_recipients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("organization_name", sa.String(length=255), nullable=True),
        sa.Column("segment", campaign_recipient_segment, nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("status", campaign_recipient_status, nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_recipients")),
        sa.UniqueConstraint("email", name=op.f("uq_campaign_recipients_email")),
    )
    op.create_index(op.f("ix_campaign_recipients_email"), "campaign_recipients", ["email"])


def downgrade() -> None:
    op.drop_index(op.f("ix_campaign_recipients_email"), table_name="campaign_recipients")
    op.drop_table("campaign_recipients")
    campaign_recipient_status.drop(op.get_bind(), checkfirst=True)
    campaign_recipient_segment.drop(op.get_bind(), checkfirst=True)
