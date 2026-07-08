import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from codrut.contracts.emails import (
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
)
from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
    TeamType,
)
from codrut.modules.assignments.schemas import AssignmentPlanSaveRequest
from codrut.modules.assignments.service import AssignmentService
from codrut.modules.communications.email_provider import LocalEmailProvider
from codrut.modules.communications.models import EmailSend, EmailSendStatus
from codrut.modules.companies.models import (
    Company,
    CompanyAccessCode,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ParticipantReportingRelationship,
    ProjectMembership,
)
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.companies.schemas import (
    CompanyAccessCodeCreateRequest,
    CompanyAccessCodeRegistrationRequest,
    CompanyCreateRequest,
    CompanyProjectCreateRequest,
    CompanyProjectUpdateRequest,
    ParticipantCreateRequest,
    ParticipantInviteBatchRequest,
    ParticipantUpdateRequest,
    RosterImportRequest,
)
from codrut.modules.companies.service import CompanyService, hash_company_access_code
from codrut.modules.identity.models import AssignmentInvite, Session, User, UserRole
from codrut.modules.identity.schemas import RegisterRequest, SessionPrincipal
from codrut.modules.identity.service import IdentityService


class FailingEmailProvider(LocalEmailProvider):
    async def send(self, message: EmailMessage) -> EmailSendResult:
        self.sent_messages.append(message)
        return EmailSendResult(
            provider=EmailProviderKey.test,
            status=EmailDeliveryStatus.failed,
            message_id="test:failed",
            recipient=message.to,
            error_details="provider unavailable",
        )


class FakeSession:
    def add(self, _obj: Any) -> None:
        return None

    async def flush(self) -> None:
        return None


