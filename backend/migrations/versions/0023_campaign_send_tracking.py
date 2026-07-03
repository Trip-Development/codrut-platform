"""track campaign sends on email_sends

Revision ID: 0023_campaign_send_tracking
Revises: 0022_campaign_recipient_events
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_campaign_send_tracking"
down_revision: str | None = "0022_campaign_recipient_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("email_sends", sa.Column("campaign_id", sa.Uuid(), nullable=True))
    op.add_column("email_sends", sa.Column("campaign_recipient_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_email_sends_campaign_id"),
        "email_sends",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_sends_campaign_recipient_id"),
        "email_sends",
        ["campaign_recipient_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_email_sends_campaign_id_campaigns"),
        "email_sends",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_email_sends_campaign_recipient_id_campaign_recipients"),
        "email_sends",
        "campaign_recipients",
        ["campaign_recipient_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_email_sends_campaign_recipient_id_campaign_recipients"),
        "email_sends",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_email_sends_campaign_id_campaigns"),
        "email_sends",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_email_sends_campaign_recipient_id"), table_name="email_sends")
    op.drop_index(op.f("ix_email_sends_campaign_id"), table_name="email_sends")
    op.drop_column("email_sends", "campaign_recipient_id")
    op.drop_column("email_sends", "campaign_id")
