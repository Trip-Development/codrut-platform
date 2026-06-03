import uuid
from typing import Any, cast

import pytest
from fastapi import HTTPException

from codrut.core.errors import DomainError
from codrut.modules.companies.models import (
    Company,
    CompanyAccessCode,
    CompanyMembership,
    ParticipantProfile,
    ParticipantReportingRelationship,
)
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.companies.schemas import (
    CompanyAccessCodeCreateRequest,
    CompanyAccessCodeRegistrationRequest,
    CompanyCreateRequest,
    ParticipantCreateRequest,
    RosterImportRequest,
)
from codrut.modules.companies.service import CompanyService, hash_company_access_code
from codrut.modules.identity.models import Session, User, UserRole
from codrut.modules.identity.schemas import SessionPrincipal


class FakeCompanyRepository:
    def __init__(self) -> None:
        self.companies_by_id: dict[uuid.UUID, Company] = {}
        self.companies_by_name: dict[str, Company] = {}
        self.access_codes_by_hash: dict[str, CompanyAccessCode] = {}
        self.memberships: list[CompanyMembership] = []
        self.participants: list[ParticipantProfile] = []
        self.reporting_relationships: list[ParticipantReportingRelationship] = []

    async def list_companies_for_user(self, user_id: uuid.UUID) -> list[Company]:
        company_ids = {
            membership.company_id
            for membership in self.memberships
            if membership.user_id == user_id
        }
        return [company for company in self.companies_by_name.values() if company.id in company_ids]

    async def get_company(self, company_id: uuid.UUID) -> Company | None:
        return self.companies_by_id.get(company_id)

    async def get_company_by_name(self, name: str) -> Company | None:
        return self.companies_by_name.get(name)

    async def add_company(self, company: Company) -> Company:
        company.id = uuid.uuid4()
        self.companies_by_id[company.id] = company
        self.companies_by_name[company.name] = company
        return company

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
            participant
            for participant in self.participants
            if participant.company_id == company_id
        ]

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

    async def get_user_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email.lower())

    async def add_user(self, user: User) -> User:
        user.id = uuid.uuid4()
        self.users_by_email[user.email] = user
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


async def test_list_companies_only_returns_user_memberships() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    first = await service.create_company(owner_id, CompanyCreateRequest(name="First"))
    await service.create_company(other_owner_id, CompanyCreateRequest(name="Second"))

    assert await service.list_companies(owner_id) == [first]


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


async def test_create_participant_rejects_trainer_without_company_membership() -> None:
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
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))

    participants = await service.import_roster(
        owner_id,
        company.id,
        RosterImportRequest(
            rows=[
                {
                    "Name": "  Ana Ionescu  ",
                    "Reports To": "Maria Popescu",
                    "Position": "Consultant",
                    "Location": "Bucharest",
                    "email": "ANA@example.com",
                    "Profil PCM": "",
                }
            ]
        ),
    )

    assert len(participants) == 1
    assert participants[0].full_name == "Ana Ionescu"
    assert participants[0].reports_to_name == "Maria Popescu"
    assert participants[0].email == "ana@example.com"
    assert participants[0].pcm_profile is None


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


async def test_access_code_registration_claims_roster_profile() -> None:
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

    result = await service.register_with_access_code(
        CompanyAccessCodeRegistrationRequest(
            email="ANA@example.com",
            access_code=code.code.lower(),
            **{"password": "correct horse battery"},
        )
    )

    assert result.response.email == "ana@example.com"
    assert result.response.role == UserRole.participant
    assert repository.participants[0].user_id == result.response.user_id
    assert any(
        membership.user_id == result.response.user_id
        for membership in repository.memberships
    )
    assert identity_repository.sessions


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

    with pytest.raises(DomainError, match="Invalid access code or email"):
        await service.register_with_access_code(
            CompanyAccessCodeRegistrationRequest(
                email="missing@example.com",
                access_code=code.code,
                **{"password": "correct horse battery"},
            )
        )


async def test_access_code_registration_rejects_invalid_code_generically() -> None:
    service = make_service(FakeCompanyRepository())

    with pytest.raises(DomainError, match="Invalid access code or email"):
        await service.register_with_access_code(
            CompanyAccessCodeRegistrationRequest(
                email="missing@example.com",
                access_code="WRONG-CODE",
                **{"password": "correct horse battery"},
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

    with pytest.raises(DomainError, match="Invalid access code or email"):
        await service.register_with_access_code(
            CompanyAccessCodeRegistrationRequest(
                email="ana@example.com",
                access_code=code.code.replace("-", ""),
                **{"password": "correct horse battery"},
            )
        )


def test_access_code_hash_ignores_case_spaces_and_hyphens() -> None:
    assert hash_company_access_code("ABCD-EFGH-IJKL") == hash_company_access_code(
        "abcd efgh ijkl"
    )


async def test_import_reporting_relationships_resolves_reports_to_names() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    manager = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(full_name="Maria", email="maria@example.com"),
    )
    participant = await service.create_participant(
        owner_id,
        company.id,
        ParticipantCreateRequest(
            full_name="Ana",
            email="ana@example.com",
            reports_to_name="maria",
        ),
    )

    result = await service.import_reporting_relationships(owner_id, company.id)

    assert result.created_count == 1
    assert result.issues == []
    assert repository.reporting_relationships[0].participant_profile_id == participant.id
    assert repository.reporting_relationships[0].manager_profile_id == manager.id


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