class FakeCompanyRepository:
    def __init__(self) -> None:
        self.session: Any = FakeSession()
        self.companies_by_id: dict[uuid.UUID, Company] = {}
        self.companies_by_name: dict[str, Company] = {}
        self.access_codes_by_hash: dict[str, CompanyAccessCode] = {}
        self.memberships: list[CompanyMembership] = []
        self.participants: list[ParticipantProfile] = []
        self.projects: list[CompanyProject] = []
        self.project_memberships: list[ProjectMembership] = []
        self.reporting_relationships: list[ParticipantReportingRelationship] = []
        self.assignments: list[QuestionnaireAssignment] = []

    async def list_companies_for_user(self, user_id: uuid.UUID) -> list[Company]:
        company_ids = {
            membership.company_id
            for membership in self.memberships
            if membership.user_id == user_id
        }
        return [company for company in self.companies_by_name.values() if company.id in company_ids]

    async def list_all_companies(self) -> list[Company]:
        return sorted(self.companies_by_name.values(), key=lambda item: item.name)

    async def list_company_summaries(
        self,
        user_id: uuid.UUID,
    ) -> list[tuple[Company, int, int, int, int, int]]:
        company_ids = {
            membership.company_id
            for membership in self.memberships
            if membership.user_id == user_id
        }
        return [
            (
                company,
                4,
                len([project for project in self.projects if project.company_id == company.id]),
                6,
                3,
                1,
            )
            for company in sorted(self.companies_by_name.values(), key=lambda item: item.name)
            if company.id in company_ids
        ]

    async def get_company(self, company_id: uuid.UUID) -> Company | None:
        return self.companies_by_id.get(company_id)

    async def get_company_by_name(self, name: str) -> Company | None:
        return self.companies_by_name.get(name)

    async def add_company(self, company: Company) -> Company:
        company.id = uuid.uuid4()
        self.companies_by_id[company.id] = company
        self.companies_by_name[company.name] = company
        return company

    async def delete_company(self, company: Company) -> None:
        self.companies_by_id.pop(company.id, None)
        self.companies_by_name.pop(company.name, None)
        self.memberships = [
            membership for membership in self.memberships if membership.company_id != company.id
        ]
        self.participants = [
            participant for participant in self.participants if participant.company_id != company.id
        ]
        self.reporting_relationships = [
            relationship
            for relationship in self.reporting_relationships
            if relationship.company_id != company.id
        ]
        self.projects = [project for project in self.projects if project.company_id != company.id]
        self.project_memberships = [
            membership
            for membership in self.project_memberships
            if membership.company_id != company.id
        ]

    async def list_projects(self, company_id: uuid.UUID) -> list[CompanyProject]:
        return [project for project in self.projects if project.company_id == company_id]

    async def list_projects_for_user(self, user_id: uuid.UUID) -> list[tuple[CompanyProject, str]]:
        companies = self.companies_by_id
        company_ids = {
            membership.company_id
            for membership in self.memberships
            if membership.user_id == user_id
        }
        return [
            (project, companies[project.company_id].name)
            for project in self.projects
            if project.company_id in companies and project.company_id in company_ids
        ]

    async def get_project_by_id(
        self,
        project_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
    ) -> tuple[CompanyProject, str] | None:
        company_ids = {
            membership.company_id
            for membership in self.memberships
            if membership.user_id == user_id
        } if user_id is not None else None
        for project in self.projects:
            if (
                project.id == project_id
                and (company_ids is None or project.company_id in company_ids)
            ):
                return project, self.companies_by_id[project.company_id].name
        return None

    async def get_project(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> CompanyProject | None:
        for project in self.projects:
            if project.company_id == company_id and project.id == project_id:
                return project
        return None

    async def get_project_by_name(
        self,
        company_id: uuid.UUID,
        name: str,
    ) -> CompanyProject | None:
        for project in self.projects:
            if project.company_id == company_id and project.name == name:
                return project
        return None

    async def add_project(self, project: CompanyProject) -> CompanyProject:
        now = datetime.now(UTC)
        project.id = uuid.uuid4()
        project.created_at = now
        project.updated_at = now
        self.projects.append(project)
        return project

    async def delete_project(self, project: CompanyProject) -> None:
        self.projects = [existing for existing in self.projects if existing.id != project.id]

    async def add_membership(self, membership: CompanyMembership) -> CompanyMembership:
        membership.id = uuid.uuid4()
        self.memberships.append(membership)
        return membership

    async def get_membership(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CompanyMembership | None:
        for membership in self.memberships:
            if membership.company_id == company_id and membership.user_id == user_id:
                return membership
        return None

    async def list_participants(self, company_id: uuid.UUID) -> list[ParticipantProfile]:
        return [
            participant for participant in self.participants if participant.company_id == company_id
        ]

    async def get_participant(
        self,
        company_id: uuid.UUID,
        participant_id: uuid.UUID,
    ) -> ParticipantProfile | None:
        for participant in self.participants:
            if participant.company_id == company_id and participant.id == participant_id:
                return participant
        return None

    async def list_project_memberships(
        self,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[tuple[ProjectMembership, ParticipantProfile]]:
        participants_by_id = {participant.id: participant for participant in self.participants}
        return [
            (membership, participants_by_id[membership.participant_profile_id])
            for membership in self.project_memberships
            if membership.company_id == company_id
            and membership.project_id == project_id
            and membership.active
            and membership.participant_profile_id in participants_by_id
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

    async def add_project_membership(
        self,
        membership: ProjectMembership,
    ) -> ProjectMembership:
        membership.id = uuid.uuid4()
        self.project_memberships.append(membership)
        return membership

    async def replace_reporting_relationships(
        self,
        company_id: uuid.UUID,
        relationships: list[ParticipantReportingRelationship],
    ) -> list[ParticipantReportingRelationship]:
        self.reporting_relationships = [
            relationship
            for relationship in self.reporting_relationships
            if relationship.company_id != company_id
        ]
        for relationship in relationships:
            relationship.id = uuid.uuid4()
            self.reporting_relationships.append(relationship)
        return relationships

    async def get_participant_by_company_email(
        self,
        company_id: uuid.UUID,
        email: str,
    ) -> ParticipantProfile | None:
        for participant in self.participants:
            if participant.company_id == company_id and participant.email == email:
                return participant
        return None

    async def add_participant(self, participant: ParticipantProfile) -> ParticipantProfile:
        participant.id = uuid.uuid4()
        self.participants.append(participant)
        return participant

    async def get_team_by_company_name(self, _company_id: uuid.UUID, _name: str) -> None:
        return None

    async def list_team_memberships_by_team(self, _team_id: uuid.UUID) -> list[TeamMembership]:
        return []

    async def list_assignments_for_participants(
        self,
        participant_ids: list[uuid.UUID],
    ) -> list[QuestionnaireAssignment]:
        participant_id_set = set(participant_ids)
        return [
            assignment
            for assignment in self.assignments
            if assignment.respondent_profile_id in participant_id_set
        ]

    async def add_access_code(self, access_code: CompanyAccessCode) -> CompanyAccessCode:
        access_code.id = uuid.uuid4()
        self.access_codes_by_hash[access_code.code_hash] = access_code
        return access_code

    async def get_active_access_code(self, code_hash: str) -> CompanyAccessCode | None:
        access_code = self.access_codes_by_hash.get(code_hash)
        if access_code is None or not access_code.active:
            return None
        return access_code

    async def get_unclaimed_participant_by_company_email(
        self,
        company_id: uuid.UUID,
        email: str,
    ) -> ParticipantProfile | None:
        for participant in self.participants:
            if (
                participant.company_id == company_id
                and participant.email == email
                and participant.user_id is None
            ):
                return participant
        return None


class FakeIdentityRepository:
    def __init__(self) -> None:
        self.sessions: list[Session] = []
        self.users_by_email: dict[str, User] = {}
        self.users_by_id: dict[uuid.UUID, User] = {}

    async def get_user_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email.lower())

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users_by_id.get(user_id)

    async def add_user(self, user: User) -> User:
        user.id = uuid.uuid4()
        self.users_by_email[user.email] = user
        self.users_by_id[user.id] = user
        return user

    async def add_session(self, session: Session) -> Session:
        session.id = uuid.uuid4()
        self.sessions.append(session)
        return session


def make_service(
    repository: FakeCompanyRepository,
    identity_repository: FakeIdentityRepository | None = None,
) -> CompanyService:
    service = CompanyService(cast(Any, None))
    service.repository = cast(Any, repository)
    service.identity_repository = cast(Any, identity_repository or FakeIdentityRepository())
    return service


async def test_create_company_strips_name_and_rejects_duplicates() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()

    company = await service.create_company(owner_id, CompanyCreateRequest(name="  Acme  "))

    assert company.name == "Acme"
    assert repository.memberships[0].company_id == company.id
    assert repository.memberships[0].user_id == owner_id
    with pytest.raises(DomainError, match="already exists"):
        await service.create_company(owner_id, CompanyCreateRequest(name="Acme"))


async def test_list_companies_returns_only_membership_companies() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    first = await service.create_company(owner_id, CompanyCreateRequest(name="First"))
    await service.create_company(other_owner_id, CompanyCreateRequest(name="Second"))

    assert await service.list_companies(owner_id) == [first]


async def test_list_company_summaries_returns_operational_counts() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    await service.create_company(owner_id, CompanyCreateRequest(name="Second"))
    first = await service.create_company(owner_id, CompanyCreateRequest(name="First"))

    summaries = await service.list_company_summaries(owner_id)

    assert [summary.name for summary in summaries] == ["First", "Second"]
    assert summaries[0].id == first.id
    assert summaries[0].participant_count == 4
    assert summaries[0].project_count == 0
    assert summaries[0].assignment_count == 6
    assert summaries[0].completed_count == 3
    assert summaries[0].scored_count == 1
    assert summaries[0].stage == "completion"


async def test_get_project_by_id_returns_any_project_with_company_name_for_trainers() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    project = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Leadership"),
    )

    result = await service.get_project_by_id(project.id)

    assert result.id == project.id
    assert result.company_id == company.id
    assert result.company_name == "Client"


async def test_get_project_by_id_can_still_filter_by_membership_for_future_tenancy() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    project = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Leadership"),
    )

    with pytest.raises(DomainError) as exc_info:
        await service.get_project_by_id(project.id, user_id=other_owner_id)

    assert exc_info.value.code == "project_not_found"


@pytest.mark.asyncio
async def test_list_company_summaries_counts_roster_and_assignments_from_database() -> None:
    try:
        async with SessionLocal() as session:
            company = Company(id=uuid.uuid4(), name=f"Summary Company {uuid.uuid4().hex[:8]}")
            trainer = User(
                id=uuid.uuid4(),
                email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("trainer-password-123"),
                role=UserRole.trainer,
            )
            first_participant = ParticipantProfile(
                company_id=company.id,
                full_name="Ana Pop",
                email=f"ana-{uuid.uuid4().hex[:8]}@example.com",
            )
            second_participant = ParticipantProfile(
                company_id=company.id,
                full_name="Mihai Pop",
                email=f"mihai-{uuid.uuid4().hex[:8]}@example.com",
            )
            membership = CompanyMembership(
                company_id=company.id,
                user_id=trainer.id,
                role=CompanyMembershipRole.owner,
            )
            session.add_all([company, trainer, membership, first_participant, second_participant])
            await session.flush()
            session.add_all(
                [
                    QuestionnaireAssignment(
                        company_id=company.id,
                        respondent_profile_id=first_participant.id,
                        questionnaire_key="lencioni",
                        target_type=AssignmentTargetType.self_assessment,
                        status=AssignmentStatus.submitted,
                    ),
                    QuestionnaireAssignment(
                        company_id=company.id,
                        respondent_profile_id=second_participant.id,
                        questionnaire_key="distress_drivers",
                        target_type=AssignmentTargetType.self_assessment,
                        status=AssignmentStatus.assigned,
                    ),
                ]
            )
            await session.flush()

            summaries = await CompanyService(session).list_company_summaries(trainer.id)
            summary = next(item for item in summaries if item.id == company.id)

            assert summary.participant_count == 2
            assert summary.project_count == 0
            assert summary.assignment_count == 2
            assert summary.completed_count == 1
            assert summary.scored_count == 0
            assert summary.stage == "completion"
            await session.rollback()
    finally:
        await engine.dispose()


async def test_delete_company_removes_company_and_related_local_records() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(full_name="Ana Pop", email="ana@example.com"),
    )
    await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Leadership Septembrie 2026"),
    )

    await service.delete_company(owner_id, company.id)

    assert await repository.get_company(company.id) is None
    assert repository.memberships == []
    assert repository.participants == []
    assert repository.projects == []


