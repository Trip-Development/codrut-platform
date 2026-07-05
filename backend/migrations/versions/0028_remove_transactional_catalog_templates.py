"""remove transactional templates from editable catalog

Revision ID: 0028_tx_template_catalog
Revises: 0027_campaign_owner_scope
Create Date: 2026-07-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0028_tx_template_catalog"
down_revision: str | None = "0027_campaign_owner_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        delete from email_templates
        where owner_id is null
          and key in ('account_setup', 'assignment_bundle')
        """
    )


def downgrade() -> None:
    # Transactional templates are code-owned fallbacks. They are intentionally
    # not recreated as editable DB rows on downgrade.
    pass
