"""store questionnaire keys as strings

Revision ID: 0012_questionnaire_key_strings
Revises: 7f6d8f0c9b21
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_questionnaire_key_strings"
down_revision: str | None = "7f6d8f0c9b21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "questionnaire_definitions",
        "key",
        existing_type=sa.Enum(name="questionnairekey"),
        type_=sa.String(length=120),
        existing_nullable=False,
        postgresql_using="key::text",
    )
    op.alter_column(
        "questionnaire_responses",
        "questionnaire_key",
        existing_type=sa.Enum(name="questionnairekey"),
        type_=sa.String(length=120),
        existing_nullable=False,
        postgresql_using="questionnaire_key::text",
    )
    op.execute("DROP TYPE IF EXISTS questionnairekey")


def downgrade() -> None:
    questionnaire_key = sa.Enum(
        "pcm_base",
        "phase",
        "lencioni",
        "distress_drivers",
        "boss_360",
        "icare",
        name="questionnairekey",
    )
    questionnaire_key.create(op.get_bind(), checkfirst=True)

    op.execute(
        """
        ALTER TABLE questionnaire_definitions
        ALTER COLUMN key TYPE questionnairekey
        USING key::questionnairekey
        """
    )
    op.execute(
        """
        ALTER TABLE questionnaire_responses
        ALTER COLUMN questionnaire_key TYPE questionnairekey
        USING questionnaire_key::questionnairekey
        """
    )