async def test_trainer_without_company_membership_can_delete_company_for_pilot() -> None:
    repository = FakeCompanyRepository()
    identity_repository = FakeIdentityRepository()
    service = make_service(repository, identity_repository)
    owner_id = uuid.uuid4()
    trainer = User(
        id=uuid.uuid4(),
        email="trainer@example.com",
        password_hash=hash_password("trainer-password-123"),
        role=UserRole.trainer,
    )
    identity_repository.users_by_id[trainer.id] = trainer
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    await service.delete_company(trainer.id, company.id)

    assert await repository.get_company(company.id) is None


async def test_create_project_is_company_scoped_and_cleans_fields() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    project = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(
            name="  Leadership training septembrie 2026  ",
            description="  Cohorta executivă  ",
            status=CompanyProjectStatus.active,
        ),
    )

    assert project.company_id == company.id
    assert project.name == "Leadership training septembrie 2026"
    assert project.description == "Cohorta executivă"
    assert project.status == CompanyProjectStatus.active
    assert await service.list_projects(owner_id, company.id) == [project]


async def test_create_project_rejects_duplicate_name_inside_company() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    payload = CompanyProjectCreateRequest(name="Leadership")

    await service.create_project(owner_id, company.id, payload)

    with pytest.raises(DomainError, match="already exists"):
        await service.create_project(owner_id, company.id, payload)


async def test_update_project_changes_fields_and_allows_clearing_description() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    project = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Leadership", description="Initial"),
    )

    updated = await service.update_project(
        owner_id,
        company.id,
        project.id,
        CompanyProjectUpdateRequest(
            name="Leadership Septembrie",
            description=None,
            status=CompanyProjectStatus.completed,
        ),
    )

    assert updated.name == "Leadership Septembrie"
    assert updated.description is None
    assert updated.status == CompanyProjectStatus.completed


async def test_update_project_rejects_invalid_dates() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    project = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Leadership"),
    )

    with pytest.raises(DomainError, match="due date"):
        await service.update_project(
            owner_id,
            company.id,
            project.id,
            CompanyProjectUpdateRequest(
                starts_at=datetime(2026, 9, 10, tzinfo=UTC),
                due_at=datetime(2026, 9, 1, tzinfo=UTC),
            ),
        )


async def test_delete_project_removes_only_that_project() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    first = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Leadership"),
    )
    second = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Vânzări"),
    )

    await service.delete_project(owner_id, company.id, first.id)

    assert await service.list_projects(owner_id, company.id) == [second]


async def test_trainer_without_company_membership_can_manage_projects_for_pilot() -> None:
    repository = FakeCompanyRepository()
    identity_repository = FakeIdentityRepository()
    service = make_service(repository, identity_repository)
    owner_id = uuid.uuid4()
    trainer = User(
        id=uuid.uuid4(),
        email="trainer@example.com",
        password_hash=hash_password("trainer-password-123"),
        role=UserRole.trainer,
    )
    identity_repository.users_by_id[trainer.id] = trainer
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    project = await service.create_project(
        trainer.id,
        company.id,
        CompanyProjectCreateRequest(name="Leadership"),
    )

    assert project.name == "Leadership"


async def test_create_participant_is_company_scoped_and_cleans_fields() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    participant = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(
            full_name="  Maria Popescu  ",
            email="MARIA@example.com",
            position=" Manager ",
            location=" ",
            role_group="Leadership",
            pcm_profile=None,
        ),
    )

    assert participant.company_id == company.id
    assert participant.full_name == "Maria Popescu"
    assert participant.email == "maria@example.com"
    assert participant.position == "Manager"
    assert participant.location is None


async def test_create_participant_rejects_duplicate_email_inside_company() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    payload = ParticipantCreateRequest(full_name="Ana", email="ana@example.com")

    await service.create_participant(owner_id, company.id, payload)

    with pytest.raises(DomainError, match="already exists"):
        await service.create_participant(owner_id, company.id, payload)


async def test_create_participant_rejects_missing_company() -> None:
    service = make_service(FakeCompanyRepository())

    with pytest.raises(DomainError, match="Company not found"):
        await service.create_participant(
            uuid.uuid4(),
            uuid.uuid4(),
            ParticipantCreateRequest(full_name="Ana", email="ana@example.com"),
        )


async def test_create_participant_allows_trainer_without_company_membership_for_pilot() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    trainer = User(
        id=uuid.uuid4(),
        email="global-trainer@example.com",
        password_hash=hash_password("trainer-password-123"),
        role=UserRole.trainer,
    )
    service.identity_repository.users_by_id[trainer.id] = trainer

    participant = await service.create_participant(
        trainer.id,
        company.id,
        ParticipantCreateRequest(full_name="Ana", email="ana@example.com"),
    )

    assert participant.full_name == "Ana"


async def test_create_participant_rejects_non_trainer_without_company_membership() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    with pytest.raises(DomainError, match="do not have access"):
        await service.create_participant(
            uuid.uuid4(),
            company.id,
            ParticipantCreateRequest(full_name="Ana", email="ana@example.com"),
        )


