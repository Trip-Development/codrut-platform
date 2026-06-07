import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.core.security import hash_password, new_session_token
from codrut.modules.companies.models import (
    Company,
    CompanyAccessCode,
    CompanyMembership,
    CompanyMembershipRole,
    ParticipantProfile,
    ParticipantReportingRelationship,
)
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.companies.schemas import (
    CompanyAccessCodeCreateRequest,
    CompanyAccessCodeRegistrationRequest,
    CompanyAccessCodeResponse,
    CompanyCreateRequest,
    ParticipantCreateRequest,
    ReportingRelationshipImportResponse,
    ReportingRelationshipIssue,
    RosterImportRequest,
    RosterImportRow,
)
from codrut.modules.identity.models import Session, User, UserRole
from codrut.modules.identity.repository import IdentityRepository, hash_session_token
from codrut.modules.identity.schemas import AuthResponse


@dataclass(frozen=True)
class CompanyAccessRegistrationResult:
    response: AuthResponse
    session_token: str


class CompanyService:
    def __init__(self, session: AsyncSession) -> None:
        self.identity_repository = IdentityRepository(session)
        self.repository = CompanyRepository(session)

    async def list_companies(self, user_id: UUID) -> list[Company]:
        return await self.repository.list_companies_for_user(user_id)

    async def create_company(self, owner_user_id: UUID, payload: CompanyCreateRequest) -> Company:
        name = payload.name.strip()
        existing = await self.repository.get_company_by_name(name)
        if existing is not None:
            raise DomainError("A company with this name already exists.", code="company_exists")
        company = await self.repository.add_company(Company(name=name))
        await self.repository.add_membership(
            CompanyMembership(
                company_id=company.id,
                user_id=owner_user_id,
                role=CompanyMembershipRole.owner,
            )
        )
        return company

    async def list_participants(self, user_id: UUID, company_id: UUID) -> list[ParticipantProfile]:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        return await self.repository.list_participants(company_id)

    async def create_participant(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: ParticipantCreateRequest,
    ) -> ParticipantProfile:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        email = payload.email.lower()
        existing = await self.repository.get_participant_by_company_email(company_id, email)
        if existing is not None:
            raise DomainError(
                "A participant with this email already exists for this company.",
                code="participant_exists",
            )
        return await self.repository.add_participant(
            ParticipantProfile(
                company_id=company_id,
                full_name=payload.full_name.strip(),
                email=email,
                reports_to_name=_clean_optional(payload.reports_to_name),
                position=_clean_optional(payload.position),
                location=_clean_optional(payload.location),
                role_group=_clean_optional(payload.role_group),
                pcm_profile=_clean_optional(payload.pcm_profile),
            )
        )

    async def import_roster(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: RosterImportRequest,
    ) -> list[ParticipantProfile]:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        rows = [_normalize_roster_row(row) for row in payload.rows]
        seen_emails: set[str] = set()
        for row in rows:
            if row.email in seen_emails:
                raise DomainError(
                    f"Duplicate roster email: {row.email}",
                    code="roster_duplicate_email",
                )
            seen_emails.add(row.email)
            existing = await self.repository.get_participant_by_company_email(company_id, row.email)
            if existing is not None:
                raise DomainError(
                    f"Participant already exists for this company: {row.email}",
                    code="participant_exists",
                )

        participants: list[ParticipantProfile] = []
        for row in rows:
            participants.append(
                await self.repository.add_participant(
                    ParticipantProfile(
                        company_id=company_id,
                        full_name=row.full_name,
                        email=row.email,
                        reports_to_name=row.reports_to_name,
                        position=row.position,
                        location=row.location,
                        role_group=None,
                        pcm_profile=row.pcm_profile,
                    )
                )
            )
        return participants

    async def create_access_code(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: CompanyAccessCodeCreateRequest,
    ) -> CompanyAccessCodeResponse:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        code = _new_access_code()
        access_code = await self.repository.add_access_code(
            CompanyAccessCode(
                company_id=company_id,
                code_hash=hash_company_access_code(code),
                label=_clean_optional(payload.label),
                active=True,
            )
        )
        return CompanyAccessCodeResponse(
            id=access_code.id,
            company_id=access_code.company_id,
            label=access_code.label,
            code=code,
        )

    async def register_with_access_code(
        self,
        payload: CompanyAccessCodeRegistrationRequest,
    ) -> CompanyAccessRegistrationResult:
        access_code = await self.repository.get_active_access_code(
            hash_company_access_code(payload.access_code)
        )
        if access_code is None:
            raise _invalid_registration()

        email = payload.email.lower()
        participant = await self.repository.get_unclaimed_participant_by_company_email(
            access_code.company_id,
            email,
        )
        existing_user = await self.identity_repository.get_user_by_email(email)
        if participant is None or existing_user is not None:
            raise _invalid_registration()

        user = await self.identity_repository.add_user(
            User(
                email=email,
                password_hash=hash_password(payload.password),
                role=UserRole.participant,
            )
        )
        await self.repository.add_membership(
            CompanyMembership(
                company_id=access_code.company_id,
                user_id=user.id,
                role=CompanyMembershipRole.participant,
            )
        )
        participant.user_id = user.id
        session_token = new_session_token()
        await self.identity_repository.add_session(
            Session(
                user_id=user.id,
                token_hash=hash_session_token(session_token),
                expires_at=datetime.now(UTC) + timedelta(days=14),
            )
        )
        return CompanyAccessRegistrationResult(
            response=AuthResponse(user_id=user.id, email=user.email, role=user.role),
            session_token=session_token,
        )

    async def import_reporting_relationships(
        self,
        user_id: UUID,
        company_id: UUID,
    ) -> ReportingRelationshipImportResponse:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        participants = await self.repository.list_participants(company_id)
        participants_by_name = {
            participant.full_name.strip().casefold(): participant
            for participant in participants
        }
        manager_by_participant: dict[UUID, ParticipantProfile] = {}
        issues: list[ReportingRelationshipIssue] = []

        for participant in participants:
            reports_to_name = _clean_optional(participant.reports_to_name)
            if reports_to_name is None:
                continue
            manager = participants_by_name.get(reports_to_name.casefold())
            if manager is None:
                issues.append(
                    _relationship_issue(
                        participant,
                        reports_to_name,
                        "manager_not_found",
                        "Manager was not found in this company roster.",
                    )
                )
                continue
            if manager.id == participant.id:
                issues.append(
                    _relationship_issue(
                        participant,
                        reports_to_name,
                        "self_report",
                        "Participant cannot report to themselves.",
                    )
                )
                continue
            manager_by_participant[participant.id] = manager

        issues.extend(_cycle_issues(participants, manager_by_participant))
        if issues:
            return ReportingRelationshipImportResponse(created_count=0, issues=issues)

        relationships = [
            ParticipantReportingRelationship(
                company_id=company_id,
                participant_profile_id=participant_id,
                manager_profile_id=manager.id,
            )
            for participant_id, manager in manager_by_participant.items()
        ]
        await self.repository.replace_reporting_relationships(company_id, relationships)
        return ReportingRelationshipImportResponse(created_count=len(relationships), issues=[])

    async def _require_company(self, company_id: UUID) -> Company:
        company = await self.repository.get_company(company_id)
        if company is None:
            raise DomainError("Company not found.", code="company_not_found")
        return company

    async def _require_company_manager(self, user_id: UUID, company_id: UUID) -> None:
        membership = await self.repository.get_membership(company_id, user_id)
        if membership is None or membership.role not in {
            CompanyMembershipRole.owner,
            CompanyMembershipRole.trainer,
        }:
            raise DomainError(
                "You do not have access to manage this company.",
                code="company_access_denied",
            )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_roster_row(row: RosterImportRow) -> RosterImportRow:
    return RosterImportRow(
        full_name=row.full_name.strip(),
        reports_to_name=_clean_optional(row.reports_to_name),
        position=_clean_optional(row.position),
        location=_clean_optional(row.location),
        email=row.email.lower(),
        pcm_profile=_clean_optional(row.pcm_profile),
    )


