from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from codrut.core.database import Base
from codrut.modules.assignments.models import (
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    ResponseVisibilityPolicy,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.identity import models as identity_models  # noqa: F401


def test_assignment_tables_are_registered() -> None:
    assert {"teams", "team_memberships", "questionnaire_assignments"}.issubset(
        Base.metadata.tables
    )
    configure_mappers()


def test_assignment_enums_support_current_workflow() -> None:
    assert {item.value for item in TeamType} == {"leadership", "functional"}
    assert {item.value for item in TeamMembershipRole} == {"leader", "member"}
    assert {item.value for item in AssignmentTargetType} == {"self", "person", "team"}
    assert {item.value for item in AssignmentAccessMode} == {"account_link"}
    assert {item.value for item in ResponseVisibilityPolicy} == {
        "trainer_raw_review",
        "reviewed_anonymized",
    }
    assert "invited" in {item.value for item in AssignmentStatus}
    assert "submitted" in {item.value for item in AssignmentStatus}


def test_team_memberships_allow_many_to_many_without_duplicates() -> None:
    constraints = Base.metadata.tables["team_memberships"].constraints
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("team_id", "participant_profile_id") in unique_columns


def test_assignment_target_shape_is_constrained() -> None:
    checks = {
        constraint.name
        for constraint in Base.metadata.tables["questionnaire_assignments"].constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_questionnaire_assignments_assignment_target_shape" in checks


def test_assignment_tracking_columns_exist() -> None:
    columns = Base.metadata.tables["questionnaire_assignments"].columns

    assert {
        "due_at",
        "invited_at",
        "started_at",
        "submitted_at",
        "validated_at",
        "scored_at",
        "reminder_due_at",
        "last_reminder_sent_at",
    }.issubset(columns.keys())