async def test_update_participant_changes_profile_and_project_membership_fields() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    project = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Pilot iulie"),
    )
    participant = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(
            full_name="Andrei Vacaru",
            email="andrei@example.com",
            reports_to_name="root",
            position="CEO",
            location="București",
            role_group="leadership",
        ),
    )
    membership = await repository.add_project_membership(
        ProjectMembership(
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=participant.id,
            reports_to_name="root",
            position="CEO",
            location="București",
            role_group="leadership",
        )
    )

    updated = await service.update_participant(
        owner_id,
        company.id,
        participant.id,
        ParticipantUpdateRequest(
            project_id=project.id,
            full_name=" Andrei Văcaru ",
            email="ANDREY@example.com",
            reports_to_name="1",
            position="Director General",
            location="Cluj",
            role_group="leadership",
        ),
    )

    assert updated.full_name == "Andrei Văcaru"
    assert updated.email == "andrey@example.com"
    assert updated.reports_to_name is None
    assert updated.position == "Director General"
    assert updated.location == "Cluj"
    assert updated.role_group == "leadership"
    assert membership.reports_to_name is None
    assert membership.position == "Director General"
    assert membership.location == "Cluj"
    assert membership.role_group == "leadership"


async def test_update_participant_rejects_duplicate_company_email() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    first = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(full_name="Ana", email="ana@example.com"),
    )
    await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(full_name="Maria", email="maria@example.com"),
    )

    with pytest.raises(DomainError, match="already exists"):
        await service.update_participant(
            owner_id,
            company.id,
            first.id,
            ParticipantUpdateRequest(email="maria@example.com"),
        )


async def test_update_participant_rejects_claimed_account_email_change() -> None:
    repository = FakeCompanyRepository()
    identity_repository = FakeIdentityRepository()
    service = make_service(repository, identity_repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    user = User(
        id=uuid.uuid4(),
        email="ana@example.com",
        password_hash=hash_password("participant-password-123"),
        role=UserRole.participant,
    )
    identity_repository.users_by_id[user.id] = user
    identity_repository.users_by_email[user.email] = user
    participant = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(full_name="Ana", email="ana@example.com"),
    )
    participant.user_id = user.id

    with pytest.raises(DomainError) as exc_info:
        await service.update_participant(
            owner_id,
            company.id,
            participant.id,
            ParticipantUpdateRequest(email="ana.nou@example.com"),
        )

    assert exc_info.value.code == "participant_email_claimed"
    assert participant.email == "ana@example.com"
    assert user.email == "ana@example.com"


async def test_update_participant_rejects_blank_name_after_trim() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    participant = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(full_name="Ana", email="ana@example.com"),
    )

    with pytest.raises(DomainError) as exc_info:
        await service.update_participant(
            owner_id,
            company.id,
            participant.id,
            ParticipantUpdateRequest(full_name="   "),
        )

    assert exc_info.value.code == "participant_name_required"
    assert participant.full_name == "Ana"


def test_require_trainer_principal_allows_trainer() -> None:
    require_trainer_principal(
        SessionPrincipal(
            user_id=uuid.uuid4(),
            email="trainer@example.com",
            role=UserRole.trainer,
            **{"session_token": "test-session"},
        )
    )


def test_require_trainer_principal_rejects_participant() -> None:
    with pytest.raises(HTTPException) as exc:
        require_trainer_principal(
            SessionPrincipal(
                user_id=uuid.uuid4(),
                email="participant@example.com",
                role=UserRole.participant,
                **{"session_token": "test-session"},
            )
        )

    assert exc.value.status_code == 403


async def test_import_roster_accepts_owner_spreadsheet_columns() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    trainer = User(
        id=uuid.uuid4(),
        email="trainer@example.com",
        password_hash=hash_password("trainer-password-123"),
        role=UserRole.trainer,
    )
    company = await service.create_company(trainer.id, CompanyCreateRequest(name="Client"))
    service.identity_repository.users_by_id[trainer.id] = trainer

    result = await service.import_roster(
        trainer.id,
        company.id,
        RosterImportRequest(
            rows=[
                {
                    "Name": "Maria Popescu",
                    "Reports To": "  Rădăcină  ",
                    "Position": "Manager",
                    "Location": "Bucharest",
                    "email": "maria.popescu@example.com",
                    "Profil PCM": "",
                },
                {
                    "Name": "  Ana Ionescu  ",
                    "Reports To": "Maria Popescu",
                    "Position": "Consultant",
                    "Location": "Bucharest",
                    "email": "ANA@example.com",
                    "Profil PCM": "",
                },
            ]
        ),
    )

    participants = result.participants
    assert result.total_imported == 2
    assert result.email_results == []
    assert result.emails_sent == 0
    assert result.emails_failed == 0
    assert len(participants) == 2
    assert participants[0].full_name == "Maria Popescu"
    assert participants[0].reports_to_name is None
    assert participants[0].role_group == "leadership"
    assert participants[1].full_name == "Ana Ionescu"
    assert participants[1].reports_to_name == "Maria Popescu"
    assert participants[1].email == "ana@example.com"
    assert participants[1].pcm_profile is None


async def test_create_participant_cleans_top_level_reports_to_markers() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    participant = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(
            full_name="Maria",
            email="maria@example.com",
            reports_to_name="root",
        ),
    )

    assert participant.reports_to_name is None

    numeric_root = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(
            full_name="Ana",
            email="ana@example.com",
            reports_to_name=" 2 ",
        ),
    )

    assert numeric_root.reports_to_name is None


async def test_import_roster_rejects_duplicate_row_email() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    with pytest.raises(DomainError, match="Duplicate roster email"):
        await service.import_roster(
            owner_id,
            company.id,
            RosterImportRequest(
                rows=[
                    {"Name": "Ana", "email": "ana@example.com"},
                    {"Name": "Ana Again", "email": "ANA@example.com"},
                ]
            ),
        )


async def test_import_roster_infers_managers_from_reports_to_names_without_positions() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    result = await service.import_roster(
        owner_id,
        company.id,
        RosterImportRequest(
            rows=[
                {
                    "Name": "Andrei Vacaru",
                    "Reports To": "",
                    "Location": "Bucharest",
                    "email": "andrei.vacaru@tripdevelopment.ro",
                },
                {
                    "Name": "Ilinca Corbu",
                    "Reports To": "Andrei Vacaru",
                    "Location": "Bucharest",
                    "email": "ilincacrb4825@gmail.com",
                },
                {
                    "Name": "Member Vlad",
                    "Reports To": "Ilinca Corbu",
                    "Location": "Bucharest",
                    "email": "vlad.soimu@yahoo.com",
                },
            ]
        ),
    )

    participants_by_email = {participant.email: participant for participant in result.participants}
    assert participants_by_email["andrei.vacaru@tripdevelopment.ro"].role_group == "leadership"
    assert participants_by_email["ilincacrb4825@gmail.com"].role_group == "leadership"
    assert participants_by_email["vlad.soimu@yahoo.com"].role_group == "member"


