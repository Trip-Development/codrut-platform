from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from codrut.modules.assignments.models import QuestionnaireAssignment
from codrut.modules.communications.models import EmailEvent, EmailSend
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.forms.models import QuestionnaireDefinition, QuestionnaireResponse
from codrut.modules.identity.models import AssignmentInvite, Session
from codrut.modules.scoring.models import ResultPublication, ScoringResult


def test_email_send_idempotency_matches_unique_index_migration() -> None:
    indexes = {index.name: index for index in EmailSend.__table__.indexes}
    idempotency_index = indexes["ix_email_sends_idempotency_key"]
    idempotency_constraints = {
        constraint.name
        for constraint in EmailSend.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert idempotency_index.unique is True
    assert tuple(column.name for column in idempotency_index.columns) == ("idempotency_key",)
    assert "uq_email_sends_idempotency_key" not in idempotency_constraints


def test_participant_company_identity_constraint_matches_migration_name() -> None:
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in ParticipantProfile.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert constraints["uq_participant_profiles_company_id_id"] == (
        "company_id",
        "id",
    )


def test_persisted_questionnaire_and_scoring_payloads_remain_jsonb() -> None:
    assert isinstance(QuestionnaireDefinition.schema.property.columns[0].type, JSONB)
    assert isinstance(QuestionnaireResponse.answers.property.columns[0].type, JSONB)
    assert isinstance(ScoringResult.scores.property.columns[0].type, JSONB)


def test_project_invites_and_assignment_rounds_match_latest_migrations() -> None:
    invite_indexes = {index.name for index in AssignmentInvite.__table__.indexes}
    session_indexes = {index.name for index in Session.__table__.indexes}
    assignment_indexes = {index.name for index in QuestionnaireAssignment.__table__.indexes}

    assert "ix_assignment_invites_project_id" in invite_indexes
    assert "ix_sessions_assignment_invite_id" in session_indexes
    assert "ix_questionnaire_assignments_assignment_round_id" in assignment_indexes
    assert QuestionnaireAssignment.__table__.c.assignment_round_id.nullable is False
    assert "gen_random_uuid" in str(
        QuestionnaireAssignment.__table__.c.assignment_round_id.server_default.arg
    )
    assert QuestionnaireAssignment.__table__.c.questionnaire_definition_id.nullable is False


def test_delivery_event_and_publication_audit_constraints_match_latest_migrations() -> None:
    event_indexes = {index.name: index for index in EmailEvent.__table__.indexes}
    publication_constraints = {
        constraint.name
        for constraint in ResultPublication.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert event_indexes["uq_email_events_provider_event_id"].unique is True
    assert QuestionnaireAssignment.__table__.c.reminder_count.nullable is False
    assert "uq_result_publications_publication_key" in publication_constraints
    assert isinstance(ResultPublication.policy_snapshot.property.columns[0].type, JSONB)
