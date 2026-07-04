"""allow inactive campaign recipients without email

Revision ID: 0026_nullable_campaign_email
Revises: 0025_retire_en_questionnaires
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_nullable_campaign_email"
down_revision: str | None = "0025_retire_en_questionnaires"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "campaign_recipients",
        "email",
        existing_type=sa.String(length=320),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "campaign_recipients",
        "email",
        existing_type=sa.String(length=320),
        nullable=False,
    )
