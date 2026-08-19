import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleQuestionnaire,
    AssessmentCycleStatus,
    AssessmentCycleTeamMembership,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.assignments.schemas import (
    AssessmentCycleUpdateRequest,
    AssignmentCreateRequest,
    AssignmentPlanSaveItem,
    AssignmentPlanSaveRequest,
)
from codrut.modules.assignments.service import AssignmentService
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)
from codrut.modules.forms.service import FormsService
from codrut.modules.identity.models import User, UserRole


async def _ensure_questionnaire_definition(
    session,
    key: str = "lencioni",
) -> QuestionnaireDefinition:
    existing = (
        await session.scalars(
            select(QuestionnaireDefinition).where(
                QuestionnaireDefinition.key == key,
                QuestionnaireDefinition.active.is_(True),
            )
        )
    ).first()
    if existing:
        return existing
    definition = QuestionnaireDefinition(
        id=uuid.uuid4(),
        key=key,
        title=f"Test {key}",
        description="",
        version=1,
        active=True,
        schema={
            "sections": [
                {
                    "id": "section_1",
                    "title": "Section 1",
                    "questions": [
                        {
                            "id": "q1",
                            "type": "scale",
                            "prompt": "Question 1",
                            "required": True,
                        }
                    ],
                }
            ]
        },
    )
    session.add(definition)
    await session.commit()
    return definition


async def _setup_test_project_and_trainer(session) -> tuple[Company, CompanyProject, User]:
    company_id = uuid.uuid4()
    company = Company(id=company_id, name=f"Test Company {uuid.uuid4().hex[:6]}")
    session.add(company)

    trainer_user = User(
        id=uuid.uuid4(),
        email=f"trainer-{uuid.uuid4().hex[:6]}@test.com",
        password_hash="mock_hash",  # noqa: S106
        role=UserRole.trainer,
    )
    session.add(trainer_user)
    session.add(
        CompanyMembership(
            id=uuid.uuid4(),
            company_id=company_id,
            user_id=trainer_user.id,
            role=CompanyMembershipRole.trainer,
        )
    )

    project = CompanyProject(
        id=uuid.uuid4(),
        company_id=company_id,
        name="Test Leadership Project",
        status=CompanyProjectStatus.active,
    )
    session.add(project)
    for q_key in (
        "lencioni",
        "boss_360",
        "icare",
        "pcm_base",
        "distress_drivers",
        "pilot_feedback",
    ):
        await _ensure_questionnaire_definition(session, q_key)
    await session.commit()
    return company, project, trainer_user


