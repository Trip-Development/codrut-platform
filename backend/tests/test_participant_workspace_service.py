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
            session.add_all([profile, manager, project, team])
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
            session.add_all([team_assignment, person_assignment])
            await session.flush()
            session.add(
                ScoringResult(
                    assignment_id=person_assignment.id,
                    scores={
                        "icare_01_dezvolta_oamenii": {"score": 82, "answered": 3},
                        "icare_02_conduce_prin_puterea_exemplului": {
                            "score": 67,
                            "answered": 3,
                        },
                    },
                    primary_result="icare_02_conduce_prin_puterea_exemplului",
                )
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
            ] == {"score": 82, "answered": 3}

            await session.rollback()
    finally:
        await engine.dispose()
