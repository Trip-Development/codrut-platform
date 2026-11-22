"""practice_daily_reminders: notificarea zilnică a replicii zilei (plicul 252, L3-P2)

Un rând pe telefon (adresa anonimă dată de serviciul de notificări al telefonului), cu omul,
proiectul și ora aleasă (7–21, ora României). Fără nume, email, text, cheile browserului, IP
sau „user agent”. Fără date mutate, fără import din `codrut`.

Revision ID: 0078_daily_reminders
Revises: 0077_reservation_profile
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0078_daily_reminders"
down_revision = "0077_reservation_profile"
branch_labels = None
depends_on = None

TABELA = "practice_daily_reminders"


def upgrade() -> None:
    op.create_table(
        TABELA,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint", sa.String(length=2048), nullable=False),
        sa.Column("ora", sa.SmallInteger(), nullable=False),
        sa.Column("ultima_zi_trimisa", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ora >= 7 AND ora <= 21", name=op.f("ck_practice_daily_reminders_ora_intre_7_si_21")
        ),
        sa.ForeignKeyConstraint(
            ["participant_profile_id"], ["participant_profiles.id"], ondelete="CASCADE",
            name="fk_practice_daily_reminders_profile",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["company_projects.id"], ondelete="CASCADE",
            name="fk_practice_daily_reminders_project",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_practice_daily_reminders"),
        sa.UniqueConstraint("endpoint", name="uq_practice_daily_reminders_endpoint"),
    )
    op.create_index(
        "ix_practice_daily_reminders_participant_profile_id", TABELA,
        ["participant_profile_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_practice_daily_reminders_participant_profile_id", table_name=TABELA)
    op.drop_table(TABELA)
