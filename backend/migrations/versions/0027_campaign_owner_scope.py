"""scope campaigns and contacts to trainer owner

Revision ID: 0027_campaign_owner_scope
Revises: 0026_nullable_campaign_email
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_campaign_owner_scope"
down_revision: str | None = "0026_nullable_campaign_email"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaign_recipients", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column("campaigns", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.create_index("ix_campaign_recipients_owner_id", "campaign_recipients", ["owner_id"])
    op.create_index("ix_campaigns_owner_id", "campaigns", ["owner_id"])
    op.create_foreign_key(
        "fk_campaign_recipients_owner_id_users",
        "campaign_recipients",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_campaigns_owner_id_users",
        "campaigns",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_campaigns_owner_id_users", "campaigns", type_="foreignkey")
    op.drop_constraint(
        "fk_campaign_recipients_owner_id_users",
        "campaign_recipients",
        type_="foreignkey",
    )
    op.drop_index("ix_campaigns_owner_id", table_name="campaigns")
    op.drop_index("ix_campaign_recipients_owner_id", table_name="campaign_recipients")
    op.drop_column("campaigns", "owner_id")
    op.drop_column("campaign_recipients", "owner_id")
