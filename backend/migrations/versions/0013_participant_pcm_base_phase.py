"""add structured participant PCM fields

Revision ID: 0013_participant_pcm_base_phase
Revises: 0012_questionnaire_key_strings
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_participant_pcm_base_phase"
down_revision: str | None = "0012_questionnaire_key_strings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "assignment_invites",
        "token",
        existing_type=sa.String(length=512),
        type_=sa.String(length=2048),
        existing_nullable=False,
    )
    op.add_column(
        "participant_profiles",
        sa.Column("pcm_base", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "participant_profiles",
        sa.Column("pcm_phase", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("participant_profiles", "pcm_phase")
    op.drop_column("participant_profiles", "pcm_base")
    op.alter_column(
        "assignment_invites",
        "token",
        existing_type=sa.String(length=2048),
        type_=sa.String(length=512),
        existing_nullable=False,
    )
