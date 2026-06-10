import uuid
from typing import Any, cast

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssignmentStatus,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
    TeamType,
)
from codrut.modules.communications.email_provider import LocalEmailProvider
from codrut.modules.companies.models import (
    Company,
    CompanyAccessCode,
    CompanyMembership,
    CompanyMembershipRole,
    ParticipantProfile,
    ParticipantReportingRelationship,
)
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.companies.schemas import (
    CompanyAccessCodeCreateRequest,
    CompanyAccessCodeRegistrationRequest,
    CompanyCreateRequest,
    ParticipantCreateRequest,
    ParticipantInviteBatchRequest,
    RosterImportRequest,
)
from codrut.modules.companies.service import CompanyService, hash_company_access_code
from codrut.modules.identity.models import AssignmentInvite, Session, User, UserRole
from codrut.modules.identity.schemas import RegisterRequest, SessionPrincipal
from codrut.modules.identity.service import IdentityService


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


async def test_list_companies_only_returns_user_memberships() -> None:
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    first = await service.create_company(owner_id, CompanyCreateRequest(name="First"))
    await service.create_company(other_owner_id, CompanyCreateRequest(name="Second"))

    assert await service.list_companies(owner_id) == [first]


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

    await service.delete_company(owner_id, company.id)

    assert await repository.get_company(company.id) is None
    assert repository.memberships == []
    assert repository.participants == []


async def test_trainer_can_delete_any_company_without_membership() -> None:
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


async def test_create_participant_allows_trainer_without_company_membership() -> None:
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

    assert participant.email == "ana@example.com"


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
                    "Reports To": "",
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
    assert participants[0].role_group == "leadership"
    assert participants[1].full_name == "Ana Ionescu"
    assert participants[1].reports_to_name == "Maria Popescu"
    assert participants[1].email == "ana@example.com"
    assert participants[1].pcm_profile is None


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
        assert len(assignments) == 6
        assert {assignment.status for assignment in assignments} == {AssignmentStatus.assigned}

        invite_result = await session.execute(
            select(AssignmentInvite).where(AssignmentInvite.company_id == company.id)
        )
        assert invite_result.scalars().all() == []

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
        assert (
            sum("Activeaza contul" in message.html_body for message in provider.sent_messages) == 2
        )
        assert (
            sum(
                "Deschide sarcinile mele" in message.html_body for message in provider.sent_messages
            )
            == 1
        )

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
        assert len(verify_manager.tasks) == 2

        registration_token = next(
            invite.token for invite in invites if invite.respondent_profile_id == participants[0].id
        )
        registration_password = "".join(["Satinmint3!", "23"])
        register_result = await identity_service.register(
            RegisterRequest(
                email=participants[0].email,
                password=registration_password,
                token=registration_token,
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
        membership.user_id == result.response.user_id for membership in repository.memberships
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
    assert hash_company_access_code("ABCD-EFGH-IJKL") == hash_company_access_code("abcd efgh ijkl")


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
