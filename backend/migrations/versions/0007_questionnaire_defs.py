"""create questionnaire definitions

Revision ID: 0007_questionnaire_defs
Revises: 0006_assignment_tracking
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_questionnaire_defs"
down_revision: str | None = "0006_assignment_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    questionnaire_key.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "questionnaire_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", questionnaire_key, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("schema", postgresql.JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questionnaire_definitions")),
        sa.UniqueConstraint(
            "key",
            "version",
            name=op.f("uq_questionnaire_definitions_key_version"),
        ),
    )


def downgrade() -> None:
    op.drop_table("questionnaire_definitions")
    questionnaire_key.drop(op.get_bind(), checkfirst=True)
