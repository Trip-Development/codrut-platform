"""create questionnaire responses

Revision ID: 0008_questionnaire_responses
Revises: 0007_questionnaire_defs
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_questionnaire_responses"
down_revision: str | None = "0007_questionnaire_defs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


response_status = postgresql.ENUM(
    "draft",
    "submitted",
    name="questionnaireresponsestatus",
    create_type=False,
)
questionnaire_key = postgresql.ENUM(
    "pcm_base",
    "phase",
    "lencioni",
    "distress_drivers",
    "boss_360",
    name="questionnairekey",
    create_type=False,
)


def upgrade() -> None:
    response_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "questionnaire_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_key", questionnaire_key, nullable=False),
        sa.Column("questionnaire_version", sa.Integer(), nullable=False),
        sa.Column("status", response_status, nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["questionnaire_assignments.id"],
            name=op.f("fk_questionnaire_responses_assignment_id_questionnaire_assignments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questionnaire_responses")),
        sa.UniqueConstraint(
            "assignment_id",
            name=op.f("uq_questionnaire_responses_assignment_id"),
        ),
    )
    op.create_index(
        op.f("ix_questionnaire_responses_assignment_id"),
        "questionnaire_responses",
        ["assignment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_questionnaire_responses_assignment_id"),
        table_name="questionnaire_responses",
    )
    op.drop_table("questionnaire_responses")
    response_status.drop(op.get_bind(), checkfirst=True)
