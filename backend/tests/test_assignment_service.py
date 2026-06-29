import uuid
from typing import Any, cast

import pytest

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.assignments.schemas import (
    AssignmentCreateRequest,
    TeamMembershipCreateRequest,
)
from codrut.modules.assignments.service import (
    AssignmentService,
    _stamp_status_time,
    _validate_target_shape,
)
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    ParticipantProfile,
    ParticipantReportingRelationship,
    ProjectMembership,
)
from codrut.modules.identity.models import User


class FakeAssignmentRepository:
    def __init__(self) -> None:
        self.teams: dict[uuid.UUID, Team] = {}
        self.memberships: list[TeamMembership] = []
        self.assignments: list[QuestionnaireAssignment] = []

    async def add_team(self, team: Team) -> Team:
        team.id = team.id or uuid.uuid4()
        self.teams[team.id] = team
        return team

    async def get_team(self, company_id: uuid.UUID, team_id: uuid.UUID) -> Team | None:
        team = self.teams.get(team_id)
        if team is None or team.company_id != company_id:
            return None
        return team

    async def get_team_by_name(self, company_id: uuid.UUID, name: str) -> Team | None:
        for team in self.teams.values():
            if team.company_id == company_id and team.name == name:
                return team
        return None

    async def list_teams(self, company_id: uuid.UUID) -> list[Team]:
        return sorted(
            [team for team in self.teams.values() if team.company_id == company_id],
            key=lambda team: team.name,
        )

    async def get_team_membership(
        self,
        team_id: uuid.UUID,
        participant_profile_id: uuid.UUID,
    ) -> TeamMembership | None:
        for membership in self.memberships:
            if (
                membership.team_id == team_id
                and membership.participant_profile_id == participant_profile_id
            ):
                return membership
        return None

    async def list_team_memberships(self, team_id: uuid.UUID) -> list[TeamMembership]:
        return [membership for membership in self.memberships if membership.team_id == team_id]

    async def add_team_membership(self, membership: TeamMembership) -> TeamMembership:
        membership.id = uuid.uuid4()
        self.memberships.append(membership)
        return membership

    async def add_assignment(self, assignment: QuestionnaireAssignment) -> QuestionnaireAssignment:
        assignment.id = uuid.uuid4()
        self.assignments.append(assignment)
        return assignment

    async def get_matching_assignment(
        self,
        *,
        company_id: uuid.UUID,
        project_id: uuid.UUID | None,
        respondent_profile_id: uuid.UUID,
        questionnaire_key: str,
        target_type: AssignmentTargetType,
        target_person_id: uuid.UUID | None,
        target_team_id: uuid.UUID | None,
    ) -> QuestionnaireAssignment | None:
        for assignment in self.assignments:
            if (
                assignment.company_id == company_id
                and assignment.project_id == project_id
                and assignment.respondent_profile_id == respondent_profile_id
                and assignment.questionnaire_key == questionnaire_key
                and assignment.target_type == target_type
                and assignment.target_person_id == target_person_id
                and assignment.target_team_id == target_team_id
            ):
                return assignment
        return None

    async def list_assignments(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> list[QuestionnaireAssignment]:
        assignments = [
            assignment
            for assignment in self.assignments
            if assignment.company_id == company_id
            and (project_id is None or assignment.project_id == project_id)
        ]
        return assignments


class FakeCompanyRepository:
    def __init__(self) -> None:
        self.companies: dict[uuid.UUID, Company] = {}
        self.memberships: list[CompanyMembership] = []
        self.participants: dict[uuid.UUID, ParticipantProfile] = {}
        self.projects: dict[uuid.UUID, CompanyProject] = {}
        self.project_memberships: list[ProjectMembership] = []
        self.reporting_relationships: list[ParticipantReportingRelationship] = []

    async def get_company(self, company_id: uuid.UUID) -> Company | None:
        return self.companies.get(company_id)

    async def get_membership(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CompanyMembership | None:
        for membership in self.memberships:
            if membership.company_id == company_id and membership.user_id == user_id:
                return membership
        return None

    async def get_participant_by_id(
        self,
        participant_id: uuid.UUID,
    ) -> ParticipantProfile | None:
        return self.participants.get(participant_id)

    async def list_participants(self, company_id: uuid.UUID) -> list[ParticipantProfile]:
        return [
            participant
            for participant in self.participants.values()
            if participant.company_id == company_id
        ]

    async def list_project_memberships(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[tuple[ProjectMembership, ParticipantProfile]]:
        return [
            (membership, self.participants[membership.participant_profile_id])
            for membership in self.project_memberships
            if membership.company_id == company_id
            and membership.project_id == project_id
            and membership.active
            and membership.participant_profile_id in self.participants
        ]

    async def list_reporting_relationships(
        self,
        company_id: uuid.UUID,
    ) -> list[ParticipantReportingRelationship]:
        return [
            relationship
            for relationship in self.reporting_relationships
            if relationship.company_id == company_id
        ]

    async def get_project(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> CompanyProject | None:
        project = self.projects.get(project_id)
        if project is None or project.company_id != company_id:
            return None
        return project


class FakeIdentityRepository:
    def __init__(self) -> None:
        self.users_by_id: dict[uuid.UUID, User] = {}

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users_by_id.get(user_id)


class FakeFormsRepository:
    def __init__(self) -> None:
        self.active_keys: set[str] = set()
        self.persisted_keys: set[str] = set()

    async def get_definition(self, key: str) -> object | None:
        if key in self.active_keys:
            return object()
        return None

    async def get_latest_version(self, key: str) -> int:
        return 1 if key in self.persisted_keys or key in self.active_keys else 0


def make_assignment_service(
    *,
    assignment_repository: FakeAssignmentRepository,
    company_repository: FakeCompanyRepository,
    forms_repository: FakeFormsRepository | None = None,
    identity_repository: FakeIdentityRepository | None = None,
) -> AssignmentService:
    service = AssignmentService(cast(Any, None))
    service.assignment_repository = cast(Any, assignment_repository)
    service.company_repository = cast(Any, company_repository)
    service.forms_repository = cast(Any, forms_repository or FakeFormsRepository())
    service.identity_repository = cast(Any, identity_repository or FakeIdentityRepository())
    return service


def seed_assignment_scope() -> tuple[
    AssignmentService,
    FakeAssignmentRepository,
    FakeCompanyRepository,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
]:
    company_id = uuid.uuid4()
    other_company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    target_id = uuid.uuid4()
    outside_participant_id = uuid.uuid4()
    assignment_repository = FakeAssignmentRepository()
    company_repository = FakeCompanyRepository()
    company_repository.companies[company_id] = Company(id=company_id, name="Client")
    company_repository.memberships.append(
        CompanyMembership(
            company_id=company_id,
            user_id=user_id,
            role=CompanyMembershipRole.owner,
        )
    )
    company_repository.participants[respondent_id] = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        full_name="Respondent",
        email="respondent@example.com",
    )
    company_repository.participants[target_id] = ParticipantProfile(
        id=target_id,
        company_id=company_id,
        full_name="Target",
        email="target@example.com",
    )
    company_repository.participants[outside_participant_id] = ParticipantProfile(
        id=outside_participant_id,
        company_id=other_company_id,
        full_name="Outside",
        email="outside@example.com",
    )
    service = make_assignment_service(
        assignment_repository=assignment_repository,
        company_repository=company_repository,
    )
    return (
        service,
        assignment_repository,
        company_repository,
        user_id,
        company_id,
        respondent_id,
        target_id,
        outside_participant_id,
    )


async def test_team_membership_requires_participant_in_company_and_rejects_duplicates() -> None:
    (
        service,
        assignment_repository,
        _company_repository,
        user_id,
        company_id,
        respondent_id,
        _target_id,
        outside_participant_id,
    ) = seed_assignment_scope()
    team_id = uuid.uuid4()
    assignment_repository.teams[team_id] = Team(
        id=team_id,
        company_id=company_id,
        name="Leadership",
        type=TeamType.leadership,
    )

    with pytest.raises(DomainError, match="Participant not found"):
        await service.add_team_membership(
            user_id,
            company_id,
            team_id,
            TeamMembershipCreateRequest(
                participant_profile_id=outside_participant_id,
                role=TeamMembershipRole.member,
            ),
        )

    membership = await service.add_team_membership(
        user_id,
        company_id,
        team_id,
        TeamMembershipCreateRequest(
            participant_profile_id=respondent_id,
            role=TeamMembershipRole.leader,
        ),
    )

    assert membership.participant_profile_id == respondent_id
    assert await service.list_team_memberships(user_id, company_id, team_id) == [membership]

    with pytest.raises(DomainError, match="already in this team"):
        await service.add_team_membership(
            user_id,
            company_id,
            team_id,
            TeamMembershipCreateRequest(
                participant_profile_id=respondent_id,
                role=TeamMembershipRole.member,
            ),
        )


async def test_create_assignment_requires_respondent_and_person_target_in_company() -> None:
    (
        service,
        _assignment_repository,
        _company_repository,
        user_id,
        company_id,
        respondent_id,
        target_id,
        outside_participant_id,
    ) = seed_assignment_scope()

    with pytest.raises(DomainError, match="Participant not found"):
        await service.create_assignment(
            user_id,
            company_id,
            AssignmentCreateRequest(
                respondent_profile_id=outside_participant_id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.self_assessment,
            ),
        )

    with pytest.raises(DomainError, match="Participant not found"):
        await service.create_assignment(
            user_id,
            company_id,
            AssignmentCreateRequest(
                respondent_profile_id=respondent_id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.person,
                target_person_id=outside_participant_id,
            ),
        )

    assignment = await service.create_assignment(
        user_id,
        company_id,
        AssignmentCreateRequest(
            respondent_profile_id=respondent_id,
            questionnaire_key="lencioni",
            target_type=AssignmentTargetType.person,
            target_person_id=target_id,
        ),
    )

    assert assignment.respondent_profile_id == respondent_id
    assert assignment.target_person_id == target_id


async def test_create_assignment_rejects_unknown_questionnaire_key() -> None:
    (
        service,
        _assignment_repository,
        _company_repository,
        user_id,
        company_id,
        respondent_id,
        _target_id,
        _outside_participant_id,
    ) = seed_assignment_scope()

    with pytest.raises(DomainError) as exc_info:
        await service.create_assignment(
            user_id,
            company_id,
            AssignmentCreateRequest(
                respondent_profile_id=respondent_id,
                questionnaire_key="unknown_questionnaire",
                target_type=AssignmentTargetType.self_assessment,
            ),
        )

    assert exc_info.value.code == "definition_not_found"


async def test_create_assignment_accepts_active_persisted_questionnaire_key() -> None:
    (
        service,
        _assignment_repository,
        _company_repository,
        user_id,
        company_id,
        respondent_id,
        _target_id,
        _outside_participant_id,
    ) = seed_assignment_scope()
    service.forms_repository.active_keys.add("boss_360")

    assignment = await service.create_assignment(
        user_id,
        company_id,
        AssignmentCreateRequest(
            respondent_profile_id=respondent_id,
            questionnaire_key=" boss_360 ",
            target_type=AssignmentTargetType.self_assessment,
        ),
    )

    assert assignment.questionnaire_key == "boss_360"


async def test_create_assignment_persists_project_scope() -> None:
    (
        service,
        _assignment_repository,
        company_repository,
        user_id,
        company_id,
        respondent_id,
        _target_id,
        _outside_participant_id,
    ) = seed_assignment_scope()
    project_id = uuid.uuid4()
    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Leadership Septembrie",
    )

    assignment = await service.create_assignment(
        user_id,
        company_id,
        AssignmentCreateRequest(
            project_id=project_id,
            respondent_profile_id=respondent_id,
            questionnaire_key="lencioni",
            target_type=AssignmentTargetType.self_assessment,
        ),
    )

    assert assignment.project_id == project_id


async def test_create_assignment_rejects_project_from_another_company() -> None:
    (
        service,
        _assignment_repository,
        company_repository,
        user_id,
        company_id,
        respondent_id,
        _target_id,
        _outside_participant_id,
    ) = seed_assignment_scope()
    project_id = uuid.uuid4()
    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=uuid.uuid4(),
        name="Other",
    )

    with pytest.raises(DomainError) as exc_info:
        await service.create_assignment(
            user_id,
            company_id,
            AssignmentCreateRequest(
                project_id=project_id,
                respondent_profile_id=respondent_id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.self_assessment,
            ),
        )

    assert exc_info.value.code == "project_not_found"


async def test_default_assignment_plan_uses_leadership_peers_and_actual_manager_teams() -> None:
    (
        service,
        assignment_repository,
        company_repository,
        user_id,
        company_id,
        respondent_id,
        target_id,
        _outside_participant_id,
    ) = seed_assignment_scope()
    ilinca_id = uuid.uuid4()
    alexandra_id = uuid.uuid4()
    member_vlad_id = uuid.uuid4()
    member_ilinca_id = uuid.uuid4()
    project_id = uuid.uuid4()

    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Leadership Septembrie",
    )
    company_repository.participants[respondent_id].full_name = "Andrei Vacaru"
    company_repository.participants[respondent_id].role_group = "leadership"
    company_repository.participants[target_id].full_name = "Vlad Soimu"
    company_repository.participants[target_id].role_group = "leadership"
    company_repository.participants[ilinca_id] = ParticipantProfile(
        id=ilinca_id,
        company_id=company_id,
        full_name="Ilinca Corbu",
        email="ilinca@example.com",
        role_group="leadership",
    )
    company_repository.participants[alexandra_id] = ParticipantProfile(
        id=alexandra_id,
        company_id=company_id,
        full_name="Alexandra Giurca",
        email="alexandra@example.com",
        role_group="member",
    )
    company_repository.participants[member_vlad_id] = ParticipantProfile(
        id=member_vlad_id,
        company_id=company_id,
        full_name="Member Vlad",
        email="member-vlad@example.com",
        role_group="member",
    )
    company_repository.participants[member_ilinca_id] = ParticipantProfile(
        id=member_ilinca_id,
        company_id=company_id,
        full_name="Member Ilinca",
        email="member-ilinca@example.com",
        role_group="member",
    )
    company_repository.reporting_relationships.extend(
        [
            ParticipantReportingRelationship(
                company_id=company_id,
                manager_profile_id=respondent_id,
                participant_profile_id=ilinca_id,
            ),
            ParticipantReportingRelationship(
                company_id=company_id,
                manager_profile_id=respondent_id,
                participant_profile_id=target_id,
            ),
            ParticipantReportingRelationship(
                company_id=company_id,
                manager_profile_id=ilinca_id,
                participant_profile_id=alexandra_id,
            ),
            ParticipantReportingRelationship(
                company_id=company_id,
                manager_profile_id=ilinca_id,
                participant_profile_id=member_vlad_id,
            ),
            ParticipantReportingRelationship(
                company_id=company_id,
                manager_profile_id=target_id,
                participant_profile_id=member_ilinca_id,
            ),
        ]
    )
    for participant in company_repository.participants.values():
        manager_name = None
        for relationship in company_repository.reporting_relationships:
            if relationship.participant_profile_id == participant.id:
                manager_name = company_repository.participants[
                    relationship.manager_profile_id
                ].full_name
                break
        company_repository.project_memberships.append(
            ProjectMembership(
                company_id=company_id,
                project_id=project_id,
                participant_profile_id=participant.id,
                reports_to_name=manager_name,
                position=None,
                location=None,
                role_group=participant.role_group,
                active=True,
            )
        )
    assignment_repository.teams[uuid.uuid4()] = Team(
        company_id=company_id,
        name="Leadership",
        type=TeamType.leadership,
    )

    plan = await service.build_default_assignment_plan(user_id, company_id, project_id)

    leadership_scope = next(scope for scope in plan.scopes if scope.type == "leadership_team")
    assert leadership_scope.participant_ids == [respondent_id, ilinca_id, target_id]

    manager_team_scopes = [scope.name for scope in plan.scopes if scope.type == "manager_team"]
    assert manager_team_scopes == ["Echipa Ilinca Corbu", "Echipa Vlad Soimu"]
    assert "Echipa Andrei Vacaru" not in manager_team_scopes

    manager_team_members = {
        scope.name: scope.participant_ids for scope in plan.scopes if scope.type == "manager_team"
    }
    assert manager_team_members == {
        "Echipa Ilinca Corbu": [ilinca_id, alexandra_id, member_vlad_id],
        "Echipa Vlad Soimu": [target_id, member_ilinca_id],
    }

    andrei_360_respondents = {
        item.respondent_profile_id
        for item in plan.assignments
        if item.questionnaire_key == "boss_360" and item.target_person_id == respondent_id
    }
    assert andrei_360_respondents == {respondent_id, ilinca_id, target_id}

    ilinca_360_respondents = {
        item.respondent_profile_id
        for item in plan.assignments
        if item.questionnaire_key == "boss_360" and item.target_person_id == ilinca_id
    }
    assert ilinca_360_respondents == {
        respondent_id,
        ilinca_id,
        target_id,
        alexandra_id,
        member_vlad_id,
    }

    vlad_360_respondents = {
        item.respondent_profile_id
        for item in plan.assignments
        if item.questionnaire_key == "boss_360" and item.target_person_id == target_id
    }
    assert vlad_360_respondents == {
        respondent_id,
        ilinca_id,
        target_id,
        member_ilinca_id,
    }

    andrei_lencioni_team_assignments = [
        item
        for item in plan.assignments
        if item.questionnaire_key == "lencioni"
        and item.scope_name == "Echipa Andrei Vacaru"
    ]
    assert andrei_lencioni_team_assignments == []

    andrei_pcm_assignments = [
        item
        for item in plan.assignments
        if item.questionnaire_key == "pcm_base"
        and item.respondent_profile_id == respondent_id
    ]
    assert len(andrei_pcm_assignments) == 1

    company_repository.participants[respondent_id].pcm_base = "Gânditor"
    company_repository.participants[respondent_id].pcm_phase = "Perseverent"
    plan_without_pcm_gap = await service.build_default_assignment_plan(
        user_id,
        company_id,
        project_id,
    )
    assert not [
        item
        for item in plan_without_pcm_gap.assignments
        if item.questionnaire_key == "pcm_base"
        and item.respondent_profile_id == respondent_id
    ]


