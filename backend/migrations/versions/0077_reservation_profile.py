"""practice_budget_reservations.participant_profile_id: al cui e consumul fără ședință (plicul 250)

Revision ID: 0077_reservation_profile
Revises: 0076_practice_turn_eval_state
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0077_reservation_profile"
down_revision = "0076_practice_turn_eval_state"
branch_labels = None
depends_on = None

TABELA = "practice_budget_reservations"
CHEIA = "fk_practice_budget_reservations_participant_profile_id"
INDEXUL = "ix_practice_budget_reservations_participant_profile_id"


def upgrade() -> None:
    # Fără date mutate: toate rândurile existente rămân cu NULL.
    op.add_column(
        TABELA,
        sa.Column("participant_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        CHEIA, TABELA, "participant_profiles", ["participant_profile_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index(INDEXUL, TABELA, ["participant_profile_id"])


def downgrade() -> None:
    op.drop_index(INDEXUL, table_name=TABELA)
    op.drop_constraint(CHEIA, TABELA, type_="foreignkey")
    op.drop_column(TABELA, "participant_profile_id")
