"""remove legacy placeholder email templates

Revision ID: 0024_remove_legacy_templates
Revises: 0023_campaign_send_tracking
Create Date: 2026-07-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0024_remove_legacy_templates"
down_revision: str | None = "0023_campaign_send_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("delete from email_templates where key like 'template\\_%' escape '\\'")


def downgrade() -> None:
    # Legacy placeholder templates were trainer-created scratch data. They are
    # intentionally not recreated on downgrade.
    pass
