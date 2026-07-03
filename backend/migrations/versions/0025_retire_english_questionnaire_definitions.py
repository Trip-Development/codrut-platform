"""retire english questionnaire definitions

Revision ID: 0025_retire_en_questionnaires
Revises: 0024_remove_legacy_templates
Create Date: 2026-07-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0025_retire_en_questionnaires"
down_revision: str | None = "0024_remove_legacy_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        update questionnaire_definitions
        set active = false
        where key in ('lencioni_en', 'distress_drivers_en', 'boss_360_en')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        update questionnaire_definitions
        set active = true
        where key in ('lencioni_en', 'distress_drivers_en', 'boss_360_en')
        """
    )
