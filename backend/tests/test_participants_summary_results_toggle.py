import uuid
from datetime import UTC, datetime

import pytest

from codrut.core.database import SessionLocal, engine
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleStatus,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.companies.schemas import (
    CompanyCreateRequest,
    CompanyProjectCreateRequest,
    CompanyProjectUpdateRequest,
)
from codrut.modules.companies.service import CompanyService
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.identity.models import User, UserRole
from codrut.modules.participants.service import ParticipantWorkspaceService
from codrut.modules.scoring.models import ScoringResult
from codrut.modules.scoring.publication import ResultPublicationService


def _feedback_definition() -> QuestionnaireDefinition:
    return QuestionnaireDefinition(
        id=uuid.uuid4(),
        key="boss_360",
        version=1_000_000 + int(uuid.uuid4().hex[:6], 16),
        title="Feedback sintetic",
        schema={"schema_version": "questionnaire.v1", "sections": []},
        private_config={
            "schema": {
                "scoring": {
                    "method": "average_statement_scores_by_section",
                    "scale_max": 5,
                    "score_unit": "grade_1_to_5",
                },
                "sections": [
                    {
                        "id": "feedback",
                        "questions": [
                            {
                                "id": "feedback_signal_a",
                                "label": "Claritate",
                                "type": "statement_score_set",
                            },
                        ],
                    }
                ],
            }
        },
        feedback_policy={
            "participant_results": {
                "publication": "scores",
                "dimension_ids": ["feedback_signal_a"],
                "target_types": ["self"],
                "include_primary_result": True,
            }
        },
        trainer_visibility_policy={"raw_responses": "hidden"},
        content_checksum=None,
        active=True,
    )


@pytest.mark.asyncio
async def test_workspace_summary_hides_results_when_flag_is_false():
    if engine is None:
        pytest.skip("Database is not configured")

    async with SessionLocal() as session:
        company = Company(id=uuid.uuid4(), name=f"Test Co {uuid.uuid4().hex[:6]}")
        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Leadership Proj",
            status=CompanyProjectStatus.active,
            show_participant_results=False,
        )
        session.add_all([company, project])
        await session.flush()

        cycle = AssessmentCycle(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="Cycle 1",
            status=AssessmentCycleStatus.active,
        )
        user = User(
            id=uuid.uuid4(),
            email=f"part-{uuid.uuid4().hex[:6]}@example.com",
            role=UserRole.participant,
            password_hash="hash",
        )
        profile = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            user_id=user.id,
            full_name="Alex Part",
            email=user.email,
        )
        membership = ProjectMembership(
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=profile.id,
        )
        definition = _feedback_definition()
        session.add_all([cycle, user, profile, membership, definition])
        await session.flush()

        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            assessment_cycle_id=cycle.id,
            respondent_profile_id=profile.id,
            questionnaire_key=definition.key,
            questionnaire_definition_id=definition.id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.scored,
        )
        session.add(assignment)
        await session.flush()

        session.add(
            ScoringResult(
                assignment_id=assignment.id,
                scores={"feedback_signal_a": {"score": 4.3}},
                primary_result="feedback_signal_a",
            )
        )
        await session.flush()
        await ResultPublicationService(session).reconcile_assignment(assignment.id)
        await session.commit()

    async with SessionLocal() as session:
        service = ParticipantWorkspaceService(session)
        summary = await service.get_workspace_summary(user_id=user.id)

        # Flag is false
        assert summary.show_participant_results is False

        # Results cut:
        assert summary.results == []
        assert summary.pcm_base is None
        assert summary.pcm_phase is None
        assert summary.received_feedback_groups == []
        assert summary.received_feedback is None

        # Tasks remain:
        assert len(summary.tasks) == 1


@pytest.mark.asyncio
async def test_workspace_summary_shows_results_when_flag_is_true():
    if engine is None:
        pytest.skip("Database is not configured")

    async with SessionLocal() as session:
        company = Company(id=uuid.uuid4(), name=f"Test Co {uuid.uuid4().hex[:6]}")
        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Leadership Open Proj",
            status=CompanyProjectStatus.active,
            show_participant_results=True,
        )
        session.add_all([company, project])
        await session.flush()

        cycle = AssessmentCycle(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="Cycle 1",
            status=AssessmentCycleStatus.active,
        )
        user = User(
            id=uuid.uuid4(),
            email=f"part-{uuid.uuid4().hex[:6]}@example.com",
            role=UserRole.participant,
            password_hash="hash",
        )
        profile = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            user_id=user.id,
            full_name="Elena Part",
            email=user.email,
        )
        membership = ProjectMembership(
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=profile.id,
        )
        definition = _feedback_definition()
        session.add_all([cycle, user, profile, membership, definition])
        await session.flush()

        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            assessment_cycle_id=cycle.id,
            respondent_profile_id=profile.id,
            questionnaire_key=definition.key,
            questionnaire_definition_id=definition.id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.scored,
        )
        session.add(assignment)
        await session.flush()

        session.add(
            ScoringResult(
                assignment_id=assignment.id,
                scores={"feedback_signal_a": {"score": 4.3}},
                primary_result="feedback_signal_a",
            )
        )
        await session.flush()
        await ResultPublicationService(session).reconcile_assignment(assignment.id)
        await session.commit()

    async with SessionLocal() as session:
        service = ParticipantWorkspaceService(session)
        summary = await service.get_workspace_summary(user_id=user.id)

        # Flag is true
        assert summary.show_participant_results is True

        # Results visible:
        assert len(summary.results) == 1
        assert summary.results[0].scores["feedback_signal_a"]["score"] == 4.3


@pytest.mark.asyncio
async def test_company_service_updates_show_participant_results():
    if engine is None:
        pytest.skip("Database is not configured")

    async with SessionLocal() as session:
        owner = User(
            id=uuid.uuid4(),
            email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
            role=UserRole.trainer,
            password_hash="hash",
        )
        session.add(owner)
        await session.flush()

        service = CompanyService(session)
        company = await service.create_company(
            owner.id,
            CompanyCreateRequest(name=f"Test Co {uuid.uuid4().hex[:6]}"),
        )
        project = await service.create_project(
            owner.id,
            company.id,
            CompanyProjectCreateRequest(
                name="Toggle Proj",
                show_participant_results=False,
            ),
        )
        assert project.show_participant_results is False

        # Update show_participant_results to True
        updated = await service.update_project(
            owner.id,
            company.id,
            project.id,
            CompanyProjectUpdateRequest(
                name="Toggle Proj",
                show_participant_results=True,
            ),
        )
        assert updated.show_participant_results is True

        # Update back to False
        updated2 = await service.update_project(
            owner.id,
            company.id,
            project.id,
            CompanyProjectUpdateRequest(
                name="Toggle Proj",
                show_participant_results=False,
            ),
        )
        assert updated2.show_participant_results is False
