"""add questionnaire_response_archives table and assignment reopen counter

Revision ID: 0061_response_reopen_archive
Revises: 0060_show_participant_results
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0061_response_reopen_archive"
down_revision: str | None = "0060_show_participant_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "questionnaire_response_archives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questionnaire_assignments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "respondent_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participant_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assessment_cycle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("questionnaire_key", sa.String(length=120), nullable=False),
        sa.Column("questionnaire_version", sa.Integer(), nullable=False),
        sa.Column("response_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_status", sa.String(length=32), nullable=False),
        sa.Column("response_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("primary_result", sa.String(length=255), nullable=True),
        sa.Column(
            "reopened_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reopened_by_email", sa.String(length=320), nullable=False),
        sa.Column("reopen_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "reopened_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reopen_sequence > 0",
            name="reopen_sequence_positive",
        ),
        sa.UniqueConstraint(
            "assignment_id",
            "reopen_sequence",
            name="uq_questionnaire_response_archives_assignment_sequence",
        ),
    )
    # Index NEunic pe assignment_id, intentionat: arhiva este istorie, deci
    # aceeasi asignare are mai multe randuri, cate unul pentru fiecare
    # redeschidere. Unicitatea sta pe perechea (assignment_id, reopen_sequence).
    op.create_index(
        "ix_questionnaire_response_archives_assignment_id",
        "questionnaire_response_archives",
        ["assignment_id"],
    )
    op.create_index(
        "ix_questionnaire_response_archives_company_id",
        "questionnaire_response_archives",
        ["company_id"],
    )
    op.create_index(
        "ix_questionnaire_response_archives_respondent_profile_id",
        "questionnaire_response_archives",
        ["respondent_profile_id"],
    )
    op.create_index(
        "ix_questionnaire_response_archives_reopened_by_user_id",
        "questionnaire_response_archives",
        ["reopened_by_user_id"],
    )
    op.create_index(
        "ix_questionnaire_response_archives_reopened_at",
        "questionnaire_response_archives",
        ["reopened_at"],
    )

    op.add_column(
        "questionnaire_assignments",
        sa.Column(
            "reopen_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "reopen_count_non_negative",
        "questionnaire_assignments",
        "reopen_count >= 0",
    )


def downgrade() -> None:
    # Numele scurt, nu cel complet: alembic aplica conventia de denumire a
    # repoului ("ck_%(table_name)s_%(constraint_name)s") si la stergere, nu doar
    # la creare. Numele complet ar fi prefixat a doua oara si trunchiat cu hash.
    op.drop_constraint(
        "reopen_count_non_negative",
        "questionnaire_assignments",
        type_="check",
    )
    op.drop_column("questionnaire_assignments", "reopen_count")

    op.drop_index(
        "ix_questionnaire_response_archives_reopened_at",
        table_name="questionnaire_response_archives",
    )
    op.drop_index(
        "ix_questionnaire_response_archives_reopened_by_user_id",
        table_name="questionnaire_response_archives",
    )
    op.drop_index(
        "ix_questionnaire_response_archives_respondent_profile_id",
        table_name="questionnaire_response_archives",
    )
    op.drop_index(
        "ix_questionnaire_response_archives_company_id",
        table_name="questionnaire_response_archives",
    )
    op.drop_index(
        "ix_questionnaire_response_archives_assignment_id",
        table_name="questionnaire_response_archives",
    )
    op.drop_table("questionnaire_response_archives")
