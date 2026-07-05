"""clear campaign contacts for clean reimport

Revision ID: 0029_clear_campaign_contacts
Revises: 0028_tx_template_catalog
Create Date: 2026-07-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029_clear_campaign_contacts"
down_revision: str | None = "0028_tx_template_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("delete from campaign_recipient_events")
    op.execute("update email_sends set campaign_recipient_id = null")
    op.execute("delete from campaign_recipients")


def downgrade() -> None:
    # Deleted campaign contacts were imported working data. They cannot be
    # reconstructed safely from migration history.
    pass