@pytest.mark.asyncio
async def test_active_cycle_team_snapshot_superset_addition() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company, project, trainer = await _setup_test_project_and_trainer(session)
        service = AssignmentService(session)

        # Create 2 participants
        p1 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Leader One",
            email=f"leader1-{uuid.uuid4().hex[:4]}@test.com",
        )
        p2 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Member Two",
            email=f"member2-{uuid.uuid4().hex[:4]}@test.com",
        )
        session.add_all([p1, p2])
        await session.flush()

        session.add_all(
            [
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=p1.id,
                ),
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=p2.id,
                ),
            ]
        )
        team = Team(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Leadership Team",
            type=TeamType.leadership,
        )
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMembership(
                    id=uuid.uuid4(),
                    team_id=team.id,
                    participant_profile_id=p1.id,
                    role=TeamMembershipRole.leader,
                ),
                TeamMembership(
                    id=uuid.uuid4(),
                    team_id=team.id,
                    participant_profile_id=p2.id,
                    role=TeamMembershipRole.member,
                ),
            ]
        )

        cycle = AssessmentCycle(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="Evaluation C1",
            status=AssessmentCycleStatus.draft,
        )
        session.add(cycle)
        await session.commit()

        # Save initial plan in draft -> snapshots 2 members
        item_draft = AssignmentPlanSaveItem(
            respondent_profile_id=p1.id,
            questionnaire_key="lencioni",
            target_type=AssignmentTargetType.team,
            target_team_id=team.id,
            target_team_leader_id=p1.id,
            target_team_member_ids=[p1.id, p2.id],
        )
        await service.save_assignment_plan(
            trainer.id,
            company.id,
            AssignmentPlanSaveRequest(
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                assignments=[item_draft],
            ),
        )
        await session.commit()

        # Verify initial snapshot
        memberships_initial = (
            await session.scalars(
                select(AssessmentCycleTeamMembership).where(
                    AssessmentCycleTeamMembership.assessment_cycle_id == cycle.id,
                    AssessmentCycleTeamMembership.team_id == team.id,
                )
            )
        ).all()
        assert len(memberships_initial) == 2

        # Transition cycle to ACTIVE
        cycle.status = AssessmentCycleStatus.active
        await session.commit()

        # Add 3rd participant
        p3 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Member Three",
            email=f"member3-{uuid.uuid4().hex[:4]}@test.com",
        )
        session.add(p3)
        await session.flush()
        session.add(
            ProjectMembership(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                participant_profile_id=p3.id,
            )
        )
        session.add(
            TeamMembership(
                id=uuid.uuid4(),
                team_id=team.id,
                participant_profile_id=p3.id,
                role=TeamMembershipRole.member,
            )
        )
        await session.commit()

        # Save plan on ACTIVE cycle with 3 members (superset addition)
        item_active = AssignmentPlanSaveItem(
            respondent_profile_id=p3.id,
            questionnaire_key="lencioni",
            target_type=AssignmentTargetType.team,
            target_team_id=team.id,
            target_team_leader_id=p1.id,
            target_team_member_ids=[p1.id, p2.id, p3.id],
        )
        await service.save_assignment_plan(
            trainer.id,
            company.id,
            AssignmentPlanSaveRequest(
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                assignments=[item_active],
            ),
        )
        await session.commit()

        # Verify updated snapshot has all 3 members with exact roles
        memberships_updated = (
            await session.scalars(
                select(AssessmentCycleTeamMembership).where(
                    AssessmentCycleTeamMembership.assessment_cycle_id == cycle.id,
                    AssessmentCycleTeamMembership.team_id == team.id,
                )
            )
        ).all()
        assert len(memberships_updated) == 3
        roles_by_id = {m.participant_profile_id: m.role for m in memberships_updated}
        assert roles_by_id[p1.id] == TeamMembershipRole.leader
        assert roles_by_id[p2.id] == TeamMembershipRole.member
        assert roles_by_id[p3.id] == TeamMembershipRole.member


@pytest.mark.asyncio
async def test_active_cycle_team_snapshot_member_removed_raises_distinct_error() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company, project, trainer = await _setup_test_project_and_trainer(session)
        service = AssignmentService(session)

        p1 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Leader One",
            email=f"p1-{uuid.uuid4().hex[:4]}@test.com",
        )
        p2 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Member Two",
            email=f"p2-{uuid.uuid4().hex[:4]}@test.com",
        )
        session.add_all([p1, p2])
        await session.flush()
        session.add_all(
            [
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=p1.id,
                ),
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=p2.id,
                ),
            ]
        )
        team = Team(id=uuid.uuid4(), company_id=company.id, name="T1", type=TeamType.leadership)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMembership(
                    id=uuid.uuid4(),
                    team_id=team.id,
                    participant_profile_id=p1.id,
                    role=TeamMembershipRole.leader,
                ),
                TeamMembership(
                    id=uuid.uuid4(),
                    team_id=team.id,
                    participant_profile_id=p2.id,
                    role=TeamMembershipRole.member,
                ),
            ]
        )
        cycle = AssessmentCycle(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="C1",
            status=AssessmentCycleStatus.draft,
        )
        session.add(cycle)
        await session.commit()

        # Initial snapshot with p1 and p2
        await service.save_assignment_plan(
            trainer.id,
            company.id,
            AssignmentPlanSaveRequest(
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                assignments=[
                    AssignmentPlanSaveItem(
                        respondent_profile_id=p1.id,
                        questionnaire_key="lencioni",
                        target_type=AssignmentTargetType.team,
                        target_team_id=team.id,
                        target_team_leader_id=p1.id,
                        target_team_member_ids=[p1.id, p2.id],
                    )
                ],
            ),
        )
        await session.commit()

        # Now try to save plan with p2 REMOVED
        with pytest.raises(DomainError) as exc_info:
            await service.save_assignment_plan(
                trainer.id,
                company.id,
                AssignmentPlanSaveRequest(
                    project_id=project.id,
                    assessment_cycle_id=cycle.id,
                    assignments=[
                        AssignmentPlanSaveItem(
                            respondent_profile_id=p1.id,
                            questionnaire_key="lencioni",
                            target_type=AssignmentTargetType.team,
                            target_team_id=team.id,
                            target_team_leader_id=p1.id,
                            target_team_member_ids=[p1.id],  # p2 omitted
                        )
                    ],
                ),
            )
        assert exc_info.value.code == "assessment_cycle_team_member_removed"


