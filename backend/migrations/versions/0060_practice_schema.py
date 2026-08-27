"""create practice module schema

Revision ID: 0060_practice_schema
Revises: 0059_participant_view_audits
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0060_practice_schema"
down_revision: str | None = "0059_participant_view_audits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enums
    knowledge_pack_state = postgresql.ENUM(
        "draft",
        "approved",
        "frozen",
        name="knowledgepackstate",
        create_type=False,
    )
    knowledge_pack_state.create(op.get_bind(), checkfirst=True)

    scenario_state = postgresql.ENUM(
        "draft",
        "piloted",
        "validated",
        name="scenariostate",
        create_type=False,
    )
    scenario_state.create(op.get_bind(), checkfirst=True)

    program_mode = postgresql.ENUM(
        "training",
        "course",
        name="programmode",
        create_type=False,
    )
    program_mode.create(op.get_bind(), checkfirst=True)

    session_kind = postgresql.ENUM(
        "roleplay",
        "coaching",
        "knowledge",
        "research",
        name="sessionkind",
        create_type=False,
    )
    session_kind.create(op.get_bind(), checkfirst=True)

    session_state = postgresql.ENUM(
        "open",
        "closed",
        name="sessionstate",
        create_type=False,
    )
    session_state.create(op.get_bind(), checkfirst=True)

    turn_role = postgresql.ENUM(
        "participant",
        "actor",
        "system",
        name="turnrole",
        create_type=False,
    )
    turn_role.create(op.get_bind(), checkfirst=True)

    outcome_kind = postgresql.ENUM(
        "good",
        "bad",
        "turn_limit",
        "safety_stop",
        name="outcomekind",
        create_type=False,
    )
    outcome_kind.create(op.get_bind(), checkfirst=True)

    creator_note_state = postgresql.ENUM(
        "new",
        "accepted",
        "rejected",
        "applied",
        name="creatornotestate",
        create_type=False,
    )
    creator_note_state.create(op.get_bind(), checkfirst=True)

    budget_reservation_state = postgresql.ENUM(
        "reserved",
        "settled",
        "released",
        name="budgetreservationstate",
        create_type=False,
    )
    budget_reservation_state.create(op.get_bind(), checkfirst=True)

    # 2. Table: practice_themes
    op.create_table(
        "practice_themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=255), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 3. Table: practice_competencies
    op.create_table(
        "practice_competencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_themes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("level_1", sa.Text(), nullable=True),
        sa.Column("level_2", sa.Text(), nullable=True),
        sa.Column("level_3", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("theme_id", "slug", name="uq_practice_competencies_theme_id_slug"),
    )
    op.create_index(
        "ix_practice_competencies_theme_id",
        "practice_competencies",
        ["theme_id"],
    )

    # 4. Table: practice_knowledge_packs
    op.create_table(
        "practice_knowledge_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_themes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", knowledge_pack_state, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("checksum", sa.String(length=255), nullable=False),
        sa.Column(
            "manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("content_uri", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "theme_id", "version", name="uq_practice_knowledge_packs_theme_id_version"
        ),
    )
    op.create_index(
        "ix_practice_knowledge_packs_theme_id",
        "practice_knowledge_packs",
        ["theme_id"],
    )
    op.create_index(
        "ix_practice_knowledge_packs_approved_by_user_id",
        "practice_knowledge_packs",
        ["approved_by_user_id"],
    )

    # 5. Table: practice_scenarios
    op.create_table(
        "practice_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_themes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("state", scenario_state, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("difficulty", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("shared_brief", sa.Text(), nullable=False),
        sa.Column("roles", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("exits", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("debrief_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("max_turns", sa.Integer(), server_default=sa.text("20"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "difficulty >= 1 AND difficulty <= 5", name="ck_practice_scenarios_difficulty"
        ),
        sa.UniqueConstraint(
            "theme_id", "slug", "version", name="uq_practice_scenarios_theme_slug_version"
        ),
    )
    op.create_index(
        "ix_practice_scenarios_theme_id",
        "practice_scenarios",
        ["theme_id"],
    )

    # 6. Table: practice_program_settings
    op.create_table(
        "practice_program_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company_projects.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("mode", program_mode, nullable=False),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_themes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "active_pack_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_knowledge_packs.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "max_turns_per_session", sa.Integer(), server_default=sa.text("20"), nullable=False
        ),
        sa.Column(
            "max_sessions_per_day", sa.Integer(), server_default=sa.text("5"), nullable=False
        ),
        sa.Column(
            "max_chars_per_turn", sa.Integer(), server_default=sa.text("1200"), nullable=False
        ),
        sa.Column(
            "turn_retention_days", sa.Integer(), server_default=sa.text("30"), nullable=False
        ),
        sa.Column(
            "usd_cap_per_participant",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("3.00"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id", name="uq_practice_program_settings_project_id"),
    )
    op.create_index(
        "ix_practice_program_settings_project_id",
        "practice_program_settings",
        ["project_id"],
    )
    op.create_index(
        "ix_practice_program_settings_theme_id",
        "practice_program_settings",
        ["theme_id"],
    )
    op.create_index(
        "ix_practice_program_settings_active_pack_id",
        "practice_program_settings",
        ["active_pack_id"],
    )

    # 7. Table: practice_sessions
    op.create_table(
        "practice_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_settings_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_program_settings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "participant_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participant_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pack_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_knowledge_packs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_scenarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", session_kind, nullable=False),
        sa.Column("state", session_state, server_default=sa.text("'open'"), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("turn_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_practice_sessions_program_settings_id",
        "practice_sessions",
        ["program_settings_id"],
    )
    op.create_index(
        "ix_practice_sessions_participant_profile_id",
        "practice_sessions",
        ["participant_profile_id"],
    )
    op.create_index(
        "ix_practice_sessions_pack_id",
        "practice_sessions",
        ["pack_id"],
    )
    op.create_index(
        "ix_practice_sessions_scenario_id",
        "practice_sessions",
        ["scenario_id"],
    )
    op.create_index(
        "ix_practice_sessions_participant_started",
        "practice_sessions",
        ["participant_profile_id", sa.text("started_at DESC")],
    )

    # 8. Table: practice_turns
    op.create_table(
        "practice_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", turn_role, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("thought_tokens", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("session_id", "ordinal", name="uq_practice_turns_session_id_ordinal"),
    )
    op.create_index(
        "ix_practice_turns_session_id",
        "practice_turns",
        ["session_id"],
    )
    op.create_index(
        "ix_practice_turns_expires_at",
        "practice_turns",
        ["expires_at"],
    )

    # 9. Table: practice_outcomes
    op.create_table(
        "practice_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("kind", outcome_kind, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("session_id", name="uq_practice_outcomes_session_id"),
    )
    op.create_index(
        "ix_practice_outcomes_session_id",
        "practice_outcomes",
        ["session_id"],
    )

    # 10. Table: practice_feedback
    op.create_table(
        "practice_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "competency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_competencies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("criterion", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("quote_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_practice_feedback_session_id",
        "practice_feedback",
        ["session_id"],
    )
    op.create_index(
        "ix_practice_feedback_competency_id",
        "practice_feedback",
        ["competency_id"],
    )
    op.create_index(
        "ix_practice_feedback_expires_at",
        "practice_feedback",
        ["expires_at"],
    )

    # 11. Table: practice_session_samples
    op.create_table(
        "practice_session_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("real_weak", sa.Text(), nullable=True),
        sa.Column("real_improved", sa.Text(), nullable=True),
        sa.Column("invented_weak", sa.Text(), nullable=True),
        sa.Column("invented_improved", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_practice_session_samples_session_id",
        "practice_session_samples",
        ["session_id"],
    )
    op.create_index(
        "ix_practice_session_samples_expires_at",
        "practice_session_samples",
        ["expires_at"],
    )

    # 12. Table: practice_creator_notes
    op.create_table(
        "practice_creator_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "author_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("state", creator_note_state, server_default=sa.text("'new'"), nullable=False),
        sa.Column(
            "applied_pack_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_knowledge_packs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_practice_creator_notes_author_user_id",
        "practice_creator_notes",
        ["author_user_id"],
    )
    op.create_index(
        "ix_practice_creator_notes_session_id",
        "practice_creator_notes",
        ["session_id"],
    )
    op.create_index(
        "ix_practice_creator_notes_applied_pack_id",
        "practice_creator_notes",
        ["applied_pack_id"],
    )

    # 13. Table: practice_budget_reservations
    op.create_table(
        "practice_budget_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_settings_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_program_settings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reserved_usd", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("actual_usd", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column(
            "state", budget_reservation_state, server_default=sa.text("'reserved'"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_practice_budget_reservations_program_settings_id",
        "practice_budget_reservations",
        ["program_settings_id"],
    )
    op.create_index(
        "ix_practice_budget_reservations_session_id",
        "practice_budget_reservations",
        ["session_id"],
    )
    op.create_index(
        "ix_practice_budget_reservations_program_state",
        "practice_budget_reservations",
        ["program_settings_id", "state"],
    )


def downgrade() -> None:
    # 1. Drop tables in reverse dependency order
    op.drop_index(
        "ix_practice_budget_reservations_program_state", table_name="practice_budget_reservations"
    )
    op.drop_index(
        "ix_practice_budget_reservations_session_id", table_name="practice_budget_reservations"
    )
    op.drop_index(
        "ix_practice_budget_reservations_program_settings_id",
        table_name="practice_budget_reservations",
    )
    op.drop_table("practice_budget_reservations")

    op.drop_index("ix_practice_creator_notes_applied_pack_id", table_name="practice_creator_notes")
    op.drop_index("ix_practice_creator_notes_session_id", table_name="practice_creator_notes")
    op.drop_index("ix_practice_creator_notes_author_user_id", table_name="practice_creator_notes")
    op.drop_table("practice_creator_notes")

    op.drop_index("ix_practice_session_samples_expires_at", table_name="practice_session_samples")
    op.drop_index("ix_practice_session_samples_session_id", table_name="practice_session_samples")
    op.drop_table("practice_session_samples")

    op.drop_index("ix_practice_feedback_expires_at", table_name="practice_feedback")
    op.drop_index("ix_practice_feedback_competency_id", table_name="practice_feedback")
    op.drop_index("ix_practice_feedback_session_id", table_name="practice_feedback")
    op.drop_table("practice_feedback")

    op.drop_index("ix_practice_outcomes_session_id", table_name="practice_outcomes")
    op.drop_table("practice_outcomes")

    op.drop_index("ix_practice_turns_expires_at", table_name="practice_turns")
    op.drop_index("ix_practice_turns_session_id", table_name="practice_turns")
    op.drop_table("practice_turns")

    op.drop_index("ix_practice_sessions_participant_started", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_scenario_id", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_pack_id", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_participant_profile_id", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_program_settings_id", table_name="practice_sessions")
    op.drop_table("practice_sessions")

    op.drop_index(
        "ix_practice_program_settings_active_pack_id", table_name="practice_program_settings"
    )
    op.drop_index("ix_practice_program_settings_theme_id", table_name="practice_program_settings")
    op.drop_index("ix_practice_program_settings_project_id", table_name="practice_program_settings")
    op.drop_table("practice_program_settings")

    op.drop_index("ix_practice_scenarios_theme_id", table_name="practice_scenarios")
    op.drop_table("practice_scenarios")

    op.drop_index(
        "ix_practice_knowledge_packs_approved_by_user_id", table_name="practice_knowledge_packs"
    )
    op.drop_index("ix_practice_knowledge_packs_theme_id", table_name="practice_knowledge_packs")
    op.drop_table("practice_knowledge_packs")

    op.drop_index("ix_practice_competencies_theme_id", table_name="practice_competencies")
    op.drop_table("practice_competencies")

    op.drop_table("practice_themes")

    # 2. Drop enums
    budget_reservation_state = postgresql.ENUM(
        "reserved",
        "settled",
        "released",
        name="budgetreservationstate",
        create_type=False,
    )
    budget_reservation_state.drop(op.get_bind(), checkfirst=True)

    creator_note_state = postgresql.ENUM(
        "new",
        "accepted",
        "rejected",
        "applied",
        name="creatornotestate",
        create_type=False,
    )
    creator_note_state.drop(op.get_bind(), checkfirst=True)

    outcome_kind = postgresql.ENUM(
        "good",
        "bad",
        "turn_limit",
        "safety_stop",
        name="outcomekind",
        create_type=False,
    )
    outcome_kind.drop(op.get_bind(), checkfirst=True)

    turn_role = postgresql.ENUM(
        "participant",
        "actor",
        "system",
        name="turnrole",
        create_type=False,
    )
    turn_role.drop(op.get_bind(), checkfirst=True)

    session_state = postgresql.ENUM(
        "open",
        "closed",
        name="sessionstate",
        create_type=False,
    )
    session_state.drop(op.get_bind(), checkfirst=True)

    session_kind = postgresql.ENUM(
        "roleplay",
        "coaching",
        "knowledge",
        "research",
        name="sessionkind",
        create_type=False,
    )
    session_kind.drop(op.get_bind(), checkfirst=True)

    program_mode = postgresql.ENUM(
        "training",
        "course",
        name="programmode",
        create_type=False,
    )
    program_mode.drop(op.get_bind(), checkfirst=True)

    scenario_state = postgresql.ENUM(
        "draft",
        "piloted",
        "validated",
        name="scenariostate",
        create_type=False,
    )
    scenario_state.drop(op.get_bind(), checkfirst=True)

    knowledge_pack_state = postgresql.ENUM(
        "draft",
        "approved",
        "frozen",
        name="knowledgepackstate",
        create_type=False,
    )
    knowledge_pack_state.drop(op.get_bind(), checkfirst=True)
