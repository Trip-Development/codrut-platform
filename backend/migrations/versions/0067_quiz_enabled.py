"""practice_program_settings: butonul „Verificam cat ai retinut", stins la orice proiect

Plicul 128, partea E. Hotararea lui Andrei, 22 septembrie: quizul e activ numai la cursuri, nu
la team coaching, unde nu preda nimic. Implicit STINS — un proiect nou nu are de unde sa stie
daca e curs.

Revision ID: 0067_quiz_enabled
Revises: 0066_practice_turn_cost
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0067_quiz_enabled"
down_revision = "0066_practice_turn_cost"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `server_default="false"` ca randurile care exista deja sa capete valoarea fara sa fie
    # atinse una cate una; apoi se scoate, ca valoarea sa vina din cod de aici incolo.
    op.add_column(
        "practice_program_settings",
        sa.Column("quiz_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("practice_program_settings", "quiz_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("practice_program_settings", "quiz_enabled")
