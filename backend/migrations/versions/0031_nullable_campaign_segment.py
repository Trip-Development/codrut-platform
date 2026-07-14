"""allow campaigns without a preselected recipient group

Revision ID: 0031_nullable_campaign_segment
Revises: 0030_campaign_memberships
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_nullable_campaign_segment"
down_revision: str | None = "0030_campaign_memberships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


campaign_recipient_segment = postgresql.ENUM(
    "past_customer",
    "potential_customer",
    name="campaignrecipientsegment",
    create_type=False,
)


def upgrade() -> None:
    op.alter_column(
        "campaigns",
        "segment",
        existing_type=campaign_recipient_segment,
        nullable=True,
    )


def downgrade() -> None:
    op.execute("update campaigns set segment = 'potential_customer' where segment is null")
    op.alter_column(
        "campaigns",
        "segment",
        existing_type=campaign_recipient_segment,
        nullable=False,
    )
