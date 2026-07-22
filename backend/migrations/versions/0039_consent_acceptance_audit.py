"""add immutable consent acceptance audit records

Revision ID: 0039_consent_acceptance_audit
Revises: 0038_durable_email_outbox
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_consent_acceptance_audit"
down_revision: str | None = "0038_durable_email_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consent_acceptances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("assignment_invite_id", sa.Uuid(), nullable=True),
        sa.Column("respondent_profile_id", sa.Uuid(), nullable=True),
        sa.Column("terms_version", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source in ('authenticated', 'secure_invite', 'local_preview')",
            name=op.f("ck_consent_acceptances_consent_acceptance_source"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_consent_acceptances_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_acceptances")),
        sa.UniqueConstraint(
            "user_id",
            "session_id",
            "terms_version",
            name="uq_consent_acceptances_user_session_version",
        ),
    )
    op.create_index(
        op.f("ix_consent_acceptances_user_id"),
        "consent_acceptances",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consent_acceptances_session_id"),
        "consent_acceptances",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consent_acceptances_assignment_invite_id"),
        "consent_acceptances",
        ["assignment_invite_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consent_acceptances_respondent_profile_id"),
        "consent_acceptances",
        ["respondent_profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_consent_acceptances_respondent_profile_id"),
        table_name="consent_acceptances",
    )
    op.drop_index(
        op.f("ix_consent_acceptances_assignment_invite_id"),
        table_name="consent_acceptances",
    )
    op.drop_index(
        op.f("ix_consent_acceptances_session_id"),
        table_name="consent_acceptances",
    )
    op.drop_index(
        op.f("ix_consent_acceptances_user_id"),
        table_name="consent_acceptances",
    )
    op.drop_table("consent_acceptances")
