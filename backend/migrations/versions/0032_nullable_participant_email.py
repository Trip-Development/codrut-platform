"""allow roster participants without sendable email

Revision ID: 0032_nullable_participant_email
Revises: 0031_nullable_campaign_segment
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_nullable_participant_email"
down_revision: str | None = "0031_nullable_campaign_segment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "participant_profiles",
        "email",
        existing_type=sa.String(length=320),
        nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    null_email_count = bind.execute(
        sa.text("select count(*) from participant_profiles where email is null")
    ).scalar_one()
    if null_email_count:
        raise RuntimeError(
            "Cannot downgrade participant_profiles.email to NOT NULL while "
            f"{null_email_count} participant rows have no email."
        )

    op.alter_column(
        "participant_profiles",
        "email",
        existing_type=sa.String(length=320),
        nullable=False,
    )