async def test_import_roster_infers_compact_manager_keys_and_numeric_root_marker() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    result = await service.import_roster(
        owner_id,
        company.id,
        RosterImportRequest(
            rows=[
                {
                    "Name": "Chief Example",
                    "Reports To": "1",
                    "Position": "CEO",
                    "email": "chief@example.com",
                },
                {
                    "Name": "Operations Coordinator",
                    "Reports To": "ChiefExample",
                    "Position": "Operations",
                    "email": "ops@example.com",
                },
                {
                    "Name": "Team Member",
                    "Reports To": "OperationsCoordinator",
                    "Position": "Specialist",
                    "email": "member@example.com",
                },
                {
                    "Name": "Title Only Manager",
                    "Reports To": "OperationsCoordinator",
                    "Position": "Manager proiect",
                    "email": "title-only@example.com",
                },
            ]
        ),
    )

    participants_by_email = {participant.email: participant for participant in result.participants}
    assert participants_by_email["chief@example.com"].reports_to_name is None
    assert participants_by_email["chief@example.com"].role_group == "leadership"
    assert participants_by_email["ops@example.com"].reports_to_name == "ChiefExample"
    assert participants_by_email["ops@example.com"].role_group == "leadership"
    assert participants_by_email["member@example.com"].role_group == "member"
    assert participants_by_email["title-only@example.com"].role_group == "member"


async def test_import_roster_treats_matrix_suffix_as_normal_name_text() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    result = await service.import_roster(
        owner_id,
        company.id,
        RosterImportRequest(
            rows=[
                {
                    "Name": "Chief Example",
                    "Reports To": "1",
                    "Position": "CEO",
                    "email": "chief@example.com",
                },
                {
                    "Name": "External Leader - Matrix",
                    "Reports To": "ChiefExample",
                    "Position": "Plant Engineering Mgr",
                    "email": "matrix@example.com",
                },
                {
                    "Name": "Team Member",
                    "Reports To": "ExternalLeaderMatrix",
                    "Position": "Specialist",
                    "email": "member@example.com",
                },
            ]
        ),
    )

    participants_by_email = {participant.email: participant for participant in result.participants}
    assert participants_by_email["chief@example.com"].role_group == "leadership"
    assert participants_by_email["matrix@example.com"].role_group == "leadership"
    assert participants_by_email["member@example.com"].role_group == "member"


async def test_project_roster_reuses_company_participants_and_stores_project_context() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    first_project = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Leadership Iunie"),
    )
    second_project = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Leadership Septembrie"),
    )

    first_import = await service.import_roster(
        owner_id,
        company.id,
        RosterImportRequest(
            project_id=first_project.id,
            rows=[
                {
                    "Name": "Vlad Manager",
                    "Reports To": "",
                    "Position": "Manager",
                    "Location": "București",
                    "email": "vlad@example.com",
                }
            ],
        ),
    )
    second_import = await service.import_roster(
        owner_id,
        company.id,
        RosterImportRequest(
            project_id=second_project.id,
            rows=[
                {
                    "Name": "Vlad Manager",
                    "Reports To": "",
                    "Position": "Director",
                    "Location": "Zalău",
                    "email": "VLAD@example.com",
                }
            ],
        ),
    )

    assert first_import.participants[0].id == second_import.participants[0].id
    assert len(repository.participants) == 1
    assert len(repository.project_memberships) == 2

    first_roster = await service.list_project_participants(owner_id, company.id, first_project.id)
    second_roster = await service.list_project_participants(owner_id, company.id, second_project.id)

    assert first_roster[0].position == "Manager"
    assert first_roster[0].location == "București"
    assert second_roster[0].position == "Director"
    assert second_roster[0].location == "Zalău"