async def test_default_assignment_plan_rejects_ambiguous_project_manager_names() -> None:
    (
        service,
        _assignment_repository,
        company_repository,
        user_id,
        company_id,
        respondent_id,
        target_id,
        _outside_participant_id,
    ) = seed_assignment_scope()
    member_id = uuid.uuid4()
    project_id = uuid.uuid4()

    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Ambiguous Managers",
    )
    company_repository.participants[respondent_id].full_name = "Ana Pop"
    company_repository.participants[respondent_id].role_group = "leadership"
    company_repository.participants[target_id].full_name = "Ana Pop"
    company_repository.participants[target_id].role_group = "leadership"
    company_repository.participants[member_id] = ParticipantProfile(
        id=member_id,
        company_id=company_id,
        full_name="Mihai Ionescu",
        email="mihai@example.com",
        role_group="member",
    )
    for participant_id, reports_to_name in [
        (respondent_id, None),
        (target_id, None),
        (member_id, "Ana Pop"),
    ]:
        company_repository.project_memberships.append(
            ProjectMembership(
                company_id=company_id,
                project_id=project_id,
                participant_profile_id=participant_id,
                reports_to_name=reports_to_name,
                position=None,
                location=None,
                role_group=company_repository.participants[participant_id].role_group,
                active=True,
            )
        )

    with pytest.raises(DomainError) as exc_info:
        await service.build_default_assignment_plan(user_id, company_id, project_id)

    assert exc_info.value.code == "manager_name_ambiguous"


