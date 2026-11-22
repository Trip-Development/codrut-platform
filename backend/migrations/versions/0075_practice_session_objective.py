"""practice_sessions.objective_id: sesiunea pornită „pe obiectiv”

Plicul 244 (L1-P3). Când omul apasă „Exersează pe obiectiv”, sesiunea se leagă de obiectivul lui
curent și rămâne pe el, chiar dacă omul își schimbă alegerea în timpul conversației.

- practice_sessions.objective_id: uuid, gol implicit, spre practice_objectives (RESTRICT), cu
  index. Fără date: toate sesiunile de azi rămân cu objective_id gol.
- Fără niciun import din `codrut`, fără fișiere citite.

`downgrade`: indexul, apoi coloana.

Revision ID: 0075_practice_session_objective
Revises: 0074_project_trainers
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0075_practice_session_objective"
down_revision = "0074_project_trainers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "practice_sessions",
        sa.Column(
            "objective_id",
            sa.Uuid(),
            sa.ForeignKey(
                "practice_objectives.id",
                ondelete="RESTRICT",
                name="fk_practice_sessions_objective_id_practice_objectives",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_practice_sessions_objective_id", "practice_sessions", ["objective_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_practice_sessions_objective_id", table_name="practice_sessions")
    op.drop_column("practice_sessions", "objective_id")