@pytest.mark.asyncio
async def test_two_person_roster_generates_manager_member_default_plan() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            trainer = User(
                id=uuid.uuid4(),
                email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("trainer-password-123"),
                role=UserRole.trainer,
            )
            company = Company(id=uuid.uuid4(), name="Two Person Roster Company")
            session.add_all([trainer, company])
            await session.flush()
            session.add(
                CompanyMembership(
                    company_id=company.id,
                    user_id=trainer.id,
                    role=CompanyMembershipRole.owner,
                )
            )
            await session.flush()

            service = CompanyService(session)
            result = await service.import_roster(
                trainer.id,
                company.id,
                RosterImportRequest(
                    rows=[
                        {
                            "Name": "Vlad Soimu Manager",
                            "Reports To": "",
                            "Position": "Manager",
                            "Location": "Bucharest",
                            "email": "manager@example.com",
                            "Profil PCM": "Gânditor",
                        },
                        {
                            "Name": "Vlad Soimu Membru",
                            "Reports To": "Vlad Soimu Manager",
                            "Position": "Membru echipă",
                            "Location": "Bucharest",
                            "email": "member@example.com",
                            "Profil PCM": "Armonizator",
                        },
                    ]
                ),
            )

            manager, member = result.participants
            assert manager.role_group == "leadership"
            assert member.role_group == "member"

            assignment_service = AssignmentService(session)
            plan = await assignment_service.build_default_assignment_plan(trainer.id, company.id)
            planned = {
                (
                    item.respondent_profile_id,
                    item.questionnaire_key,
                    item.target_type.value,
                    item.target_person_id,
                    item.target_team_type,
                )
                for item in plan.assignments
            }

            assert planned == {
                (manager.id, "lencioni", "team", None, "leadership"),
                (member.id, "lencioni", "team", None, "leadership"),
                (manager.id, "distress_drivers", "self", None, None),
                (manager.id, "pcm_base", "self", None, None),
                (manager.id, "boss_360", "person", manager.id, None),
                (member.id, "boss_360", "person", manager.id, None),
                (member.id, "distress_drivers", "self", None, None),
                (member.id, "pcm_base", "self", None, None),
                (member.id, "boss_360", "person", member.id, None),
                (manager.id, "boss_360", "person", member.id, None),
            }

            save_result = await assignment_service.save_assignment_plan(
                trainer.id,
                company.id,
                payload=AssignmentPlanSaveRequest(
                    assignments=[item.model_dump() for item in plan.assignments],
                ),
            )
            assert save_result.created_count == len(planned)
            assert save_result.existing_count == 0

            repeated_save = await assignment_service.save_assignment_plan(
                trainer.id,
                company.id,
                payload=AssignmentPlanSaveRequest(
                    assignments=[item.model_dump() for item in plan.assignments],
                ),
            )
            assert repeated_save.created_count == 0
            assert repeated_save.existing_count == len(planned)

            link_result = await service.send_participant_invites(
                trainer.id,
                company.id,
                ParticipantInviteBatchRequest(mode="secure_links"),
            )
            assert link_result.total == 2
            assert link_result.links_generated == 2
            assert link_result.emails_sent == 0
            assert all(
                result.invite_url and "/invite/" in result.invite_url
                for result in link_result.results
            )
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_import_roster_creates_invites_and_rank_specific_email_flows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = LocalEmailProvider()

    monkeypatch.setattr(
        "codrut.modules.communications.email_provider.build_email_provider",
        lambda _settings: provider,
    )

    async with SessionLocal() as session:
        trainer = User(
            id=uuid.uuid4(),
            email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("trainer-password-123"),
            role=UserRole.trainer,
        )
        company = Company(id=uuid.uuid4(), name="Roster Flow Company")
        session.add(trainer)
        session.add(company)
        await session.flush()
        session.add(
            CompanyMembership(
                company_id=company.id,
                user_id=trainer.id,
                role=CompanyMembershipRole.owner,
            )
        )
        await session.flush()

        service = CompanyService(session)
        result = await service.import_roster(
            trainer.id,
            company.id,
            RosterImportRequest(
                rows=[
                    {
                        "Name": "Manager Andrei",
                        "Reports To": "",
                        "Position": "Manager",
                        "Location": "Bucharest",
                        "email": "andrei.vacaru@tripdevelopment.ro",
                        "Profil PCM": "",
                    },
                    {
                        "Name": "Manager Ilinca",
                        "Reports To": "",
                        "Position": "Manager",
                        "Location": "Bucharest",
                        "email": "ilincacrb4825@gmail.com",
                        "Profil PCM": "",
                    },
                    {
                        "Name": "Member Vlad",
                        "Reports To": "Manager Andrei",
                        "Position": "Member",
                        "Location": "Bucharest",
                        "email": "vlad.soimu@yahoo.com",
                        "Profil PCM": "",
                    },
                ]
            ),
        )

        participants = result.participants
        assert result.total_imported == 3
        assert result.email_results == []
        assert result.emails_sent == 0
        assert provider.sent_messages == []
        assert [participant.role_group for participant in participants] == [
            "leadership",
            "leadership",
            "member",
        ]

        assignment_result = await session.execute(
            select(QuestionnaireAssignment).where(QuestionnaireAssignment.company_id == company.id)
        )
        assignments = assignment_result.scalars().all()
        assert assignments == []

        invite_result = await session.execute(
            select(AssignmentInvite).where(AssignmentInvite.company_id == company.id)
        )
        assert invite_result.scalars().all() == []

        with pytest.raises(DomainError) as exc_info:
            await service.send_participant_invites(
                trainer.id,
                company.id,
                ParticipantInviteBatchRequest(mode="secure_links"),
            )
        assert exc_info.value.code == "no_assignments"

        assignment_service = AssignmentService(session)
        plan = await assignment_service.build_default_assignment_plan(trainer.id, company.id)
        save_result = await assignment_service.save_assignment_plan(
            trainer.id,
            company.id,
            payload=AssignmentPlanSaveRequest(
                assignments=[item.model_dump() for item in plan.assignments],
            ),
        )
        assert save_result.created_count == len(save_result.assignments)
        assert save_result.existing_count == 0
        assert {
            (assignment.respondent_profile_id, assignment.questionnaire_key)
            for assignment in save_result.assignments
        }.issuperset(
            {
                (participants[0].id, "lencioni"),
                (participants[0].id, "distress_drivers"),
                (participants[0].id, "boss_360"),
                (participants[2].id, "boss_360"),
            }
        )

        repeated_plan = await assignment_service.build_default_assignment_plan(
            trainer.id,
            company.id,
        )
        repeated_save = await assignment_service.save_assignment_plan(
            trainer.id,
            company.id,
            payload=AssignmentPlanSaveRequest(
                assignments=[item.model_dump() for item in repeated_plan.assignments],
            ),
        )
        assert repeated_save.created_count == 0
        assert repeated_save.existing_count == len(repeated_save.assignments)

        link_result = await service.send_participant_invites(
            trainer.id,
            company.id,
            ParticipantInviteBatchRequest(mode="secure_links"),
        )

        assert link_result.total == 3
        assert link_result.links_generated == 3
        assert link_result.emails_sent == 0
        assert link_result.emails_failed == 0
        assert all(
            delivery.invite_url and "/invite/" in delivery.invite_url
            for delivery in link_result.results
        )
        assert {delivery.delivery_mode for delivery in link_result.results} == {"secure_links"}
        assert provider.sent_messages == []

        email_result = await service.send_participant_invites(
            trainer.id,
            company.id,
            ParticipantInviteBatchRequest(mode="email"),
        )

        assert email_result.total == 3
        assert email_result.emails_sent == 3
        assert email_result.emails_failed == 0
        assert len(provider.sent_messages) == 3
        email_send_result = await session.execute(
            select(EmailSend.template_key).where(EmailSend.recipient_email.in_([
                "andrei.vacaru@tripdevelopment.ro",
                "ilincacrb4825@gmail.com",
                "vlad.soimu@yahoo.com",
            ]))
        )
        template_keys = email_send_result.scalars().all()
        assert template_keys.count("account_setup") == 2
        assert template_keys.count("assignment_bundle") == 1

        team_result = await session.execute(
            select(Team)
            .where(Team.company_id == company.id)
            .where(Team.type == TeamType.leadership)
        )
        leadership_team = team_result.scalar_one_or_none()
        assert leadership_team is not None

        membership_result = await session.execute(
            select(TeamMembership).where(TeamMembership.team_id == leadership_team.id)
        )
        assert len(membership_result.scalars().all()) == 2

        repeated_roster = await service.import_roster(
            trainer.id,
            company.id,
            RosterImportRequest(
                rows=[
                    {
                        "Name": "Manager Andrei",
                        "Reports To": "",
                        "Position": "Manager",
                        "Location": "Bucharest",
                        "email": "andrei.vacaru@tripdevelopment.ro",
                        "Profil PCM": "",
                    },
                    {
                        "Name": "Manager Ilinca",
                        "Reports To": "",
                        "Position": "Manager",
                        "Location": "Bucharest",
                        "email": "ilincacrb4825@gmail.com",
                        "Profil PCM": "",
                    },
                    {
                        "Name": "Member Vlad",
                        "Reports To": "Manager Andrei",
                        "Position": "Member",
                        "Location": "Bucharest",
                        "email": "vlad.soimu@yahoo.com",
                        "Profil PCM": "",
                    },
                ]
            ),
        )

        assert repeated_roster.total_imported == 3
        repeated_membership_result = await session.execute(
            select(TeamMembership).where(TeamMembership.team_id == leadership_team.id)
        )
        assert len(repeated_membership_result.scalars().all()) == 2

        assignment_result = await session.execute(
            select(QuestionnaireAssignment).where(QuestionnaireAssignment.company_id == company.id)
        )
        assert {assignment.status for assignment in assignment_result.scalars().all()} == {
            AssignmentStatus.invited
        }

        invite_result = await session.execute(
            select(AssignmentInvite).where(AssignmentInvite.company_id == company.id)
        )
        invites = invite_result.scalars().all()
        assert len(invites) == 3
        assert all(
            invite.expires_at >= datetime.now(UTC) + timedelta(days=3600)
            for invite in invites
        )

        statuses = await service.list_participant_invitation_statuses(
            trainer.id,
            company.id,
        )
        statuses_by_participant = {status.participant_id: status for status in statuses}
        assert len(statuses_by_participant) == 3
        assert all(status.has_active_secure_link for status in statuses_by_participant.values())
        assert all(
            status.latest_email_status == EmailSendStatus.accepted
            for status in statuses_by_participant.values()
        )
        assert all(status.email_send_count == 1 for status in statuses_by_participant.values())
        assert all(
            status.active_secure_link_url and "/invite/" in status.active_secure_link_url
            for status in statuses_by_participant.values()
        )

        identity_service = IdentityService(session)
        manager_invite = next(
            invite for invite in invites if invite.respondent_profile_id == participants[1].id
        )
        member_invite = next(
            invite for invite in invites if invite.respondent_profile_id == participants[2].id
        )

        verify_manager = await identity_service.verify_invite_token(manager_invite.token)
        assert verify_manager.is_leadership is True
        assert verify_manager.already_registered is False
        assert {"lencioni", "distress_drivers", "boss_360"}.issubset(
            {task.questionnaireKey for task in verify_manager.tasks}
        )

        registration_token = next(
            invite.token for invite in invites if invite.respondent_profile_id == participants[0].id
        )
        registration_password = "".join(["Satinmint3!", "23"])
        register_result = await identity_service.register(
            RegisterRequest(
                email=participants[0].email,
                password=registration_password,
                token=registration_token,
                terms_accepted=True,
            )
        )
        assert register_result.response.email == participants[0].email

        verify_member = await identity_service.verify_invite_token_and_create_session(
            member_invite.token
        )
        assert verify_member.response.is_leadership is False
        assert verify_member.session_token is not None

        repeat_import = await service.import_roster(
            trainer.id,
            company.id,
            RosterImportRequest(
                rows=[
                    {
                        "Name": "Repeat Manager",
                        "Reports To": "",
                        "Position": "Manager",
                        "Location": "Bucharest",
                        "email": "repeat.manager@example.com",
                        "Profil PCM": "",
                    },
                    {
                        "Name": "Repeat Member",
                        "Reports To": "Repeat Manager",
                        "Position": "Member",
                        "Location": "Bucharest",
                        "email": "repeat.member@example.com",
                        "Profil PCM": "",
                    },
                ]
            ),
        )
        assert repeat_import.total_imported == 2

        relationship_result = await session.execute(
            select(ParticipantReportingRelationship).where(
                ParticipantReportingRelationship.company_id == company.id
            )
        )
        relationships = relationship_result.scalars().all()
        repeat_member = next(
            participant
            for participant in repeat_import.participants
            if participant.email == "repeat.member@example.com"
        )
        repeat_manager = next(
            participant
            for participant in repeat_import.participants
            if participant.email == "repeat.manager@example.com"
        )
        assert any(
            relationship.participant_profile_id == repeat_member.id
            and relationship.manager_profile_id == repeat_manager.id
            for relationship in relationships
        )

        await session.rollback()


