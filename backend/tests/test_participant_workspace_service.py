import uuid
from datetime import UTC, datetime, timedelta

from codrut.core.database import SessionLocal, engine
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
    TeamType,
)
from codrut.modules.companies.models import Company, CompanyProject, ParticipantProfile
from codrut.modules.identity.models import User, UserRole
from codrut.modules.participants.service import ParticipantWorkspaceService
from codrut.modules.scoring.models import ScoringResult


async def test_participant_workspace_summary_uses_persisted_profile_and_assignments() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"workspace-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(
                id=uuid.uuid4(),
                name=f"Workspace Company {uuid.uuid4().hex[:8]}",
            )
            session.add_all([user, company])
            await session.flush()

            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Ana Participant",
                email=user.email,
                pcm_base="harmonizer",
                pcm_phase="thinker",
            )
            manager = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Mara Manager",
                email=f"manager-{uuid.uuid4().hex[:8]}@example.com",
            )
            reviewer_one = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Reviewer One",
                email=f"reviewer-one-{uuid.uuid4().hex[:8]}@example.com",
            )
            reviewer_two = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Reviewer Two",
                email=f"reviewer-two-{uuid.uuid4().hex[:8]}@example.com",
            )
            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership septembrie",
                due_at=datetime.now(UTC) + timedelta(days=21),
            )
            team = Team(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership",
                type=TeamType.leadership,
            )
            session.add_all([profile, manager, reviewer_one, reviewer_two, project, team])
            await session.flush()

            team_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=profile.id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.team,
                target_team_id=team.id,
                status=AssignmentStatus.invited,
            )
            person_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=profile.id,
                questionnaire_key="boss_360",
                target_type=AssignmentTargetType.person,
                target_person_id=manager.id,
                status=AssignmentStatus.submitted,
            )
            received_assignment_one = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=reviewer_one.id,
                questionnaire_key="boss_360",
                target_type=AssignmentTargetType.person,
                target_person_id=profile.id,
                status=AssignmentStatus.submitted,
            )
            received_assignment_two = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=reviewer_two.id,
                questionnaire_key="boss_360",
                target_type=AssignmentTargetType.person,
                target_person_id=profile.id,
                status=AssignmentStatus.scored,
            )
            session.add_all([
                team_assignment,
                person_assignment,
                received_assignment_one,
                received_assignment_two,
            ])
            await session.flush()
            session.add_all(
                [
                    ScoringResult(
                        assignment_id=person_assignment.id,
                        scores={
                            "icare_01_dezvolta_oamenii": {"score": 4.2, "answered": 3},
                            "icare_02_conduce_prin_puterea_exemplului": {
                                "score": 3.7,
                                "answered": 3,
                            },
                        },
                        primary_result="icare_02_conduce_prin_puterea_exemplului",
                    ),
                    ScoringResult(
                        assignment_id=received_assignment_one.id,
                        scores={
                            "icare_01_dezvolta_oamenii": {"score": 4.0, "answered": 3},
                            "icare_02_conduce_prin_puterea_exemplului": {
                                "score": 3.0,
                                "answered": 3,
                            },
                            "icare_03_creeaza_un_mediu_care_stimuleaza_implicarea": {
                                "score": 1.0,
                                "answered": 3,
                            },
                            "inspiring": {"score": 4.0, "answered": 9},
                        },
                        primary_result="icare_02_conduce_prin_puterea_exemplului",
                    ),
                    ScoringResult(
                        assignment_id=received_assignment_two.id,
                        scores={
                            "icare_01_dezvolta_oamenii": {"score": 5.0, "answered": 3},
                            "icare_02_conduce_prin_puterea_exemplului": {
                                "score": 4.0,
                                "answered": 3,
                            },
                        },
                        primary_result="icare_02_conduce_prin_puterea_exemplului",
                    ),
                ]
            )
            await session.flush()

            summary = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)

            assert summary.participant_full_name == "Ana Participant"
            assert summary.participant_email == user.email
            assert summary.company_name == company.name
            assert summary.project_name == "Leadership septembrie"
            assert summary.pcm_base == "harmonizer"
            assert summary.pcm_phase == "thinker"
            assert [task.assignmentId for task in summary.tasks] == [
                str(team_assignment.id),
                str(person_assignment.id),
            ]
            assert summary.tasks[0].targetLabel == "Leadership"
            assert summary.tasks[0].status == "not_started"
            assert summary.tasks[1].targetLabel == "Mara Manager"
            assert summary.tasks[1].status == "completed"
            assert len(summary.results) == 1
            assert summary.results[0].assignment_id == person_assignment.id
            assert summary.results[0].target_label == "Mara Manager"
            assert summary.results[0].scores[
                "icare_01_dezvolta_oamenii"
            ] == {"score": 4.2, "answered": 3}
            assert summary.received_feedback is not None
            assert summary.received_feedback.completed_count == 2
            assert summary.received_feedback.minimum_completed == 2
            assert summary.received_feedback.visible is True
            assert summary.received_feedback.overall_average == 4.0
            assert {
                dimension.id
                for dimension in summary.received_feedback.dimensions
            } == {
                "icare_01_dezvolta_oamenii",
                "icare_02_conduce_prin_puterea_exemplului",
            }
            assert [
                dimension.model_dump()
                for dimension in summary.received_feedback.dimensions
            ] == [
                {
                    "id": "icare_01_dezvolta_oamenii",
                    "average_score": 4.5,
                    "completed_count": 2,
                },
                {
                    "id": "icare_02_conduce_prin_puterea_exemplului",
                    "average_score": 3.5,
                    "completed_count": 2,
                },
            ]

            await session.rollback()
    finally:
        await engine.dispose()


async def test_participant_workspace_received_feedback_hides_scores_below_threshold() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"workspace-threshold-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(
                id=uuid.uuid4(),
                name=f"Workspace Threshold Company {uuid.uuid4().hex[:8]}",
            )
            session.add_all([user, company])
            await session.flush()

            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Ana Participant",
                email=user.email,
            )
            reviewer = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Reviewer One",
                email=f"reviewer-one-{uuid.uuid4().hex[:8]}@example.com",
            )
            session.add_all([profile, reviewer])
            await session.flush()

            received_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                respondent_profile_id=reviewer.id,
                questionnaire_key="boss_360",
                target_type=AssignmentTargetType.person,
                target_person_id=profile.id,
                status=AssignmentStatus.submitted,
            )
            session.add(received_assignment)
            await session.flush()
            session.add(
                ScoringResult(
                    assignment_id=received_assignment.id,
                    scores={
                        "icare_01_dezvolta_oamenii": {"score": 5.0, "answered": 3},
                    },
                    primary_result="icare_01_dezvolta_oamenii",
                )
            )
            await session.flush()

            summary = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)

            assert summary.received_feedback is not None
            assert summary.received_feedback.completed_count == 1
            assert summary.received_feedback.minimum_completed == 2
            assert summary.received_feedback.visible is False
            assert summary.received_feedback.overall_average is None
            assert summary.received_feedback.dimensions == []

            await session.rollback()
    finally:
        await engine.dispose()