def _new_access_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "-".join(
        "".join(secrets.choice(alphabet) for _ in range(4))
        for _ in range(3)
    )


def hash_company_access_code(code: str) -> str:
    normalized = code.strip().upper().replace(" ", "").replace("-", "")
    return hashlib.sha256(normalized.encode()).hexdigest()


def _invalid_registration() -> DomainError:
    return DomainError(
        "Invalid access code or email.",
        code="invalid_company_access",
    )


def _relationship_issue(
    participant: ParticipantProfile,
    reports_to_name: str,
    code: str,
    message: str,
) -> ReportingRelationshipIssue:
    return ReportingRelationshipIssue(
        participant_id=participant.id,
        participant_name=participant.full_name,
        reports_to_name=reports_to_name,
        code=code,
        message=message,
    )


def _cycle_issues(
    participants: list[ParticipantProfile],
    manager_by_participant: dict[UUID, ParticipantProfile],
) -> list[ReportingRelationshipIssue]:
    participants_by_id = {participant.id: participant for participant in participants}
    issues: list[ReportingRelationshipIssue] = []
    cycle_participant_ids: set[UUID] = set()
    for participant in participants:
        seen: set[UUID] = set()
        current_id = participant.id
        while current_id in manager_by_participant:
            if current_id in seen:
                cycle_participant_ids.update(seen)
                break
            seen.add(current_id)
            current_id = manager_by_participant[current_id].id

    for participant_id in cycle_participant_ids:
        participant = participants_by_id[participant_id]
        reports_to_name = participant.reports_to_name or ""
        issues.append(
            _relationship_issue(
                participant,
                reports_to_name,
                "cycle_detected",
                "Reporting relationship creates a cycle.",
            )
        )
    return issues
