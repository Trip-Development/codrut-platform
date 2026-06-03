"""create campaign templates

Revision ID: 0011_campaign_templates
Revises: 0010_campaign_recipients
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_campaign_templates"
down_revision: str | None = "0010_campaign_recipients"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


campaign_recipient_segment = postgresql.ENUM(
    "past_customer",
    "potential_customer",
    name="campaignrecipientsegment",
    create_type=False,
)
campaign_status = postgresql.ENUM(
    "draft",
    "ready",
    "paused",
    "completed",
    name="campaignstatus",
    create_type=False,
)


def upgrade() -> None:
    campaign_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("segment", campaign_recipient_segment, nullable=False),
        sa.Column("status", campaign_status, nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("html_body", sa.String(), nullable=False),
        sa.Column("text_body", sa.String(), nullable=False),
        sa.Column("video_url", sa.String(length=2048), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
        sa.Column("landing_page_url", sa.String(length=2048), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns")),
        sa.UniqueConstraint("name", name=op.f("uq_campaigns_name")),
    )


def downgrade() -> None:
    op.drop_table("campaigns")
    campaign_status.drop(op.get_bind(), checkfirst=True)