@pytest.mark.asyncio
async def test_send_project_invites_uses_earliest_project_close_or_due_date() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            trainer = User(
                id=uuid.uuid4(),
                email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("trainer-password-123"),
                role=UserRole.trainer,
            )
            company = Company(id=uuid.uuid4(), name="Invite Window Company")
            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership iulie",
                due_at=datetime.now(UTC) + timedelta(days=2),
                form_closes_at=datetime.now(UTC) + timedelta(days=5),
            )
            participant = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                email="ana.window@example.com",
                full_name="Ana Window",
                anonymous_name="Participant 1",
            )
            session.add_all([trainer, company, project, participant])
            await session.flush()
            session.add_all(
                [
                    CompanyMembership(
                        company_id=company.id,
                        user_id=trainer.id,
                        role=CompanyMembershipRole.owner,
                    ),
                    ProjectMembership(
                        company_id=company.id,
                        project_id=project.id,
                        participant_profile_id=participant.id,
                    ),
                    QuestionnaireAssignment(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        project_id=project.id,
                        respondent_profile_id=participant.id,
                        questionnaire_key="lencioni",
                        target_type=AssignmentTargetType.self_assessment,
                        status=AssignmentStatus.assigned,
                        due_at=datetime.now(UTC) + timedelta(days=10),
                    ),
                ]
            )
            await session.flush()

            result = await CompanyService(session).send_participant_invites(
                trainer.id,
                company.id,
                ParticipantInviteBatchRequest(mode="secure_links", project_id=project.id),
            )

            assert result.links_generated == 1
            invite_result = await session.execute(
                select(AssignmentInvite).where(AssignmentInvite.company_id == company.id)
            )
            invite = invite_result.scalar_one()
            assert int(invite.expires_at.timestamp()) == int(project.due_at.timestamp())
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_send_project_invites_rejects_closed_project_window() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            trainer = User(
                id=uuid.uuid4(),
                email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("trainer-password-123"),
                role=UserRole.trainer,
            )
            company = Company(id=uuid.uuid4(), name="Closed Invite Window Company")
            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership inchis",
                form_closes_at=datetime.now(UTC) - timedelta(minutes=1),
                due_at=datetime.now(UTC) + timedelta(days=3),
            )
            participant = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                email="ana.closed@example.com",
                full_name="Ana Closed",
                anonymous_name="Participant 1",
            )
            session.add_all([trainer, company, project, participant])
            await session.flush()
            session.add_all(
                [
                    CompanyMembership(
                        company_id=company.id,
                        user_id=trainer.id,
                        role=CompanyMembershipRole.owner,
                    ),
                    ProjectMembership(
                        company_id=company.id,
                        project_id=project.id,
                        participant_profile_id=participant.id,
                    ),
                    QuestionnaireAssignment(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        project_id=project.id,
                        respondent_profile_id=participant.id,
                        questionnaire_key="lencioni",
                        target_type=AssignmentTargetType.self_assessment,
                        status=AssignmentStatus.assigned,
                    ),
                ]
            )
            await session.flush()

            with pytest.raises(DomainError) as exc_info:
                await CompanyService(session).send_participant_invites(
                    trainer.id,
                    company.id,
                    ParticipantInviteBatchRequest(mode="secure_links", project_id=project.id),
                )

            assert exc_info.value.code == "project_closed"
            invite_result = await session.execute(
                select(AssignmentInvite).where(AssignmentInvite.company_id == company.id)
            )
            assert invite_result.scalars().all() == []
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_resend_invite_failure_preserves_existing_active_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FailingEmailProvider()
    monkeypatch.setattr(
        "codrut.modules.communications.email_provider.build_email_provider",
        lambda _settings: provider,
    )

    await engine.dispose()
    try:
        async with SessionLocal() as session:
            trainer = User(
                id=uuid.uuid4(),
                email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("trainer-password-123"),
                role=UserRole.trainer,
            )
            company = Company(id=uuid.uuid4(), name="Resend Failure Company")
            session.add_all([trainer, company])
            await session.flush()
            session.add(
                CompanyMembership(
                    company_id=company.id,
                    user_id=trainer.id,
                    role=CompanyMembershipRole.owner,
                )
            )
            await session.flush()

            service = CompanyService(session)
            roster = await service.import_roster(
                trainer.id,
                company.id,
                RosterImportRequest(
                    rows=[
                        {
                            "Name": "Manager Ana",
                            "Reports To": "",
                            "Position": "Manager",
                            "Location": "Bucharest",
                            "email": "manager.ana@example.com",
                            "Profil PCM": "",
                        },
                    ]
                ),
            )
            participant = roster.participants[0]

            assignment_service = AssignmentService(session)
            plan = await assignment_service.build_default_assignment_plan(trainer.id, company.id)
            await assignment_service.save_assignment_plan(
                trainer.id,
                company.id,
                payload=AssignmentPlanSaveRequest(
                    assignments=[item.model_dump() for item in plan.assignments],
                ),
            )

            link_result = await service.send_participant_invites(
                trainer.id,
                company.id,
                ParticipantInviteBatchRequest(mode="secure_links"),
            )
            assert link_result.links_generated == 1

            invite_result = await session.execute(
                select(AssignmentInvite).where(AssignmentInvite.company_id == company.id)
            )
            existing_invite = invite_result.scalar_one()

            resend_result = await service.resend_invite(trainer.id, company.id, participant.id)

            assert resend_result.emails_sent == 0
            assert resend_result.emails_failed == 1
            assert provider.sent_messages

            invite_result = await session.execute(
                select(AssignmentInvite).where(AssignmentInvite.company_id == company.id)
            )
            invites = invite_result.scalars().all()
            assert len(invites) == 1
            assert invites[0].id == existing_invite.id
            assert invites[0].token == existing_invite.token
            assert invites[0].status == "active"

            await session.rollback()
    finally:
        await engine.dispose()


