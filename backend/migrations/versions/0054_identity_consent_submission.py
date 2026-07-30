"""make consent user-version authoritative and queue submission processing

Revision ID: 0054_identity_consent_submission
Revises: 0053_contact_privacy_bridge
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0054_identity_consent_submission"
down_revision: str | None = "0053_contact_privacy_bridge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

submission_processing_status = sa.Enum(
    "queued",
    "processing",
    "completed",
    "failed",
    name="submissionprocessingstatus",
)


def upgrade() -> None:
    op.create_table(
        "submission_processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            submission_processing_status,
            server_default="queued",
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=120), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
            "attempt_count >= 0 and max_attempts > 0 and attempt_count <= max_attempts",
            name=op.f(
                "ck_submission_processing_jobs_submission_processing_attempt_bounds"
            ),
        ),
        sa.CheckConstraint(
            "status <> 'queued' or next_attempt_at is not null",
            name=op.f(
                "ck_submission_processing_jobs_submission_processing_next_attempt_present"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["questionnaire_assignments.id"],
            name=op.f(
                "fk_submission_processing_jobs_assignment_id_questionnaire_assignments"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_submission_processing_jobs"),
        ),
        sa.UniqueConstraint(
            "assignment_id",
            name="uq_submission_processing_jobs_assignment_id",
        ),
    )
    op.create_index(
        op.f("ix_submission_processing_jobs_assignment_id"),
        "submission_processing_jobs",
        ["assignment_id"],
        unique=False,
    )
    op.create_index(
        "ix_submission_processing_jobs_due",
        "submission_processing_jobs",
        ["status", "next_attempt_at", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_submission_processing_jobs_due",
        table_name="submission_processing_jobs",
    )
    op.drop_index(
        op.f("ix_submission_processing_jobs_assignment_id"),
        table_name="submission_processing_jobs",
    )
    op.drop_table("submission_processing_jobs")
    submission_processing_status.drop(op.get_bind(), checkfirst=True)
