"""project_trainers + users.is_platform_owner: paza trainerului pe proiect

Plicul 242. Hotărârea lui Andrei (21 nov 2026, 09:41): un trainer vede și schimbă numai
proiectele la care e alocat; proprietarul platformei vede tot.

- project_trainers: ce trainer e alocat la ce proiect. NUMAI id-uri și date (fără nume,
  fără adresă, fără text). Unic pe (proiect, cont).
- users.is_platform_owner: false pentru toți; migrarea NU o pune pe nimeni (se pune la
  urcare, pe un singur cont, cu cuvântul lui Andrei).

Umplerea: fiecare cont cu rolul `trainer` e alocat la FIECARE proiect care există azi
(și cele arhivate sau în ciornă) — azi orice trainer vede orice proiect, deci nimeni nu
pierde nimic. Fără niciun import din `codrut`, fără fișiere citite.

`downgrade`: tabelul, apoi coloana.

Revision ID: 0074_project_trainers
Revises: 0073_practice_daily_replies
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0074_project_trainers"
down_revision = "0073_practice_daily_replies"
branch_labels = None
depends_on = None

UMPLEREA = """
INSERT INTO project_trainers (id, project_id, user_id, created_at, updated_at)
SELECT gen_random_uuid(), p.id, u.id, now(), now()
FROM company_projects p CROSS JOIN users u
WHERE u.role::text = 'trainer'
ON CONFLICT (project_id, user_id) DO NOTHING
"""


def upgrade() -> None:
    op.create_table(
        "project_trainers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_trainers_project_user"),
    )
    op.create_index("ix_project_trainers_project_id", "project_trainers", ["project_id"])
    op.create_index("ix_project_trainers_user_id", "project_trainers", ["user_id"])
    op.add_column(
        "users",
        sa.Column(
            "is_platform_owner", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.execute(sa.text(UMPLEREA))


def downgrade() -> None:
    op.drop_index("ix_project_trainers_user_id", table_name="project_trainers")
    op.drop_index("ix_project_trainers_project_id", table_name="project_trainers")
    op.drop_table("project_trainers")
    op.drop_column("users", "is_platform_owner")
