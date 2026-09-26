from sqlalchemy.orm import configure_mappers

from codrut.core.database import Base
from codrut.modules.practice.models import (
    BudgetReservationState,
    CreatorNoteState,
    KnowledgePackState,
    OutcomeKind,
    PracticeBudgetReservation,
    PracticeCompetency,
    PracticeCreatorNote,
    PracticeFeedback,
    PracticeKnowledgePack,
    PracticeOutcome,
    PracticeProgramSettings,
    PracticeScenario,
    PracticeSession,
    PracticeSessionSample,
    PracticeTheme,
    PracticeTurn,
    ProgramMode,
    ScenarioState,
    SessionKind,
    SessionState,
    TurnRole,
)


def test_all_twelve_practice_tables_are_registered() -> None:
    expected_tables = {
        "practice_themes",
        "practice_competencies",
        "practice_knowledge_packs",
        "practice_scenarios",
        "practice_program_settings",
        "practice_sessions",
        "practice_turns",
        "practice_outcomes",
        "practice_feedback",
        "practice_session_samples",
        "practice_creator_notes",
        "practice_budget_reservations",
    }
    assert expected_tables.issubset(Base.metadata.tables)


def test_practice_mappers_configure() -> None:
    configure_mappers()


def test_practice_enums() -> None:
    assert {s.value for s in KnowledgePackState} == {"draft", "approved", "frozen"}
    assert {s.value for s in ScenarioState} == {"draft", "piloted", "validated"}
    assert {s.value for s in ProgramMode} == {"training", "course"}
    assert {s.value for s in SessionKind} == {"roleplay", "coaching", "knowledge", "research"}
    assert {s.value for s in SessionState} == {"open", "closed"}
    assert {s.value for s in TurnRole} == {"participant", "actor", "system"}
    assert {s.value for s in OutcomeKind} == {"good", "bad", "turn_limit", "safety_stop"}
    assert {s.value for s in CreatorNoteState} == {"new", "accepted", "rejected", "applied"}
    assert {s.value for s in BudgetReservationState} == {"reserved", "settled", "released"}


def test_practice_themes_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeTheme.__tablename__]
    assert "id" in table.columns
    assert "slug" in table.columns
    assert "name" in table.columns
    assert "description" in table.columns
    assert "is_active" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns
    assert not table.columns["slug"].nullable


def test_practice_competencies_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeCompetency.__tablename__]
    assert {
        "id",
        "theme_id",
        "slug",
        "name",
        "level_1",
        "level_2",
        "level_3",
        "order_index",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_practice_knowledge_packs_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeKnowledgePack.__tablename__]
    assert {
        "id",
        "theme_id",
        "version",
        "state",
        "checksum",
        "manifest",
        "content_uri",
        "word_count",
        "approved_by_user_id",
        "approved_at",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_practice_scenarios_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeScenario.__tablename__]
    assert {
        "id",
        "theme_id",
        "slug",
        "title",
        "version",
        "state",
        "difficulty",
        "shared_brief",
        "roles",
        "exits",
        "criteria",
        "debrief_questions",
        "max_turns",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_practice_program_settings_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeProgramSettings.__tablename__]
    assert {
        "id",
        "project_id",
        "mode",
        "theme_id",
        "active_pack_id",
        "is_enabled",
        "max_turns_per_session",
        "max_sessions_per_day",
        "max_chars_per_turn",
        "turn_retention_days",
        "usd_cap_per_participant",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_practice_sessions_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeSession.__tablename__]
    assert {
        "id",
        "program_settings_id",
        "participant_profile_id",
        "pack_id",
        "scenario_id",
        "kind",
        "state",
        "started_at",
        "ended_at",
        "turn_count",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_practice_turns_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeTurn.__tablename__]
    assert {
        "id",
        "session_id",
        "ordinal",
        "role",
        "text",
        "prompt_tokens",
        "output_tokens",
        "thought_tokens",
        "expires_at",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_practice_outcomes_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeOutcome.__tablename__]
    assert {"id", "session_id", "kind", "note", "created_at", "updated_at"}.issubset(
        table.columns.keys()
    )


def test_practice_feedback_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeFeedback.__tablename__]
    assert {
        "id",
        "session_id",
        "competency_id",
        "criterion",
        "passed",
        "quote",
        "quote_verified",
        "suggestion",
        "expires_at",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_practice_session_samples_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeSessionSample.__tablename__]
    assert {
        "id",
        "session_id",
        "real_weak",
        "real_improved",
        "invented_weak",
        "invented_improved",
        "expires_at",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_practice_creator_notes_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeCreatorNote.__tablename__]
    assert {
        "id",
        "author_user_id",
        "session_id",
        "excerpt",
        "note",
        "state",
        "applied_pack_id",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_practice_budget_reservations_columns_and_constraints() -> None:
    table = Base.metadata.tables[PracticeBudgetReservation.__tablename__]
    assert {
        "id",
        "program_settings_id",
        "session_id",
        "reserved_usd",
        "actual_usd",
        "state",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())
