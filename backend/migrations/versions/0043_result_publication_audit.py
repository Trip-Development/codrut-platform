"""add auditable participant result publications

Revision ID: 0043_result_publication_audit
Revises: 0042_delivery_events_reminders
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043_result_publication_audit"
down_revision: str | None = "0042_delivery_events_reminders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    publication_kind = postgresql.ENUM(
        "individual",
        "aggregate_360",
        name="resultpublicationkind",
        create_type=False,
    )
    publication_kind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "result_publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_key", sa.String(length=255), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("assignment_round_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_definition_id", sa.Uuid(), nullable=True),
        sa.Column("questionnaire_key", sa.String(length=120), nullable=False),
        sa.Column("source_assignment_id", sa.Uuid(), nullable=True),
        sa.Column("kind", publication_kind, nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("definition_checksum", sa.String(length=64), nullable=True),
        sa.Column("policy_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_count > 0",
            name=op.f("ck_result_publications_source_count_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_result_publications_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_profile_id"],
            ["participant_profiles.id"],
            name=op.f("fk_result_publications_participant_profile_id_participant_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["company_projects.id"],
            name=op.f("fk_result_publications_project_id_company_projects"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["questionnaire_definition_id"],
            ["questionnaire_definitions.id"],
            name=op.f(
                "fk_result_publications_questionnaire_definition_id_questionnaire_definitions"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_assignment_id"],
            ["questionnaire_assignments.id"],
            name=op.f("fk_result_publications_source_assignment_id_questionnaire_assignments"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_result_publications")),
        sa.UniqueConstraint(
            "publication_key",
            name="uq_result_publications_publication_key",
        ),
    )
    for column_name in (
        "assignment_round_id",
        "company_id",
        "participant_profile_id",
        "project_id",
        "questionnaire_definition_id",
        "source_assignment_id",
    ):
        op.create_index(
            op.f(f"ix_result_publications_{column_name}"),
            "result_publications",
            [column_name],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("result_publications")
    postgresql.ENUM(name="resultpublicationkind").drop(op.get_bind(), checkfirst=True)
