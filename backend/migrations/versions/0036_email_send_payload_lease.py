"""add email send payload fingerprints and leases

Revision ID: 0036_email_send_payload_lease
Revises: 0035_contact_owner_isolation
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_email_send_payload_lease"
down_revision: str | None = "0035_contact_owner_isolation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "email_sends",
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "email_sends",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        update email_sends
        set lease_expires_at = updated_at + interval '5 minutes'
        where status = 'queued'
          and idempotency_key is not null
          and lease_expires_at is null
        """
    )


def downgrade() -> None:
    op.drop_column("email_sends", "lease_expires_at")
    op.drop_column("email_sends", "payload_fingerprint")
