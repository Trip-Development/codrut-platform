"""convert_questionnaire_key_to_string

Revision ID: c21e483de579
Revises: 7f6d8f0c9b21
Create Date: 2026-06-08 16:56:17.554708
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c21e483de579'
down_revision: str | None = '7f6d8f0c9b21'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "questionnaire_definitions",
        "key",
        type_=sa.String(length=50),
        postgresql_using="key::varchar"
    )
    op.alter_column(
        "questionnaire_responses",
        "questionnaire_key",
        type_=sa.String(length=50),
        postgresql_using="questionnaire_key::varchar"
    )


def downgrade() -> None:
    op.alter_column(
        "questionnaire_definitions",
        "key",
        type_=sa.Enum(
            "pcm_base",
            "phase",
            "lencioni",
            "distress_drivers",
            "boss_360",
            "icare",
            name="questionnairekey",
        ),
        postgresql_using="key::questionnairekey"
    )
    op.alter_column(
        "questionnaire_responses",
        "questionnaire_key",
        type_=sa.Enum(
            "pcm_base",
            "phase",
            "lencioni",
            "distress_drivers",
            "boss_360",
            "icare",
            name="questionnairekey",
        ),
        postgresql_using="questionnaire_key::questionnairekey"
    )
