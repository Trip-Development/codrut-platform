"""group assignments into immutable rounds

Revision ID: 0041_assignment_rounds
Revises: 0040_project_scoped_invites
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041_assignment_rounds"
down_revision: str | None = "0040_project_scoped_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "questionnaire_assignments",
        sa.Column(
            "assignment_round_id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    # PostgreSQL evaluates this volatile default for each legacy row. Isolating
    # unknown historical lineage prevents unrelated feedback from being aggregated.
    # New application writes explicitly share one UUID for a generated plan, while
    # the default keeps inserts from the previous application version compatible.
    op.create_index(
        op.f("ix_questionnaire_assignments_assignment_round_id"),
        "questionnaire_assignments",
        ["assignment_round_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_questionnaire_assignments_assignment_round_id"),
        table_name="questionnaire_assignments",
    )
    op.drop_column("questionnaire_assignments", "assignment_round_id")