async def test_create_assignment_rejects_inactive_persisted_questionnaire_key() -> None:
    (
        service,
        _assignment_repository,
        _company_repository,
        user_id,
        company_id,
        respondent_id,
        _target_id,
        _outside_participant_id,
    ) = seed_assignment_scope()
    service.forms_repository.persisted_keys.add("lencioni")

    with pytest.raises(DomainError) as exc_info:
        await service.create_assignment(
            user_id,
            company_id,
            AssignmentCreateRequest(
                respondent_profile_id=respondent_id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.self_assessment,
            ),
        )

    assert exc_info.value.code == "definition_not_found"


async def test_create_assignment_requires_target_team_in_company() -> None:
    (
        service,
        assignment_repository,
        _company_repository,
        user_id,
        company_id,
        respondent_id,
        _target_id,
        _outside_participant_id,
    ) = seed_assignment_scope()
    other_team_id = uuid.uuid4()
    assignment_repository.teams[other_team_id] = Team(
        id=other_team_id,
        company_id=uuid.uuid4(),
        name="Other",
        type=TeamType.functional,
    )

    with pytest.raises(DomainError, match="Target team not found"):
        await service.create_assignment(
            user_id,
            company_id,
            AssignmentCreateRequest(
                respondent_profile_id=respondent_id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.team,
                target_team_id=other_team_id,
            ),
        )

    team_id = uuid.uuid4()
    assignment_repository.teams[team_id] = Team(
        id=team_id,
        company_id=company_id,
        name="Delivery",
        type=TeamType.functional,
    )

    assignment = await service.create_assignment(
        user_id,
        company_id,
        AssignmentCreateRequest(
            respondent_profile_id=respondent_id,
            questionnaire_key="lencioni",
            target_type=AssignmentTargetType.team,
            target_team_id=team_id,
        ),
    )

    assert assignment.target_team_id == team_id


