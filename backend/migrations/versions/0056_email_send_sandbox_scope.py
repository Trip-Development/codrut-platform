"""scope Brevo sandbox delivery to individual outbox messages

Revision ID: 0056_email_send_sandbox_scope
Revises: 0055_participant_aliases
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0056_email_send_sandbox_scope"
down_revision: str | None = "0055_participant_aliases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "email_sends",
        sa.Column(
            "sandbox_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("email_sends", "sandbox_required")