@pytest.mark.asyncio
async def test_active_cycle_team_snapshot_role_changed_raises_distinct_error() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company, project, trainer = await _setup_test_project_and_trainer(session)
        service = AssignmentService(session)

        p1 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Leader One",
            email=f"p1-{uuid.uuid4().hex[:4]}@test.com",
        )
        p2 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Member Two",
            email=f"p2-{uuid.uuid4().hex[:4]}@test.com",
        )
        session.add_all([p1, p2])
        await session.flush()
        session.add_all(
            [
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=p1.id,
                ),
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=p2.id,
                ),
            ]
        )
        team = Team(id=uuid.uuid4(), company_id=company.id, name="T1", type=TeamType.leadership)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMembership(
                    id=uuid.uuid4(),
                    team_id=team.id,
                    participant_profile_id=p1.id,
                    role=TeamMembershipRole.leader,
                ),
                TeamMembership(
                    id=uuid.uuid4(),
                    team_id=team.id,
                    participant_profile_id=p2.id,
                    role=TeamMembershipRole.member,
                ),
            ]
        )
        cycle = AssessmentCycle(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="C1",
            status=AssessmentCycleStatus.draft,
        )
        session.add(cycle)
        await session.commit()

        # Initial snapshot with p1 as leader, p2 as member
        await service.save_assignment_plan(
            trainer.id,
            company.id,
            AssignmentPlanSaveRequest(
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                assignments=[
                    AssignmentPlanSaveItem(
                        respondent_profile_id=p1.id,
                        questionnaire_key="lencioni",
                        target_type=AssignmentTargetType.team,
                        target_team_id=team.id,
                        target_team_leader_id=p1.id,
                        target_team_member_ids=[p1.id, p2.id],
                    )
                ],
            ),
        )
        await session.commit()

        # Now try to save plan with p2 promoted to leader instead of p1
        with pytest.raises(DomainError) as exc_info:
            await service.save_assignment_plan(
                trainer.id,
                company.id,
                AssignmentPlanSaveRequest(
                    project_id=project.id,
                    assessment_cycle_id=cycle.id,
                    assignments=[
                        AssignmentPlanSaveItem(
                            respondent_profile_id=p1.id,
                            questionnaire_key="lencioni",
                            target_type=AssignmentTargetType.team,
                            target_team_id=team.id,
                            target_team_leader_id=p2.id,  # p2 is leader now -> role changed
                            target_team_member_ids=[p1.id, p2.id],
                        )
                    ],
                ),
            )
        assert exc_info.value.code == "assessment_cycle_team_role_changed"


