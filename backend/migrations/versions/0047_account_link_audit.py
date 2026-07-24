"""audit participant account-link repairs

Revision ID: 0047_account_link_audit
Revises: 0046_assessment_cycle_integrity
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047_account_link_audit"
down_revision: str | None = "0046_assessment_cycle_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "participant_account_link_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("previous_user_id", sa.Uuid(), nullable=True),
        sa.Column("previous_user_email", sa.String(length=320), nullable=True),
        sa.Column("new_user_id", sa.Uuid(), nullable=True),
        sa.Column("new_user_email", sa.String(length=320), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action in ('link_matching_email', 'unlink')",
            name=op.f("ck_participant_account_link_audits_participant_account_link_audit_action"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_profile_id"],
            ["participant_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_participant_account_link_audits")),
    )
    for column_name in ("company_id", "participant_profile_id", "actor_user_id"):
        op.create_index(
            op.f(f"ix_participant_account_link_audits_{column_name}"),
            "participant_account_link_audits",
            [column_name],
        )


def downgrade() -> None:
    op.drop_table("participant_account_link_audits")
