"""practice_turns.evaluare_stare: nota profesorului care vine în fundal

Plicul 247 (S2). La jocul de rol cu două apeluri, replica personajului pleacă la om imediat;
nota se scrie după, o singură dată, pe aceeași replică.

- practice_turns.evaluare_stare: String(8), gol implicit. NULL = drumul de dinainte (nicio notă
  așteptată în fundal); 'vine' = nota e în lucru; 'gata' = scrisă; 'lipsa' = profesorul a căzut.
  Constrângerea `ck_practice_turns_evaluare_stare` primește numai cele trei valori.
- Nicio scriere în rânduri: rândurile vechi rămân NULL. Fără import din `codrut`.

`downgrade`: constrângerea, apoi coloana.

Revision ID: 0076_practice_turn_eval_state
Revises: 0075_practice_session_objective
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0076_practice_turn_eval_state"
down_revision = "0075_practice_session_objective"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("practice_turns", sa.Column("evaluare_stare", sa.String(8), nullable=True))
    op.create_check_constraint(
        op.f("ck_practice_turns_evaluare_stare"),
        "practice_turns",
        "evaluare_stare IN ('vine','gata','lipsa')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_practice_turns_evaluare_stare"), "practice_turns", type_="check")
    op.drop_column("practice_turns", "evaluare_stare")
