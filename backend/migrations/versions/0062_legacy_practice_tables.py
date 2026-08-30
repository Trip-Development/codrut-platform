"""add legacy practice tables and xp/streak columns

Revision ID: 0062_legacy_practice_tables
Revises: 0061_practice_prompt_version
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0062_legacy_practice_tables"
down_revision: str | None = "0061_practice_prompt_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add cached_tokens to practice_turns
    op.add_column(
        "practice_turns",
        sa.Column("cached_tokens", sa.Integer(), nullable=True, server_default="0"),
    )

    # 2. Add xp and streak to users and participant_profiles
    op.add_column(
        "users",
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("streak", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "participant_profiles",
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "participant_profiles",
        sa.Column("streak", sa.Integer(), nullable=False, server_default="0"),
    )

    # 3. Create competencies_template
    op.create_table(
        "competencies_template",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("theme_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["theme_id"], ["practice_themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competencies_template_theme_id", "competencies_template", ["theme_id"])

    # 4. Create project_competencies
    op.create_table(
        "project_competencies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_competencies_project_id", "project_competencies", ["project_id"])

    # 5. Create competency_scores
    op.create_table(
        "competency_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("competency_id", sa.UUID(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("competency_name", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="session"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_competency_scores_score"),
        sa.CheckConstraint("level >= 1 AND level <= 3", name="ck_competency_scores_level"),
        sa.ForeignKeyConstraint(["competency_id"], ["practice_competencies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competency_scores_user_id", "competency_scores", ["user_id"])
    op.create_index("ix_competency_scores_project_id", "competency_scores", ["project_id"])
    op.create_index("ix_competency_scores_competency_id", "competency_scores", ["competency_id"])

    # 6. Create insight_moments
    op.create_table(
        "insight_moments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("competency_id", sa.UUID(), nullable=True),
        sa.Column("competency_name", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["competency_id"], ["practice_competencies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insight_moments_user_id", "insight_moments", ["user_id"])

    # 7. Create session_samples
    op.create_table(
        "session_samples",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("competency_id", sa.UUID(), nullable=True),
        sa.Column("real_weak", sa.Text(), nullable=True),
        sa.Column("real_improved", sa.Text(), nullable=True),
        sa.Column("invented_weak", sa.Text(), nullable=True),
        sa.Column("invented_improved", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["competency_id"], ["practice_competencies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_samples_user_id", "session_samples", ["user_id"])

    # 8. Create participant_memory
    op.create_table(
        "participant_memory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_quotes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("evolution_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("personal_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("relevant_competencies", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("relevance_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("relevance_score >= 0 AND relevance_score <= 100", name="ck_participant_memory_relevance_score"),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_participant_memory_user_id", "participant_memory", ["user_id"])
    op.create_index("ix_participant_memory_project_id", "participant_memory", ["project_id"])

    # 9. Create evolution_logs
    op.create_table(
        "evolution_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("qualitative_analysis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evolution_logs_user_id", "evolution_logs", ["user_id"])

    # 10. Create trainer_notes
    op.create_table(
        "trainer_notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("trainer_id", sa.UUID(), nullable=False),
        sa.Column("participant_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["participant_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trainer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trainer_notes_trainer_id", "trainer_notes", ["trainer_id"])
    op.create_index("ix_trainer_notes_participant_id", "trainer_notes", ["participant_id"])


def downgrade() -> None:
    op.drop_table("trainer_notes")
    op.drop_table("evolution_logs")
    op.drop_table("participant_memory")
    op.drop_table("session_samples")
    op.drop_table("insight_moments")
    op.drop_table("competency_scores")
    op.drop_table("project_competencies")
    op.drop_table("competencies_template")
    op.drop_column("participant_profiles", "streak")
    op.drop_column("participant_profiles", "xp")
    op.drop_column("users", "streak")
    op.drop_column("users", "xp")
    op.drop_column("practice_turns", "cached_tokens")