@pytest.mark.asyncio
async def test_active_cycle_allows_create_assignment_and_blocks_closed() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company, project, trainer = await _setup_test_project_and_trainer(session)
        service = AssignmentService(session)

        p1 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Individual User",
            email=f"indiv-{uuid.uuid4().hex[:4]}@test.com",
        )
        session.add(p1)
        await session.flush()
        session.add(
            ProjectMembership(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                participant_profile_id=p1.id,
            )
        )
        # Create cycle in draft first so questionnaire definition is pinned
        forms_repo = FormsService(session).repository
        distress_def = await forms_repo.get_definition("distress_drivers")
        assert distress_def is not None

        cycle = AssessmentCycle(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="Active Cycle",
            status=AssessmentCycleStatus.active,
        )
        session.add(cycle)
        await session.flush()
        session.add(
            AssessmentCycleQuestionnaire(
                assessment_cycle_id=cycle.id,
                questionnaire_definition_id=distress_def.id,
                questionnaire_key="distress_drivers",
                display_order=0,
            )
        )
        await session.commit()

        # 1. create_assignment on ACTIVE cycle -> succeeds
        req = AssignmentCreateRequest(
            project_id=project.id,
            assessment_cycle_id=cycle.id,
            respondent_profile_id=p1.id,
            questionnaire_key="distress_drivers",
            target_type=AssignmentTargetType.self_assessment,
        )
        created = await service.create_assignment(trainer.id, company.id, req)
        assert created.id is not None
        assert created.assessment_cycle_id == cycle.id

        # 2. Transition cycle to CLOSED
        cycle.status = AssessmentCycleStatus.closed
        await session.commit()

        # 3. create_assignment on CLOSED cycle -> blocked with assessment_cycle_closed
        with pytest.raises(DomainError) as exc_info:
            await service.create_assignment(trainer.id, company.id, req)
        assert exc_info.value.code == "assessment_cycle_closed"

        # 4. save_assignment_plan on CLOSED cycle -> blocked with assessment_cycle_closed
        with pytest.raises(DomainError) as exc_info:
            await service.save_assignment_plan(
                trainer.id,
                company.id,
                AssignmentPlanSaveRequest(
                    project_id=project.id,
                    assessment_cycle_id=cycle.id,
                    assignments=[
                        AssignmentPlanSaveItem(
                            respondent_profile_id=p1.id,
                            questionnaire_key="distress_drivers",
                            target_type=AssignmentTargetType.self_assessment,
                        )
                    ],
                ),
            )
        assert exc_info.value.code == "assessment_cycle_closed"


@pytest.mark.asyncio
async def test_active_cycle_preserves_draft_only_for_cycle_mutations() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company, project, trainer = await _setup_test_project_and_trainer(session)
        service = AssignmentService(session)

        cycle = AssessmentCycle(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="Active Cycle Mutation Check",
            status=AssessmentCycleStatus.active,
        )
        session.add(cycle)
        await session.commit()

        # update_assessment_cycle MUST raise assessment_cycle_not_draft
        with pytest.raises(DomainError) as exc_info:
            await service.update_assessment_cycle(
                trainer.id,
                company.id,
                project.id,
                cycle.id,
                AssessmentCycleUpdateRequest(name="Renamed Active Cycle"),
            )
        assert exc_info.value.code == "assessment_cycle_not_draft"

        # delete_assessment_cycle MUST raise assessment_cycle_not_draft
        with pytest.raises(DomainError) as exc_info:
            await service.delete_assessment_cycle(
                trainer.id,
                company.id,
                project.id,
                cycle.id,
            )
        assert exc_info.value.code == "assessment_cycle_not_draft"


