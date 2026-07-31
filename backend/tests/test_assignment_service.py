import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

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
    AssessmentCycleCloseRequest,
    AssessmentCycleCreateRequest,
    AssessmentCycleUpdateRequest,
    AssignmentCreateRequest,
    AssignmentPlanSaveItem,
    AssignmentPlanSaveRequest,
    AssignmentStatusUpdateRequest,
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
from codrut.modules.forms.models import QuestionnaireResponse, QuestionnaireResponseStatus
from codrut.modules.identity.models import User


class FakeAssignmentRepository:
    def __init__(self) -> None:
        self.teams: dict[uuid.UUID, Team] = {}
        self.memberships: list[TeamMembership] = []
        self.assignments: list[QuestionnaireAssignment] = []
        self.assessment_cycles: dict[uuid.UUID, AssessmentCycle] = {}
        self.cycle_questionnaires: list[AssessmentCycleQuestionnaire] = []
        self.cycle_team_memberships: list[AssessmentCycleTeamMembership] = []
        self.deleted_cycle_ids: list[uuid.UUID] = []

    async def add_assessment_cycle(self, cycle: AssessmentCycle) -> AssessmentCycle:
        now = datetime.now(UTC)
        cycle.id = cycle.id or uuid.uuid4()
        cycle.created_at = getattr(cycle, "created_at", None) or now
        cycle.updated_at = getattr(cycle, "updated_at", None) or now
        self.assessment_cycles[cycle.id] = cycle
        return cycle

    async def add_assessment_cycle_questionnaires(
        self,
        questionnaires: list[AssessmentCycleQuestionnaire],
    ) -> list[AssessmentCycleQuestionnaire]:
        now = datetime.now(UTC)
        for questionnaire in questionnaires:
            questionnaire.id = questionnaire.id or uuid.uuid4()
            questionnaire.created_at = getattr(questionnaire, "created_at", None) or now
            questionnaire.updated_at = getattr(questionnaire, "updated_at", None) or now
            self.cycle_questionnaires.append(questionnaire)
        return questionnaires

    async def list_assessment_cycles(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[AssessmentCycle]:
        return sorted(
            [
                cycle
                for cycle in self.assessment_cycles.values()
                if cycle.company_id == company_id and cycle.project_id == project_id
            ],
            key=lambda cycle: cycle.sequence,
            reverse=True,
        )

    async def get_assessment_cycle(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        assessment_cycle_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AssessmentCycle | None:
        del for_update
        cycle = self.assessment_cycles.get(assessment_cycle_id)
        if cycle is None or cycle.company_id != company_id or cycle.project_id != project_id:
            return None
        return cycle

    async def get_open_assessment_cycle(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> AssessmentCycle | None:
        return next(
            (
                cycle
                for cycle in self.assessment_cycles.values()
                if cycle.company_id == company_id
                and cycle.project_id == project_id
                and cycle.status in {AssessmentCycleStatus.draft, AssessmentCycleStatus.active}
            ),
            None,
        )

    async def get_latest_assessment_cycle(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> AssessmentCycle | None:
        cycles = await self.list_assessment_cycles(company_id, project_id)
        return cycles[0] if cycles else None

    async def next_assessment_cycle_sequence(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> int:
        cycles = await self.list_assessment_cycles(company_id, project_id)
        return (cycles[0].sequence if cycles else 0) + 1

    async def list_assessment_cycle_questionnaires(
        self,
        assessment_cycle_id: uuid.UUID,
    ) -> list[AssessmentCycleQuestionnaire]:
        return sorted(
            [
                item
                for item in self.cycle_questionnaires
                if item.assessment_cycle_id == assessment_cycle_id
            ],
            key=lambda item: (item.display_order, item.questionnaire_key),
        )

    async def delete_assessment_cycle(self, cycle: AssessmentCycle) -> None:
        self.deleted_cycle_ids.append(cycle.id)
        self.assessment_cycles.pop(cycle.id, None)
        self.assignments = [
            assignment
            for assignment in self.assignments
            if assignment.assessment_cycle_id != cycle.id
        ]
        self.cycle_questionnaires = [
            item for item in self.cycle_questionnaires if item.assessment_cycle_id != cycle.id
        ]

    async def count_unfinished_cycle_assignments(
        self,
        assessment_cycle_id: uuid.UUID,
    ) -> int:
        return sum(
            assignment.assessment_cycle_id == assessment_cycle_id
            and assignment.status
            not in {
                AssignmentStatus.submitted,
                AssignmentStatus.validated,
                AssignmentStatus.scored,
                AssignmentStatus.cancelled,
            }
            for assignment in self.assignments
        )

    async def cancel_unfinished_cycle_assignments(
        self,
        assessment_cycle_id: uuid.UUID,
    ) -> list[QuestionnaireAssignment]:
        cancelled: list[QuestionnaireAssignment] = []
        for assignment in self.assignments:
            if assignment.assessment_cycle_id != assessment_cycle_id:
                continue
            if assignment.status in {
                AssignmentStatus.submitted,
                AssignmentStatus.validated,
                AssignmentStatus.scored,
                AssignmentStatus.cancelled,
            }:
                continue
            assignment.status = AssignmentStatus.cancelled
            cancelled.append(assignment)
        return cancelled

    async def synchronize_cycle_assignment_deadlines(
        self,
        assessment_cycle_id: uuid.UUID,
        due_at: datetime | None,
    ) -> None:
        for assignment in self.assignments:
            if assignment.assessment_cycle_id == assessment_cycle_id:
                assignment.due_at = due_at

    async def list_cycle_team_memberships(
        self,
        assessment_cycle_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> list[AssessmentCycleTeamMembership]:
        return [
            membership
            for membership in self.cycle_team_memberships
            if membership.assessment_cycle_id == assessment_cycle_id
            and membership.team_id == team_id
        ]

    async def add_cycle_team_memberships(
        self,
        memberships: list[AssessmentCycleTeamMembership],
    ) -> list[AssessmentCycleTeamMembership]:
        for membership in memberships:
            membership.id = membership.id or uuid.uuid4()
            self.cycle_team_memberships.append(membership)
        return memberships

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

    async def get_team_membership_by_id(
        self,
        team_id: uuid.UUID,
        membership_id: uuid.UUID,
    ) -> TeamMembership | None:
        return next(
            (
                membership
                for membership in self.memberships
                if membership.team_id == team_id and membership.id == membership_id
            ),
            None,
        )

    async def delete_team_membership(self, membership: TeamMembership) -> None:
        self.memberships.remove(membership)

    async def list_team_memberships(self, team_id: uuid.UUID) -> list[TeamMembership]:
        return [membership for membership in self.memberships if membership.team_id == team_id]

    async def add_team_membership(self, membership: TeamMembership) -> TeamMembership:
        membership.id = uuid.uuid4()
        self.memberships.append(membership)
        return membership

    async def add_assignment(self, assignment: QuestionnaireAssignment) -> QuestionnaireAssignment:
        assignment.id = uuid.uuid4()
        if assignment.reminder_count is None:
            assignment.reminder_count = 0
        self.assignments.append(assignment)
        return assignment

    async def get_assignment(
        self,
        company_id: uuid.UUID,
        assignment_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> QuestionnaireAssignment | None:
        self.assignment_requested_for_update = for_update
        for assignment in self.assignments:
            if assignment.company_id == company_id and assignment.id == assignment_id:
                return assignment
        return None

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
        assessment_cycle_id: uuid.UUID | None = None,
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
                and (
                    assessment_cycle_id is None
                    or assignment.assessment_cycle_id == assessment_cycle_id
                )
            ):
                return assignment
        return None

    async def list_assignments(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
        assessment_cycle_id: uuid.UUID | None = None,
    ) -> list[QuestionnaireAssignment]:
        assignments = [
            assignment
            for assignment in self.assignments
            if assignment.company_id == company_id
            and (project_id is None or assignment.project_id == project_id)
            and (
                assessment_cycle_id is None or assignment.assessment_cycle_id == assessment_cycle_id
            )
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

    async def get_project_membership(
        self,
        project_id: uuid.UUID,
        participant_profile_id: uuid.UUID,
    ) -> ProjectMembership | None:
        for membership in self.project_memberships:
            if (
                membership.project_id == project_id
                and membership.participant_profile_id == participant_profile_id
            ):
                return membership
        return None

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
        self.responses_by_assignment: dict[uuid.UUID, QuestionnaireResponse] = {}
        self.definitions_by_id: dict[uuid.UUID, object] = {}
        self.deleted_processing_assignment_ids: list[uuid.UUID] = []

    async def get_definition(self, key: str) -> object | None:
        if key in self.active_keys:
            return SimpleNamespace(
                id=uuid.uuid5(uuid.NAMESPACE_URL, f"test-questionnaire-definition:{key}")
            )
        return None

    async def get_latest_version(self, key: str) -> int:
        return 1 if key in self.persisted_keys or key in self.active_keys else 0

    async def get_definition_by_id(self, definition_id: uuid.UUID) -> object | None:
        return self.definitions_by_id.get(definition_id)

    async def unlock_response_for_assignment(
        self,
        assignment_id: uuid.UUID,
    ) -> QuestionnaireResponse | None:
        response = self.responses_by_assignment.get(assignment_id)
        if response is None:
            return None
        response.status = QuestionnaireResponseStatus.draft
        response.submitted_at = None
        return response

    async def delete_submission_processing_for_assignment(
        self,
        assignment_id: uuid.UUID,
    ) -> None:
        self.deleted_processing_assignment_ids.append(assignment_id)


class FakeScoringRepository:
    def __init__(self) -> None:
        self.deleted_assignment_ids: list[uuid.UUID] = []

    async def delete_by_assignment(self, assignment_id: uuid.UUID) -> None:
        self.deleted_assignment_ids.append(assignment_id)


class FakeResultPublicationService:
    def __init__(self) -> None:
        self.reconciled_assignment_ids: list[uuid.UUID] = []

    async def reconcile_assignment(self, assignment_id: uuid.UUID) -> None:
        self.reconciled_assignment_ids.append(assignment_id)


class FakeNestedTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeSession:
    def begin_nested(self) -> FakeNestedTransaction:
        return FakeNestedTransaction()


def make_assignment_service(
    *,
    assignment_repository: FakeAssignmentRepository,
    company_repository: FakeCompanyRepository,
    forms_repository: FakeFormsRepository | None = None,
    identity_repository: FakeIdentityRepository | None = None,
    scoring_repository: FakeScoringRepository | None = None,
    result_publication_service: FakeResultPublicationService | None = None,
) -> AssignmentService:
    service = AssignmentService(cast(Any, FakeSession()))
    service.assignment_repository = cast(Any, assignment_repository)
    service.company_repository = cast(Any, company_repository)
    service.forms_repository = cast(Any, forms_repository or FakeFormsRepository())
    service.identity_repository = cast(Any, identity_repository or FakeIdentityRepository())
    service.scoring_repository = cast(Any, scoring_repository or FakeScoringRepository())
    service.result_publication_service = cast(
        Any,
        result_publication_service or FakeResultPublicationService(),
    )
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
    forms_repository = FakeFormsRepository()
    forms_repository.active_keys.add("lencioni")
    service = make_assignment_service(
        assignment_repository=assignment_repository,
        company_repository=company_repository,
        forms_repository=forms_repository,
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

    await service.remove_team_membership(user_id, company_id, team_id, membership.id)
    assert await service.list_team_memberships(user_id, company_id, team_id) == []

    with pytest.raises(DomainError) as missing_membership:
        await service.remove_team_membership(user_id, company_id, team_id, membership.id)
    assert missing_membership.value.code == "team_membership_not_found"


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
    company_repository.project_memberships.append(
        ProjectMembership(
            company_id=company_id,
            project_id=project_id,
            participant_profile_id=respondent_id,
            active=True,
        )
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


async def test_initial_cycle_pins_questionnaire_when_first_assignment_is_saved() -> None:
    (
        service,
        assignment_repository,
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
        name="Initial cycle",
    )
    company_repository.project_memberships.append(
        ProjectMembership(
            company_id=company_id,
            project_id=project_id,
            participant_profile_id=respondent_id,
            active=True,
        )
    )
    cycle = await assignment_repository.add_assessment_cycle(
        AssessmentCycle(
            company_id=company_id,
            project_id=project_id,
            sequence=1,
            name="Evaluare inițială",
            status=AssessmentCycleStatus.draft,
            created_by_user_id=user_id,
        )
    )

    assignment = await service.create_assignment(
        user_id,
        company_id,
        AssignmentCreateRequest(
            project_id=project_id,
            assessment_cycle_id=cycle.id,
            respondent_profile_id=respondent_id,
            questionnaire_key="lencioni",
            target_type=AssignmentTargetType.self_assessment,
        ),
    )

    pinned = await assignment_repository.list_assessment_cycle_questionnaires(cycle.id)
    assert assignment.assessment_cycle_id == cycle.id
    assert [item.questionnaire_key for item in pinned] == ["lencioni"]
    assert pinned[0].questionnaire_definition_id == assignment.questionnaire_definition_id


async def test_project_assignment_requires_active_respondent_and_person_target_memberships() -> (
    None
):
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
    project_id = uuid.uuid4()
    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Project roster",
    )
    company_repository.project_memberships.extend(
        [
            ProjectMembership(
                company_id=company_id,
                project_id=project_id,
                participant_profile_id=respondent_id,
                active=False,
            ),
            ProjectMembership(
                company_id=company_id,
                project_id=project_id,
                participant_profile_id=target_id,
                active=True,
            ),
        ]
    )

    with pytest.raises(DomainError) as exc_info:
        await service.create_assignment(
            user_id,
            company_id,
            AssignmentCreateRequest(
                project_id=project_id,
                respondent_profile_id=respondent_id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.person,
                target_person_id=target_id,
            ),
        )
    assert exc_info.value.code == "participant_not_in_project"

    company_repository.project_memberships[0].active = True
    company_repository.project_memberships[1].active = False

    with pytest.raises(DomainError) as exc_info:
        await service.create_assignment(
            user_id,
            company_id,
            AssignmentCreateRequest(
                project_id=project_id,
                respondent_profile_id=respondent_id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.person,
                target_person_id=target_id,
            ),
        )
    assert exc_info.value.code == "participant_not_in_project"


async def test_project_assignment_requires_every_existing_team_member_in_project() -> None:
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
    project_id = uuid.uuid4()
    team_id = uuid.uuid4()
    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Project roster",
    )
    company_repository.project_memberships.append(
        ProjectMembership(
            company_id=company_id,
            project_id=project_id,
            participant_profile_id=respondent_id,
            active=True,
        )
    )
    assignment_repository.teams[team_id] = Team(
        id=team_id,
        company_id=company_id,
        name="Mixed team",
        type=TeamType.functional,
    )
    assignment_repository.memberships.append(
        TeamMembership(
            team_id=team_id,
            participant_profile_id=target_id,
            role=TeamMembershipRole.member,
        )
    )

    with pytest.raises(DomainError) as exc_info:
        await service.create_assignment(
            user_id,
            company_id,
            AssignmentCreateRequest(
                project_id=project_id,
                respondent_profile_id=respondent_id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.team,
                target_team_id=team_id,
            ),
        )

    assert exc_info.value.code == "participant_not_in_project"


async def test_project_assignment_plan_requires_every_proposed_team_member_in_project() -> None:
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
    project_id = uuid.uuid4()
    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Project roster",
    )
    company_repository.project_memberships.append(
        ProjectMembership(
            company_id=company_id,
            project_id=project_id,
            participant_profile_id=respondent_id,
            active=True,
        )
    )

    with pytest.raises(DomainError) as exc_info:
        await service.save_assignment_plan(
            user_id,
            company_id,
            AssignmentPlanSaveRequest(
                project_id=project_id,
                assignments=[
                    AssignmentPlanSaveItem(
                        respondent_profile_id=respondent_id,
                        questionnaire_key="lencioni",
                        target_type=AssignmentTargetType.team,
                        target_team_name="Proposed team",
                        target_team_type=TeamType.functional,
                        target_team_member_ids=[respondent_id, target_id],
                        target_team_leader_id=respondent_id,
                    )
                ],
            ),
        )

    assert exc_info.value.code == "participant_not_in_project"


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


async def test_reopening_completed_assignment_unlocks_response_and_clears_score() -> None:
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
    forms_repository = FakeFormsRepository()
    scoring_repository = FakeScoringRepository()
    result_publication_service = FakeResultPublicationService()
    service.forms_repository = cast(Any, forms_repository)
    service.scoring_repository = cast(Any, scoring_repository)
    service.result_publication_service = cast(Any, result_publication_service)
    now = datetime.now(UTC)
    assignment = QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=respondent_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.scored,
        submitted_at=now,
        validated_at=now,
        scored_at=now,
    )
    assignment_repository.assignments.append(assignment)
    response = QuestionnaireResponse(
        id=uuid.uuid4(),
        assignment_id=assignment.id,
        questionnaire_key="lencioni",
        questionnaire_version=1,
        status=QuestionnaireResponseStatus.submitted,
        answers={"lencioni_q01": 3},
        submitted_at=now,
    )
    forms_repository.responses_by_assignment[assignment.id] = response

    updated = await service.update_assignment_status(
        user_id,
        company_id,
        assignment.id,
        AssignmentStatusUpdateRequest(status=AssignmentStatus.started),
    )

    assert updated.status == AssignmentStatus.started
    assert updated.submitted_at is None
    assert updated.validated_at is None
    assert updated.scored_at is None
    assert response.status == QuestionnaireResponseStatus.draft
    assert response.submitted_at is None
    assert assignment_repository.assignment_requested_for_update is True
    assert forms_repository.deleted_processing_assignment_ids == [assignment.id]
    assert scoring_repository.deleted_assignment_ids == [assignment.id]
    assert result_publication_service.reconciled_assignment_ids == [assignment.id]


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
    company_repository.participants[respondent_id].full_name = "Alex Dima"
    company_repository.participants[respondent_id].role_group = "leadership"
    company_repository.participants[target_id].full_name = "Sorin Pavel"
    company_repository.participants[target_id].role_group = "leadership"
    company_repository.participants[ilinca_id] = ParticipantProfile(
        id=ilinca_id,
        company_id=company_id,
        full_name="Mara Ionescu",
        email="mara@example.com",
        role_group="leadership",
    )
    company_repository.participants[alexandra_id] = ParticipantProfile(
        id=alexandra_id,
        company_id=company_id,
        full_name="Diana Luca",
        email="diana@example.com",
        role_group="member",
    )
    company_repository.participants[member_vlad_id] = ParticipantProfile(
        id=member_vlad_id,
        company_id=company_id,
        full_name="Tudor Stan",
        email="tudor@example.com",
        role_group="member",
    )
    company_repository.participants[member_ilinca_id] = ParticipantProfile(
        id=member_ilinca_id,
        company_id=company_id,
        full_name="Ioana Rusu",
        email="member-mara@example.com",
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
    project_participant_ids = {
        respondent_id,
        target_id,
        ilinca_id,
        alexandra_id,
        member_vlad_id,
        member_ilinca_id,
    }
    for participant_id in project_participant_ids:
        participant = company_repository.participants[participant_id]
        manager_name = None
        for relationship in company_repository.reporting_relationships:
            if relationship.participant_profile_id == participant.id:
                manager_name = company_repository.participants[
                    relationship.manager_profile_id
                ].full_name.replace(" ", "")
                break
        company_repository.project_memberships.append(
            ProjectMembership(
                company_id=company_id,
                project_id=project_id,
                participant_profile_id=participant.id,
                reports_to_name=manager_name or "1",
                position=None,
                location=None,
                role_group=participant.role_group,
                active=True,
            )
        )
    leadership_team_id = uuid.uuid4()
    assignment_repository.teams[leadership_team_id] = Team(
        id=leadership_team_id,
        company_id=company_id,
        name="Leadership",
        type=TeamType.leadership,
    )

    plan = await service.build_default_assignment_plan(user_id, company_id, project_id)

    leadership_scope = next(scope for scope in plan.scopes if scope.type == "leadership_team")
    assert leadership_scope.participant_ids == [respondent_id, ilinca_id, target_id]
    leadership_assignments = [
        item for item in plan.assignments if item.scope_type == "leadership_team"
    ]
    assert {item.target_team_leader_id for item in leadership_assignments} == {
        respondent_id
    }

    manager_team_scopes = [scope.name for scope in plan.scopes if scope.type == "manager_team"]
    assert manager_team_scopes == ["Echipa Mara Ionescu", "Echipa Sorin Pavel"]
    assert "Echipa Alex Dima" not in manager_team_scopes

    manager_team_members = {
        scope.name: scope.participant_ids for scope in plan.scopes if scope.type == "manager_team"
    }
    assert manager_team_members == {
        "Echipa Mara Ionescu": [ilinca_id, alexandra_id, member_vlad_id],
        "Echipa Sorin Pavel": [target_id, member_ilinca_id],
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
        if item.questionnaire_key == "lencioni" and item.scope_name == "Echipa Alex Dima"
    ]
    assert andrei_lencioni_team_assignments == []

    andrei_pcm_assignments = [
        item
        for item in plan.assignments
        if item.questionnaire_key == "pcm_base" and item.respondent_profile_id == respondent_id
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
        if item.questionnaire_key == "pcm_base" and item.respondent_profile_id == respondent_id
    ]


async def test_planner_snapshots_top_leader_in_leadership_team() -> None:
    (
        service,
        assignment_repository,
        company_repository,
        user_id,
        company_id,
        leader_id,
        member_id,
        _outside_participant_id,
    ) = seed_assignment_scope()
    project_id = uuid.uuid4()
    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Top leader snapshot",
    )
    company_repository.participants[leader_id].full_name = "Ana Top Leader"
    company_repository.participants[leader_id].role_group = "leadership"
    company_repository.participants[member_id].full_name = "Bogdan Member"
    company_repository.participants[member_id].role_group = "individual"
    company_repository.reporting_relationships.append(
        ParticipantReportingRelationship(
            company_id=company_id,
            manager_profile_id=leader_id,
            participant_profile_id=member_id,
        )
    )
    company_repository.project_memberships.extend(
        [
            ProjectMembership(
                company_id=company_id,
                project_id=project_id,
                participant_profile_id=leader_id,
                reports_to_name=None,
                role_group="leadership",
                active=True,
            ),
            ProjectMembership(
                company_id=company_id,
                project_id=project_id,
                participant_profile_id=member_id,
                reports_to_name="AnaTopLeader",
                role_group="individual",
                active=True,
            ),
        ]
    )
    leadership_team_id = uuid.uuid4()
    assignment_repository.teams[leadership_team_id] = Team(
        id=leadership_team_id,
        company_id=company_id,
        name="Leadership",
        type=TeamType.leadership,
    )

    plan = await service.build_default_assignment_plan(user_id, company_id, project_id)
    leadership_item = next(
        item for item in plan.assignments if item.scope_type == "leadership_team"
    )
    assert leadership_item.target_team_leader_id == leader_id
    cycle = AssessmentCycle(
        id=uuid.uuid4(),
        company_id=company_id,
        project_id=project_id,
        sequence=1,
        name="Planner snapshot",
        status=AssessmentCycleStatus.draft,
    )
    await service._snapshot_cycle_team_membership(
        cycle,
        leadership_team_id,
        AssignmentPlanSaveItem.model_validate(leadership_item.model_dump()),
    )

    snapshot = await assignment_repository.list_cycle_team_memberships(
        cycle.id,
        leadership_team_id,
    )
    roles_by_participant_id = {
        membership.participant_profile_id: membership.role for membership in snapshot
    }
    assert roles_by_participant_id == {
        leader_id: TeamMembershipRole.leader,
        member_id: TeamMembershipRole.member,
    }


async def test_default_assignment_plan_treats_matrix_suffix_as_participant_name() -> None:
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
    matrix_id = uuid.uuid4()
    noemi_id = uuid.uuid4()
    member_id = uuid.uuid4()
    project_id = uuid.uuid4()

    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Matrix Managers",
    )
    company_repository.participants[respondent_id].full_name = "Chief Example"
    company_repository.participants[respondent_id].role_group = "leadership"
    company_repository.participants[target_id].full_name = "Operations Leader"
    company_repository.participants[target_id].role_group = "leadership"
    company_repository.participants[matrix_id] = ParticipantProfile(
        id=matrix_id,
        company_id=company_id,
        full_name="External Leader - Matrix",
        email="matrix@example.com",
        role_group="member",
    )
    company_repository.participants[noemi_id] = ParticipantProfile(
        id=noemi_id,
        company_id=company_id,
        full_name="Noemi Demjen",
        email="noemi@example.com",
        role_group="member",
    )
    company_repository.participants[member_id] = ParticipantProfile(
        id=member_id,
        company_id=company_id,
        full_name="Team Member",
        email="member@example.com",
        role_group="member",
    )
    for participant_id, reports_to_name in [
        (respondent_id, "1"),
        (target_id, "ChiefExample"),
        (matrix_id, "ChiefExample"),
        (noemi_id, "ChiefExample"),
        (member_id, "ExternalLeaderMatrix"),
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
    assignment_repository.teams[uuid.uuid4()] = Team(
        company_id=company_id,
        name="Leadership",
        type=TeamType.leadership,
    )

    plan = await service.build_default_assignment_plan(user_id, company_id, project_id)

    leadership_scope = next(scope for scope in plan.scopes if scope.type == "leadership_team")
    assert set(leadership_scope.participant_ids) == {
        respondent_id,
        target_id,
        matrix_id,
        noemi_id,
    }

    manager_team_scopes = [scope.name for scope in plan.scopes if scope.type == "manager_team"]
    assert "Echipa External Leader - Matrix" in manager_team_scopes

    matrix_team_assignments = [
        item
        for item in plan.assignments
        if item.questionnaire_key == "lencioni"
        and item.scope_name == "Echipa External Leader - Matrix"
    ]
    assert {item.respondent_profile_id for item in matrix_team_assignments} == {member_id}


async def test_default_assignment_plan_uses_project_roles_not_stale_profile_roles() -> None:
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
    stale_manager_id = uuid.uuid4()
    stale_member_id = uuid.uuid4()
    project_id = uuid.uuid4()

    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Project-scoped leadership",
    )
    company_repository.participants[respondent_id].full_name = "Chief Example"
    company_repository.participants[respondent_id].role_group = "leadership"
    company_repository.participants[target_id].full_name = "Operations Leader"
    company_repository.participants[target_id].role_group = "leadership"
    company_repository.participants[stale_manager_id] = ParticipantProfile(
        id=stale_manager_id,
        company_id=company_id,
        full_name="Lower Manager",
        email="lower-manager@example.com",
        role_group="leadership",
    )
    company_repository.participants[stale_member_id] = ParticipantProfile(
        id=stale_member_id,
        company_id=company_id,
        full_name="Lower Member",
        email="lower-member@example.com",
        role_group="member",
    )
    for participant_id, reports_to_name, membership_role in [
        (respondent_id, "1", "leadership"),
        (target_id, "ChiefExample", "leadership"),
        (stale_manager_id, "OperationsLeader", "member"),
        (stale_member_id, "LowerManager", "member"),
    ]:
        company_repository.project_memberships.append(
            ProjectMembership(
                company_id=company_id,
                project_id=project_id,
                participant_profile_id=participant_id,
                reports_to_name=reports_to_name,
                position=None,
                location=None,
                role_group=membership_role,
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
    assert set(leadership_scope.participant_ids) == {respondent_id, target_id}

    assert not [
        item
        for item in plan.assignments
        if item.questionnaire_key == "boss_360" and item.target_person_id == stale_manager_id
    ]
    operations_team_assignments = [
        item
        for item in plan.assignments
        if item.questionnaire_key == "lencioni" and item.scope_name == "Echipa Operations Leader"
    ]
    assert {item.respondent_profile_id for item in operations_team_assignments} == {
        stale_manager_id
    }


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
    service.forms_repository.active_keys.discard("lencioni")
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


async def _seed_assessment_cycle_scope() -> tuple[
    AssignmentService,
    FakeAssignmentRepository,
    FakeCompanyRepository,
    FakeFormsRepository,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
    AssessmentCycle,
    uuid.UUID,
]:
    (
        service,
        assignment_repository,
        company_repository,
        user_id,
        company_id,
        respondent_id,
        _target_id,
        _outside_participant_id,
    ) = seed_assignment_scope()
    forms_repository = cast(FakeFormsRepository, service.forms_repository)
    project_id = uuid.uuid4()
    company_repository.projects[project_id] = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="Leadership program",
    )
    company_repository.project_memberships.append(
        ProjectMembership(
            company_id=company_id,
            project_id=project_id,
            participant_profile_id=respondent_id,
            reports_to_name=None,
            position="Director",
            location=None,
            role_group="leadership",
            active=True,
        )
    )
    company_repository.participants[respondent_id].role_group = "leadership"
    definition_id = uuid.uuid4()
    forms_repository.definitions_by_id[definition_id] = SimpleNamespace(
        id=definition_id,
        key="pcm_base",
        version=7,
        active=False,
    )
    baseline = await assignment_repository.add_assessment_cycle(
        AssessmentCycle(
            company_id=company_id,
            project_id=project_id,
            sequence=1,
            name="Evaluare inițială",
            status=AssessmentCycleStatus.closed,
            closed_at=datetime.now(UTC),
            created_by_user_id=user_id,
        )
    )
    await assignment_repository.add_assessment_cycle_questionnaires(
        [
            AssessmentCycleQuestionnaire(
                assessment_cycle_id=baseline.id,
                questionnaire_definition_id=definition_id,
                questionnaire_key="pcm_base",
                display_order=0,
            )
        ]
    )
    return (
        service,
        assignment_repository,
        company_repository,
        forms_repository,
        user_id,
        company_id,
        project_id,
        respondent_id,
        baseline,
        definition_id,
    )


async def test_cycle_creation_copies_pins_and_rejects_two_open_cycles() -> None:
    (
        service,
        _assignment_repository,
        _company_repository,
        _forms_repository,
        user_id,
        company_id,
        project_id,
        _respondent_id,
        baseline,
        definition_id,
    ) = await _seed_assessment_cycle_scope()

    created = await service.create_assessment_cycle(
        user_id,
        company_id,
        project_id,
        AssessmentCycleCreateRequest(source_cycle_id=baseline.id),
    )

    assert created.sequence == 2
    assert created.name == "Reevaluare 1"
    assert created.status == AssessmentCycleStatus.draft
    assert created.source_cycle_id == baseline.id
    assert [item.questionnaire_definition_id for item in created.questionnaires] == [definition_id]
    assert [
        cycle.id
        for cycle in await service.list_assessment_cycles(
            user_id,
            company_id,
            project_id,
        )
    ] == [created.id, baseline.id]

    with pytest.raises(DomainError) as exc_info:
        await service.create_assessment_cycle(
            user_id,
            company_id,
            project_id,
            AssessmentCycleCreateRequest(source_cycle_id=baseline.id),
        )
    assert exc_info.value.code == "assessment_cycle_open_exists"


async def test_assessment_cycle_draft_lifecycle_and_explicit_unfinished_cancellation() -> None:
    (
        service,
        assignment_repository,
        _company_repository,
        _forms_repository,
        user_id,
        company_id,
        project_id,
        respondent_id,
        baseline,
        definition_id,
    ) = await _seed_assessment_cycle_scope()
    created = await service.create_assessment_cycle(
        user_id,
        company_id,
        project_id,
        AssessmentCycleCreateRequest(source_cycle_id=baseline.id),
    )
    starts_at = datetime(2027, 1, 10, tzinfo=UTC)
    due_at = datetime(2027, 2, 10, tzinfo=UTC)

    updated = await service.update_assessment_cycle(
        user_id,
        company_id,
        project_id,
        created.id,
        AssessmentCycleUpdateRequest(
            name="Reevaluare după atelier",
            starts_at=starts_at,
            due_at=due_at,
        ),
    )
    assert updated.name == "Reevaluare după atelier"
    assert updated.starts_at == starts_at
    assert updated.due_at == due_at

    cycle = await service.activate_assessment_cycle_for_invitation(
        company_id,
        project_id,
        created.id,
    )
    assignment = await assignment_repository.add_assignment(
        QuestionnaireAssignment(
            company_id=company_id,
            project_id=project_id,
            assessment_cycle_id=cycle.id,
            assignment_round_id=uuid.uuid4(),
            respondent_profile_id=respondent_id,
            questionnaire_key="pcm_base",
            questionnaire_definition_id=definition_id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.assigned,
        )
    )

    with pytest.raises(DomainError) as exc_info:
        await service.close_assessment_cycle(
            user_id,
            company_id,
            project_id,
            cycle.id,
            AssessmentCycleCloseRequest(),
        )
    assert exc_info.value.code == "assessment_cycle_has_unfinished_assignments"
    assert exc_info.value.details == {"unfinished_count": 1}

    closed = await service.close_assessment_cycle(
        user_id,
        company_id,
        project_id,
        cycle.id,
        AssessmentCycleCloseRequest(cancel_unfinished=True),
    )
    assert closed.status == AssessmentCycleStatus.closed
    assert closed.closed_at is not None
    assert assignment.status == AssignmentStatus.cancelled


async def test_assessment_cycle_plan_is_cycle_scoped_and_uses_pinned_definition() -> None:
    (
        service,
        assignment_repository,
        company_repository,
        _forms_repository,
        user_id,
        company_id,
        project_id,
        respondent_id,
        baseline,
        definition_id,
    ) = await _seed_assessment_cycle_scope()
    company_repository.participants[respondent_id].pcm_base = "Gânditor"
    company_repository.participants[respondent_id].pcm_phase = "Perseverent"
    cycle_due_at = datetime(2027, 3, 15, tzinfo=UTC)
    cycle_response = await service.create_assessment_cycle(
        user_id,
        company_id,
        project_id,
        AssessmentCycleCreateRequest(source_cycle_id=baseline.id, due_at=cycle_due_at),
    )
    cycle = assignment_repository.assessment_cycles[cycle_response.id]
    previous_assignment = await assignment_repository.add_assignment(
        QuestionnaireAssignment(
            company_id=company_id,
            project_id=project_id,
            assessment_cycle_id=baseline.id,
            assignment_round_id=uuid.uuid4(),
            respondent_profile_id=respondent_id,
            questionnaire_key="pcm_base",
            questionnaire_definition_id=definition_id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.scored,
        )
    )

    plan = await service.build_default_assignment_plan(
        user_id,
        company_id,
        project_id,
        cycle.id,
    )
    pcm_item = next(item for item in plan.assignments if item.questionnaire_key == "pcm_base")
    assert plan.assessment_cycle_id == cycle.id
    assert pcm_item.existing_assignment_id is None
    assert pcm_item.selected is True

    first_save = await service.save_assignment_plan(
        user_id,
        company_id,
        AssignmentPlanSaveRequest(
            project_id=project_id,
            assessment_cycle_id=cycle.id,
            assignments=[AssignmentPlanSaveItem.model_validate(pcm_item.model_dump())],
        ),
    )
    assert first_save.created_count == 1
    saved = first_save.assignments[0]
    assert saved.id != previous_assignment.id
    assert saved.assessment_cycle_id == cycle.id
    persisted = next(item for item in assignment_repository.assignments if item.id == saved.id)
    assert persisted.questionnaire_definition_id == definition_id
    assert persisted.due_at == cycle_due_at

    second_save = await service.save_assignment_plan(
        user_id,
        company_id,
        AssignmentPlanSaveRequest(
            project_id=project_id,
            assessment_cycle_id=cycle.id,
            assignments=[AssignmentPlanSaveItem.model_validate(pcm_item.model_dump())],
        ),
    )
    assert second_save.created_count == 0
    assert second_save.existing_count == 1
    assert second_save.assignments[0].id == saved.id


async def test_followup_plan_preview_uses_current_roster_without_source_assignments() -> None:
    (
        service,
        assignment_repository,
        company_repository,
        _forms_repository,
        user_id,
        company_id,
        project_id,
        respondent_id,
        baseline,
        definition_id,
    ) = await _seed_assessment_cycle_scope()
    company_repository.participants[respondent_id].pcm_base = "Gânditor"
    company_repository.participants[respondent_id].pcm_phase = "Perseverent"
    source_assignment = await assignment_repository.add_assignment(
        QuestionnaireAssignment(
            company_id=company_id,
            project_id=project_id,
            assessment_cycle_id=baseline.id,
            assignment_round_id=uuid.uuid4(),
            respondent_profile_id=respondent_id,
            questionnaire_key="pcm_base",
            questionnaire_definition_id=definition_id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.scored,
        )
    )

    preview = await service.build_default_assignment_plan(
        user_id,
        company_id,
        project_id,
        source_cycle_id=baseline.id,
    )

    assert preview.assessment_cycle_id is None
    assert preview.source_cycle_id == baseline.id
    assert preview.existing_count == 0
    pcm_item = next(item for item in preview.assignments if item.questionnaire_key == "pcm_base")
    assert pcm_item.existing_assignment_id is None
    assert pcm_item.selected is True
    assert source_assignment.id not in {item.existing_assignment_id for item in preview.assignments}


async def test_manual_assignment_rejects_duplicate_within_cycle() -> None:
    (
        service,
        _assignment_repository,
        _company_repository,
        _forms_repository,
        user_id,
        company_id,
        project_id,
        respondent_id,
        baseline,
        definition_id,
    ) = await _seed_assessment_cycle_scope()
    cycle = await service.create_assessment_cycle(
        user_id,
        company_id,
        project_id,
        AssessmentCycleCreateRequest(source_cycle_id=baseline.id),
    )
    payload = AssignmentCreateRequest(
        project_id=project_id,
        assessment_cycle_id=cycle.id,
        respondent_profile_id=respondent_id,
        questionnaire_key="pcm_base",
        target_type=AssignmentTargetType.self_assessment,
    )

    created = await service.create_assignment(user_id, company_id, payload)

    assert created.assessment_cycle_id == cycle.id
    assert created.questionnaire_definition_id == definition_id
    with pytest.raises(DomainError) as exc_info:
        await service.create_assignment(user_id, company_id, payload)
    assert exc_info.value.code == "assessment_cycle_assignment_exists"


async def test_delete_assessment_cycle_requires_draft() -> None:
    (
        service,
        assignment_repository,
        _company_repository,
        _forms_repository,
        user_id,
        company_id,
        project_id,
        _respondent_id,
        baseline,
        _definition_id,
    ) = await _seed_assessment_cycle_scope()
    created = await service.create_assessment_cycle(
        user_id,
        company_id,
        project_id,
        AssessmentCycleCreateRequest(source_cycle_id=baseline.id),
    )
    assignment_repository.assignments.append(
        QuestionnaireAssignment(
            id=uuid.uuid4(),
            company_id=company_id,
            project_id=project_id,
            assessment_cycle_id=created.id,
            assignment_round_id=uuid.uuid4(),
            respondent_profile_id=uuid.uuid4(),
            questionnaire_key="pcm_base",
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.assigned,
        )
    )

    await service.delete_assessment_cycle(
        user_id,
        company_id,
        project_id,
        created.id,
    )

    assert created.id in assignment_repository.deleted_cycle_ids
    assert created.id not in assignment_repository.assessment_cycles
    assert not [
        assignment
        for assignment in assignment_repository.assignments
        if assignment.assessment_cycle_id == created.id
    ]


@pytest.mark.parametrize(
    ("status", "timestamp_field"),
    [
        (AssignmentStatus.invited, "invited_at"),
        (AssignmentStatus.submitted, "submitted_at"),
        (AssignmentStatus.validated, "validated_at"),
        (AssignmentStatus.scored, "scored_at"),
    ],
)
def test_stamp_status_time_records_each_terminal_transition_once(
    status: AssignmentStatus,
    timestamp_field: str,
) -> None:
    assignment = QuestionnaireAssignment(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="pcm_base",
        target_type=AssignmentTargetType.self_assessment,
        status=status,
    )

    _stamp_status_time(assignment)
    first_timestamp = getattr(assignment, timestamp_field)
    _stamp_status_time(assignment)

    assert first_timestamp is not None
    assert getattr(assignment, timestamp_field) == first_timestamp


def test_stamp_status_time_leaves_non_transition_status_unchanged() -> None:
    assignment = QuestionnaireAssignment(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="pcm_base",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.assigned,
    )

    _stamp_status_time(assignment)

    assert assignment.invited_at is None
    assert assignment.started_at is None
    assert assignment.submitted_at is None
    assert assignment.validated_at is None
    assert assignment.scored_at is None