async def test_create_access_code_returns_plain_code_once_and_stores_hash() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    response = await service.create_access_code(
        owner_id,
        company.id,
        CompanyAccessCodeCreateRequest(label="June intake"),
    )

    assert response.code
    assert response.label == "June intake"
    assert hash_company_access_code(response.code) in repository.access_codes_by_hash


async def test_access_code_registration_is_disabled_for_public_profile_claims() -> None:
    repository = FakeCompanyRepository()
    identity_repository = FakeIdentityRepository()
    service = make_service(repository, identity_repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(full_name="Ana", email="ana@example.com"),
    )
    code = await service.create_access_code(
        owner_id,
        company.id,
        CompanyAccessCodeCreateRequest(label=None),
    )

    with pytest.raises(DomainError) as exc_info:
        await service.register_with_access_code(
            CompanyAccessCodeRegistrationRequest(
                email="ANA@example.com",
                access_code=code.code.lower(),
                **{"password": "Correct1!"},
            )
        )

    assert exc_info.value.code == "access_code_registration_disabled"
    assert repository.participants[0].user_id is None
    assert identity_repository.sessions == []


async def test_access_code_registration_uses_generic_error_for_invalid_match() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    code = await service.create_access_code(
        owner_id,
        company.id,
        CompanyAccessCodeCreateRequest(label=None),
    )

    with pytest.raises(DomainError, match="access-code registration is disabled"):
        await service.register_with_access_code(
            CompanyAccessCodeRegistrationRequest(
                email="missing@example.com",
                access_code=code.code,
                **{"password": "Correct1!"},
            )
        )


async def test_access_code_registration_rejects_invalid_code_generically() -> None:
    service = make_service(FakeCompanyRepository())

    with pytest.raises(DomainError, match="access-code registration is disabled"):
        await service.register_with_access_code(
            CompanyAccessCodeRegistrationRequest(
                email="missing@example.com",
                access_code="WRONG-CODE",
                **{"password": "Correct1!"},
            )
        )


async def test_access_code_registration_rejects_claimed_profile_generically() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    code = await service.create_access_code(
        owner_id,
        company.id,
        CompanyAccessCodeCreateRequest(label=None),
    )
    participant = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(full_name="Ana", email="ana@example.com"),
    )
    participant.user_id = uuid.uuid4()

    with pytest.raises(DomainError, match="access-code registration is disabled"):
        await service.register_with_access_code(
            CompanyAccessCodeRegistrationRequest(
                email="ana@example.com",
                access_code=code.code.replace("-", ""),
                **{"password": "Correct1!"},
            )
        )


def test_access_code_hash_ignores_case_spaces_and_hyphens() -> None:
    assert hash_company_access_code("ABCD-EFGH-IJKL") == hash_company_access_code("abcd efgh ijkl")


async def test_import_reporting_relationships_resolves_reports_to_names() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    manager = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(full_name="Maria Manager", email="maria@example.com"),
    )
    participant = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(
            full_name="Ana",
            email="ana@example.com",
            reports_to_name="MariaManager",
        ),
    )

    result = await service.import_reporting_relationships(owner_id, company.id)

    assert result.created_count == 1
    assert result.issues == []
    assert repository.reporting_relationships[0].participant_profile_id == participant.id
    assert repository.reporting_relationships[0].manager_profile_id == manager.id


async def test_import_reporting_relationships_ignores_top_level_reports_to_markers() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    participant = ParticipantProfile(
        company_id=company.id,
        full_name="Maria",
        email="maria@example.com",
        reports_to_name="radacina",
    )
    await repository.add_participant(participant)

    result = await service.import_reporting_relationships(owner_id, company.id)

    assert result.created_count == 0
    assert result.issues == []
    assert repository.reporting_relationships == []


async def test_import_reporting_relationships_returns_validation_issues() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(
            full_name="Ana",
            email="ana@example.com",
            reports_to_name="Missing",
        ),
    )
    await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(
            full_name="Maria",
            email="maria@example.com",
            reports_to_name="Maria",
        ),
    )

    result = await service.import_reporting_relationships(owner_id, company.id)

    assert result.created_count == 0
    assert {issue.code for issue in result.issues} == {"manager_not_found", "self_report"}
    assert repository.reporting_relationships == []