@pytest.mark.asyncio
async def test_active_cycle_michelin_e2e_flow_and_mailpit() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company, project, trainer = await _setup_test_project_and_trainer(session)
        service = AssignmentService(session)

        # 1. Setup Michelin shape: 3 Leaders (DG, DT, HR), 2 existing team members
        leader_a = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Leader A (Director General)",
            email=f"leader_a-{uuid.uuid4().hex[:4]}@michelin-replica.com",
        )
        leader_b = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Leader B (Director Tehnic)",
            email=f"leader_b-{uuid.uuid4().hex[:4]}@michelin-replica.com",
        )
        leader_c = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Leader C (Director HR)",
            email=f"leader_c-{uuid.uuid4().hex[:4]}@michelin-replica.com",
        )
        member_m1 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Member M1",
            email=f"member_m1-{uuid.uuid4().hex[:4]}@michelin-replica.com",
        )
        member_m2 = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Member M2",
            email=f"member_m2-{uuid.uuid4().hex[:4]}@michelin-replica.com",
        )
        all_initial = [leader_a, leader_b, leader_c, member_m1, member_m2]
        session.add_all(all_initial)
        await session.flush()

        session.add_all(
            [
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=leader_a.id,
                    reports_to_name=None,
                ),
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=leader_b.id,
                    reports_to_name=leader_a.full_name,
                ),
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=leader_c.id,
                    reports_to_name=leader_a.full_name,
                ),
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=member_m1.id,
                    reports_to_name=leader_b.full_name,
                ),
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=member_m2.id,
                    reports_to_name=leader_c.full_name,
                ),
            ]
        )

        leadership_team = Team(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Leadership",
            type=TeamType.leadership,
        )
        session.add(leadership_team)
        await session.flush()

        session.add_all(
            [
                TeamMembership(
                    id=uuid.uuid4(),
                    team_id=leadership_team.id,
                    participant_profile_id=leader_a.id,
                    role=TeamMembershipRole.leader,
                ),
                TeamMembership(
                    id=uuid.uuid4(),
                    team_id=leadership_team.id,
                    participant_profile_id=leader_b.id,
                    role=TeamMembershipRole.member,
                ),
                TeamMembership(
                    id=uuid.uuid4(),
                    team_id=leadership_team.id,
                    participant_profile_id=leader_c.id,
                    role=TeamMembershipRole.member,
                ),
            ]
        )

        # 2. Setup Cycle and initial draft plan
        cycle = AssessmentCycle(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="Evaluation Leadership 2026",
            status=AssessmentCycleStatus.draft,
        )
        session.add(cycle)
        await session.commit()

        initial_plan = await service.build_default_assignment_plan(
            trainer.id,
            company.id,
            project_id=project.id,
            assessment_cycle_id=cycle.id,
        )
        assert len(initial_plan.assignments) > 0

        save_items = [
            AssignmentPlanSaveItem.model_validate(item.model_dump())
            for item in initial_plan.assignments
        ]
        saved_initial = await service.save_assignment_plan(
            trainer.id,
            company.id,
            AssignmentPlanSaveRequest(
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                assignments=save_items,
            ),
        )
        await session.commit()

        # 3. Simulate invitations sent & leader_a submitting their distress drivers questionnaire
        cycle.status = AssessmentCycleStatus.active
        await session.commit()

        first_leader_assignment = next(
            a for a in saved_initial.assignments
            if a.respondent_profile_id == leader_a.id and a.questionnaire_key == "distress_drivers"
        )
        first_leader_db_assignment = await session.get(
            QuestionnaireAssignment,
            first_leader_assignment.id,
        )
        assert first_leader_db_assignment is not None
        response = QuestionnaireResponse(
            id=uuid.uuid4(),
            assignment_id=first_leader_assignment.id,
            questionnaire_key="distress_drivers",
            questionnaire_version=1,
            status=QuestionnaireResponseStatus.submitted,
            answers={"q1": "val1"},
            submitted_at=datetime.now(UTC),
        )
        session.add(response)
        first_leader_db_assignment.status = AssignmentStatus.submitted
        await session.commit()

        # 4. Now Andrei adds Remy Bedu to the project under Director Tehnic (leader_b)
        remy = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Remy Bedu",
            email=f"remy.bedu-{uuid.uuid4().hex[:4]}@michelin-replica.com",
        )
        session.add(remy)
        await session.flush()
        session.add(
            ProjectMembership(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                participant_profile_id=remy.id,
                reports_to_name=leader_b.full_name,
            )
        )
        await session.commit()

        # 5. Regenerate and Save plan on ACTIVE cycle
        regenerated_plan = await service.build_default_assignment_plan(
            trainer.id,
            company.id,
            project_id=project.id,
            assessment_cycle_id=cycle.id,
        )
        assert regenerated_plan.suggested_count > 0
        assert regenerated_plan.existing_count == len(saved_initial.assignments)

        regen_save_items = [
            AssignmentPlanSaveItem.model_validate(item.model_dump())
            for item in regenerated_plan.assignments
        ]
        saved_regen = await service.save_assignment_plan(
            trainer.id,
            company.id,
            AssignmentPlanSaveRequest(
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                assignments=regen_save_items,
            ),
        )
        await session.commit()

        # 6. Verify existing data integrity:
        # Check first leader's submitted response is still intact
        reloaded_response = (
            await session.scalars(
                select(QuestionnaireResponse).where(
                    QuestionnaireResponse.assignment_id == first_leader_assignment.id
                )
            )
        ).one()
        assert reloaded_response.status == QuestionnaireResponseStatus.submitted
        assert reloaded_response.answers == {"q1": "val1"}

        # Check Remy has assignments created (e.g. feedback 360 for leader_b / distress / etc.)
        remy_assignments = [
            a for a in saved_regen.assignments
            if a.respondent_profile_id == remy.id
        ]
        assert len(remy_assignments) > 0
        assert saved_regen.created_count > 0
        assert saved_regen.existing_count == len(saved_initial.assignments)