def test_assignment_target_shape_accepts_self_assignment() -> None:
    _validate_target_shape(
        AssignmentCreateRequest(
            respondent_profile_id=uuid.uuid4(),
            questionnaire_key="pcm_base",
            target_type=AssignmentTargetType.self_assessment,
        )
    )


def test_assignment_target_shape_accepts_person_assignment() -> None:
    _validate_target_shape(
        AssignmentCreateRequest(
            respondent_profile_id=uuid.uuid4(),
            questionnaire_key="boss_360",
            target_type=AssignmentTargetType.person,
            target_person_id=uuid.uuid4(),
        )
    )


def test_assignment_target_shape_rejects_mismatched_target() -> None:
    with pytest.raises(DomainError, match="target does not match"):
        _validate_target_shape(
            AssignmentCreateRequest(
                respondent_profile_id=uuid.uuid4(),
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.team,
                target_person_id=uuid.uuid4(),
            )
        )


def test_stamp_status_time_sets_first_matching_timestamp_once() -> None:
    assignment = QuestionnaireAssignment(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="pcm_base",
        target_type=AssignmentTargetType.self_assessment,
    )
    assignment.status = AssignmentStatus.started

    _stamp_status_time(assignment)
    first_started_at = assignment.started_at
    _stamp_status_time(assignment)

    assert first_started_at is not None
    assert assignment.started_at == first_started_at
