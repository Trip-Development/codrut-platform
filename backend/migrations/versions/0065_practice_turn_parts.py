"""practice_turns: cele doua bucati ale replicii, la despartirea actor/evaluator

Plicul 117. Coloanele sunt NULE si fara valoare implicita: rândurile de pana acum raman exact
cum sunt, iar drumul cu un singur apel nu le foloseste deloc.

`practice_turns` e un tabel al ramurii noastre, creat de `0060`; pe productie nu exista inca,
deci migrarea asta nu atinge nicio data vie.

Revision ID: 0065_practice_turn_parts
Revises: 0064_legacy_practice_tables
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065_practice_turn_parts"
down_revision: str | None = "0064_legacy_practice_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("practice_turns", sa.Column("text_actor", sa.Text(), nullable=True))
    op.add_column("practice_turns", sa.Column("text_evaluator", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("practice_turns", "text_evaluator")
    op.drop_column("practice_turns", "text_actor")
