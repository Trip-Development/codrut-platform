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
    ParticipantProfile,
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


class FakeCompanyRepository:
    def __init__(self) -> None:
        self.companies: dict[uuid.UUID, Company] = {}
        self.memberships: list[CompanyMembership] = []
        self.participants: dict[uuid.UUID, ParticipantProfile] = {}

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
                questionnaire_key="boss_360",
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
