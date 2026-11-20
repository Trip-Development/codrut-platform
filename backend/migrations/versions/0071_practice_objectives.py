"""practice_objectives: obiectivele de aplicare si alegerea omului

Plicul 230 (Cody 2.0, linia 1, L1-P1). Doua tabele si o coloana goala:
- practice_objectives: lista de obiective a unui training (`catalog`), intai cele 12 de
  comunicare asertiva, aprobate de Andrei (17-18 nov 2026);
- practice_objective_choices: ce obiectiv si-a ales fiecare om, pe proiect, cu istoric la
  schimbare (`replaced_at` gol = alegerea curenta);
- practice_program_settings.objective_catalog: ce lista foloseste proiectul (gol = niciuna;
  toate proiectele de azi raman exact cum sunt).

Cele 12 se incarca AICI, prin functia comuna din `codrut.modules.practice.obiective` (scrie cu
`sa.table`, nu cu modelele), ca la urcarea pe live sa nu ramana niciun pas de mana.

Revision ID: 0071_practice_objectives
Revises: 0070_practice_consent
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from codrut.modules.practice.obiective import (
    CATALOG_COMUNICARE_ASERTIVA,
    citeste_catalog,
    incarca_catalog,
)

revision = "0071_practice_objectives"
down_revision = "0070_practice_consent"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.add_column(
        "practice_program_settings",
        sa.Column("objective_catalog", sa.String(length=100), nullable=True),
    )
    op.create_table(
        "practice_objectives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog", sa.String(length=100), nullable=False),
        sa.Column("catalog_name", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("success_sign", sa.Text(), nullable=False),
        sa.Column("competencies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog", "order_index", name="uq_practice_objectives_catalog_order"
        ),
    )
    op.create_index("ix_practice_objectives_catalog", "practice_objectives", ["catalog"])
    op.create_table(
        "practice_objective_choices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("objective_id", sa.Uuid(), nullable=False),
        sa.Column("chosen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["participant_profile_id"], ["participant_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["objective_id"], ["practice_objectives.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_practice_objective_choices_participant_profile_id", "practice_objective_choices",
        ["participant_profile_id"],
    )
    op.create_index(
        "ix_practice_objective_choices_project_id", "practice_objective_choices", ["project_id"]
    )
    op.create_index(
        "ix_practice_objective_choices_objective_id", "practice_objective_choices",
        ["objective_id"],
    )
    # o singura alegere curenta pe om si proiect
    op.create_index(
        "uq_practice_objective_choices_current", "practice_objective_choices",
        ["participant_profile_id", "project_id"], unique=True,
        postgresql_where=sa.text("replaced_at IS NULL"),
    )
    incarca_catalog(op.get_bind(), citeste_catalog(CATALOG_COMUNICARE_ASERTIVA))


def downgrade() -> None:
    # intai alegerile, apoi obiectivele, apoi coloana
    op.drop_index(
        "uq_practice_objective_choices_current", table_name="practice_objective_choices"
    )
    op.drop_index(
        "ix_practice_objective_choices_objective_id", table_name="practice_objective_choices"
    )
    op.drop_index(
        "ix_practice_objective_choices_project_id", table_name="practice_objective_choices"
    )
    op.drop_index(
        "ix_practice_objective_choices_participant_profile_id",
        table_name="practice_objective_choices",
    )
    op.drop_table("practice_objective_choices")
    op.drop_index("ix_practice_objectives_catalog", table_name="practice_objectives")
    op.drop_table("practice_objectives")
    op.drop_column("practice_program_settings", "objective_catalog")
