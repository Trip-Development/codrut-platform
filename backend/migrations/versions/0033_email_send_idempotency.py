"""add idempotency keys to email sends

Revision ID: 0033_email_send_idempotency
Revises: 0032_nullable_participant_email
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_email_send_idempotency"
down_revision: str | None = "0032_nullable_participant_email"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "email_sends",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_email_sends_idempotency_key",
        "email_sends",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_email_sends_idempotency_key", table_name="email_sends")
    op.drop_column("email_sends", "idempotency_key")
