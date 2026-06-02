import uuid
from typing import Any, cast

import pytest
from fastapi import HTTPException

from codrut.core.errors import DomainError
from codrut.modules.companies.models import Company, CompanyMembership, ParticipantProfile
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.companies.schemas import CompanyCreateRequest, ParticipantCreateRequest
from codrut.modules.companies.service import CompanyService
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


class FakeCompanyRepository:
    def __init__(self) -> None:
        self.companies_by_id: dict[uuid.UUID, Company] = {}
        self.companies_by_name: dict[str, Company] = {}
        self.memberships: list[CompanyMembership] = []
        self.participants: list[ParticipantProfile] = []

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


def make_service(repository: FakeCompanyRepository) -> CompanyService:
    service = CompanyService(cast(Any, None))
    service.repository = cast(Any, repository)
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
