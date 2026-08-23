"""add participant_view_audits table

Revision ID: 0059_participant_view_audits
Revises: 0058_project_invite_templates
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0059_participant_view_audits"
down_revision: str | None = "0058_project_invite_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "participant_view_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trainer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("trainer_email", sa.String(length=320), nullable=False),
        sa.Column(
            "participant_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participant_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("participant_name", sa.String(length=255), nullable=False),
        sa.Column("screen", sa.String(length=64), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_participant_view_audits_company_id",
        "participant_view_audits",
        ["company_id"],
    )
    op.create_index(
        "ix_participant_view_audits_trainer_user_id",
        "participant_view_audits",
        ["trainer_user_id"],
    )
    op.create_index(
        "ix_participant_view_audits_participant_profile_id",
        "participant_view_audits",
        ["participant_profile_id"],
    )
    op.create_index(
        "ix_participant_view_audits_created_at",
        "participant_view_audits",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_participant_view_audits_created_at", table_name="participant_view_audits")
    op.drop_index(
        "ix_participant_view_audits_participant_profile_id", table_name="participant_view_audits"
    )
    op.drop_index(
        "ix_participant_view_audits_trainer_user_id", table_name="participant_view_audits"
    )
    op.drop_index("ix_participant_view_audits_company_id", table_name="participant_view_audits")
    op.drop_table("participant_view_audits")
