"""practice_turns: costul adevarat al replicii, cu fiecare apel la pretul modelului lui

Plicul 120. Coloana e NULA si fara valoare implicita: randurile de pana acum raman cum sunt, iar
socoteala zilei cade inapoi pe estimarea din unitati pentru ele.

`practice_turns` e un tabel al ramurii noastre (creat de `0060`); pe productie nu exista inca.

Revision ID: 0064_practice_turn_cost
Revises: 0063_practice_turn_parts
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0064_practice_turn_cost"
down_revision: str | None = "0063_practice_turn_parts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("practice_turns", sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("practice_turns", "cost_usd")
