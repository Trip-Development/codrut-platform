"""practice: cele trei indexuri pe care modelele le cereau si nicio migrare nu le facea

Plicul 133, punctul 1. `alembic check` pica pe ramura practicii (si inainte de rebazare; pe `dev`
trecea): modelele declarau cu `index=True` trei coloane pentru care nu exista niciun index in baza.
Numai indexuri simple, fara nicio schimbare de purtare si fara nicio atingere a datelor.

Celelalte doua ceruri ale lui `alembic check` (indexuri UNICE pe `practice_outcomes.session_id` si
`practice_program_settings.project_id`) NU sunt aici: unicitatea o apara deja constrangerile din
`0062_practice_schema`, iar modelul le declara de doua ori. S-a scos dublura din model.

Revision ID: 0068_practice_missing_indexes
Revises: 0067_quiz_enabled
"""

from __future__ import annotations

from alembic import op

revision = "0068_practice_missing_indexes"
down_revision = "0067_quiz_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_insight_moments_competency_id", "insight_moments", ["competency_id"], unique=False
    )
    op.create_index(
        "ix_session_samples_competency_id", "session_samples", ["competency_id"], unique=False
    )
    op.create_index(
        "ix_trainer_notes_project_id", "trainer_notes", ["project_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_trainer_notes_project_id", table_name="trainer_notes")
    op.drop_index("ix_session_samples_competency_id", table_name="session_samples")
    op.drop_index("ix_insight_moments_competency_id", table_name="insight_moments")
