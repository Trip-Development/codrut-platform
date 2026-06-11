import hashlib
import secrets
import string
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.core.security import hash_password, new_session_token
from codrut.modules.companies.models import (
    Company,
    CompanyAccessCode,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    ParticipantProfile,
    ParticipantReportingRelationship,
)
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.companies.schemas import (
    CompanyAccessCodeCreateRequest,
    CompanyAccessCodeRegistrationRequest,
    CompanyAccessCodeResponse,
    CompanyCreateRequest,
    CompanyProjectCreateRequest,
    CompanyProjectListItemResponse,
    CompanyProjectUpdateRequest,
    CompanySummaryResponse,
    ParticipantCreateRequest,
    ParticipantInvitationStatusResponse,
    ParticipantInviteBatchRequest,
    ParticipantInviteBatchResponse,
    ReportingRelationshipImportResponse,
    ReportingRelationshipIssue,
    RosterImportEmailResult,
    RosterImportRequest,
    RosterImportResponse,
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

    async def list_all_companies(self) -> list[Company]:
        return await self.repository.list_all_companies()

    async def list_company_summaries(self) -> list[CompanySummaryResponse]:
        return [
            CompanySummaryResponse(
                id=company.id,
                name=company.name,
                participant_count=participant_count,
                project_count=project_count,
                assignment_count=assignment_count,
                completed_count=completed_count,
                scored_count=scored_count,
                stage=_derive_company_stage(assignment_count, completed_count),
            )
            for (
                company,
                participant_count,
                project_count,
                assignment_count,
                completed_count,
                scored_count,
            ) in await self.repository.list_company_summaries()
        ]

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

    async def delete_company(self, user_id: UUID, company_id: UUID) -> None:
        company = await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        await self.repository.delete_company(company)

    async def list_all_projects(self) -> list[CompanyProjectListItemResponse]:
        return [
            CompanyProjectListItemResponse(
                id=project.id,
                company_id=project.company_id,
                company_name=company_name,
                name=project.name,
                description=project.description,
                status=project.status,
                starts_at=project.starts_at,
                due_at=project.due_at,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
            for project, company_name in await self.repository.list_all_projects()
        ]

    async def list_projects(
        self,
        user_id: UUID,
        company_id: UUID,
    ) -> list[CompanyProject]:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        return await self.repository.list_projects(company_id)

    async def create_project(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: CompanyProjectCreateRequest,
    ) -> CompanyProject:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        name = payload.name.strip()
        existing = await self.repository.get_project_by_name(company_id, name)
        if existing is not None:
            raise DomainError(
                "A project with this name already exists for this company.",
                code="project_exists",
            )
        _validate_project_dates(payload.starts_at, payload.due_at)
        return await self.repository.add_project(
            CompanyProject(
                company_id=company_id,
                name=name,
                description=_clean_optional(payload.description),
                status=payload.status,
                starts_at=payload.starts_at,
                due_at=payload.due_at,
            )
        )

    async def update_project(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
        payload: CompanyProjectUpdateRequest,
    ) -> CompanyProject:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        project = await self.repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError("Project not found.", code="project_not_found")

        if "name" in payload.model_fields_set and payload.name is not None:
            name = payload.name.strip()
            existing = await self.repository.get_project_by_name(company_id, name)
            if existing is not None and existing.id != project.id:
                raise DomainError(
                    "A project with this name already exists for this company.",
                    code="project_exists",
                )
            project.name = name
        if "description" in payload.model_fields_set:
            project.description = _clean_optional(payload.description)
        if "status" in payload.model_fields_set and payload.status is not None:
            project.status = payload.status
        if "starts_at" in payload.model_fields_set:
            project.starts_at = payload.starts_at
        if "due_at" in payload.model_fields_set:
            project.due_at = payload.due_at

        _validate_project_dates(project.starts_at, project.due_at)
        await self.repository.session.flush()
        return project

    async def delete_project(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
    ) -> None:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        project = await self.repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError("Project not found.", code="project_not_found")
        await self.repository.delete_project(project)

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
                reports_to_name=_clean_reports_to_name(payload.reports_to_name),
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
    ) -> RosterImportResponse:
        company = await self._require_company(company_id)
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

        existing_emails = {
            participant.email.lower()
            for participant in await self.repository.list_participants(company_id)
        }
        duplicate_existing_email = next(
            (row.email for row in rows if row.email in existing_emails),
            None,
        )
        if duplicate_existing_email is not None:
            raise DomainError(
                f"Participant already exists for this company: {duplicate_existing_email}",
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
                        role_group=_infer_roster_role_group(row),
                        pcm_profile=row.pcm_profile,
                    )
                )
            )

        reporting_result = await self.import_reporting_relationships(user_id, company_id)
        if reporting_result.issues:
            first_issue = reporting_result.issues[0]
            raise DomainError(
                f"Roster reporting relationships are invalid: {first_issue.message}",
                code=first_issue.code,
            )

        from codrut.modules.assignments.models import (
            Team,
            TeamMembership,
            TeamMembershipRole,
            TeamType,
        )

        leadership_participants = [
            participant
            for participant in participants
            if participant.role_group == "leadership"
        ]
        if leadership_participants:
            leadership_team = await self.repository.get_team_by_company_name(
                company.id,
                "Leadership",
            )
            if leadership_team is None:
                leadership_team = Team(
                    company_id=company.id,
                    name="Leadership",
                    type=TeamType.leadership,
                )
                self.repository.session.add(leadership_team)
                await self.repository.session.flush()
            for participant in leadership_participants:
                self.repository.session.add(
                    TeamMembership(
                        team_id=leadership_team.id,
                        participant_profile_id=participant.id,
                        role=TeamMembershipRole.leader,
                    )
                )
            await self.repository.session.flush()

        if not payload.send_invites:
            return RosterImportResponse(
                participants=participants,
                email_results=[],
                total_imported=len(participants),
                emails_sent=0,
                emails_failed=0,
            )

        invite_result = await self._dispatch_participant_invites(
            user_id=user_id,
            company=company,
            participants=participants,
            mode="email",
            force_rotate=True,
        )
        return RosterImportResponse(
            participants=participants,
            email_results=invite_result.results,
            total_imported=len(participants),
            emails_sent=invite_result.emails_sent,
            emails_failed=invite_result.emails_failed,
        )

    async def send_participant_invites(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: ParticipantInviteBatchRequest,
    ) -> ParticipantInviteBatchResponse:
        company = await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        participants = await self.repository.list_participants(company_id)

        if payload.participant_ids is not None:
            requested_ids = set(payload.participant_ids)
            participants = [
                participant for participant in participants if participant.id in requested_ids
            ]
            found_ids = {participant.id for participant in participants}
            missing_ids = requested_ids - found_ids
            if missing_ids:
                raise DomainError(
                    "One or more participants were not found in this company.",
                    code="participant_not_found",
                )

        if not participants:
            raise DomainError("No participants found for invite delivery.", code="no_participants")

        return await self._dispatch_participant_invites(
            user_id=user_id,
            company=company,
            participants=participants,
            mode=payload.mode,
            force_rotate=payload.force_rotate,
        )

    async def _dispatch_participant_invites(
        self,
        *,
        user_id: UUID,
        company: Company,
        participants: list[ParticipantProfile],
        mode: Literal["email", "secure_links"],
        force_rotate: bool,
    ) -> ParticipantInviteBatchResponse:
        from codrut.core.config import get_settings
        from codrut.modules.assignments.models import AssignmentStatus
        from codrut.modules.communications.email_provider import build_email_provider
        from codrut.modules.communications.service import (
            AssignmentInvitationContext,
            TransactionalEmailService,
        )
        from codrut.modules.communications.task_links import build_task_url
        from codrut.modules.identity.service import IdentityService

        trainer = await self.identity_repository.get_user_by_id(user_id)
        trainer_name = trainer.email.split("@", 1)[0] if trainer is not None else "trainer"
        settings = get_settings()
        email_service = (
            TransactionalEmailService(build_email_provider(settings), self.repository.session)
            if mode == "email"
            else None
        )
        identity_service = IdentityService(self.repository.session)

        results: list[RosterImportEmailResult] = []
        for participant in participants:
            assignments = await self._list_active_assignments_for_participant(
                company.id,
                participant,
            )
            if not assignments:
                raise DomainError(
                    f"No assignments found for participant: {participant.email}",
                    code="no_assignments",
                )

            invite = await identity_service.create_invite(
                company_id=company.id,
                respondent_profile_id=participant.id,
                assignment_ids=[assignment.id for assignment in assignments],
                force_rotate=force_rotate,
            )
            invite_url = build_task_url(invite.token, settings)

            if mode == "secure_links":
                now = datetime.now(UTC)
                for assignment in assignments:
                    if assignment.status == AssignmentStatus.assigned:
                        assignment.status = AssignmentStatus.invited
                    assignment.invited_at = assignment.invited_at or now
                results.append(
                    RosterImportEmailResult(
                        participant_id=participant.id,
                        email=participant.email,
                        full_name=participant.full_name,
                        delivery_mode="secure_links",
                        email_sent=False,
                        invite_url=invite_url,
                    )
                )
                continue

            send_error: str | None = None
            try:
                assert email_service is not None
                result = await email_service.send_assignment_invitation(
                    assignments[0],
                    participant,
                    AssignmentInvitationContext(
                        company_name=company.name,
                        trainer_name=trainer_name,
                        action_url=invite_url,
                        task_count=len(assignments),
                    ),
                )
                if result.status == "accepted":
                    now = datetime.now(UTC)
                    for assignment in assignments:
                        assignment.status = AssignmentStatus.invited
                        assignment.invited_at = now
                else:
                    send_error = result.error_details or "Email provider rejected the message."
            except Exception as exc:  # noqa: BLE001
                send_error = str(exc)

            results.append(
                RosterImportEmailResult(
                    participant_id=participant.id,
                    email=participant.email,
                    full_name=participant.full_name,
                    delivery_mode="email",
                    email_sent=send_error is None,
                    error=send_error,
                    invite_url=invite_url,
                )
            )

        emails_sent = sum(1 for result in results if result.email_sent)
        links_generated = sum(1 for result in results if result.delivery_mode == "secure_links")
        return ParticipantInviteBatchResponse(
            results=results,
            total=len(results),
            emails_sent=emails_sent,
            emails_failed=sum(
                1
                for result in results
                if result.delivery_mode == "email" and not result.email_sent
            ),
            links_generated=links_generated,
        )

    async def list_participant_invitation_statuses(
        self,
        user_id: UUID,
        company_id: UUID,
    ) -> list[ParticipantInvitationStatusResponse]:
        from sqlalchemy import select

        from codrut.core.config import get_settings
        from codrut.modules.assignments.models import QuestionnaireAssignment
        from codrut.modules.communications.models import EmailSend
        from codrut.modules.communications.task_links import build_task_url
        from codrut.modules.identity.models import AssignmentInvite

        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)

        participants = await self.repository.list_participants(company_id)
        if not participants:
            return []

        participant_ids = {participant.id for participant in participants}

        sends_result = await self.repository.session.execute(
            select(EmailSend, QuestionnaireAssignment.respondent_profile_id)
            .join(QuestionnaireAssignment, EmailSend.assignment_id == QuestionnaireAssignment.id)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.respondent_profile_id.in_(participant_ids))
            .order_by(EmailSend.created_at.desc())
        )

        latest_send_by_participant: dict[UUID, EmailSend] = {}
        send_count_by_participant: dict[UUID, int] = {}
        for send, participant_id in sends_result.all():
            send_count_by_participant[participant_id] = (
                send_count_by_participant.get(participant_id, 0) + 1
            )
            latest_send_by_participant.setdefault(participant_id, send)

        now = datetime.now(UTC)
        invites_result = await self.repository.session.execute(
            select(AssignmentInvite)
            .where(AssignmentInvite.company_id == company_id)
            .where(AssignmentInvite.respondent_profile_id.in_(participant_ids))
            .where(AssignmentInvite.status == "active")
            .where(AssignmentInvite.expires_at > now)
            .order_by(AssignmentInvite.created_at.desc())
        )

        latest_invite_by_participant: dict[UUID, AssignmentInvite] = {}
        for invite in invites_result.scalars().all():
            latest_invite_by_participant.setdefault(invite.respondent_profile_id, invite)

        statuses: list[ParticipantInvitationStatusResponse] = []
        settings = get_settings()
        for participant in participants:
            latest_send = latest_send_by_participant.get(participant.id)
            active_invite = latest_invite_by_participant.get(participant.id)
            latest_delivery_mode: Literal["email", "secure_links"] | None = None
            if latest_send is not None and (
                active_invite is None or latest_send.created_at >= active_invite.created_at
            ):
                latest_delivery_mode = "email"
            elif active_invite is not None:
                latest_delivery_mode = "secure_links"

            statuses.append(
                ParticipantInvitationStatusResponse(
                    participant_id=participant.id,
                    latest_delivery_mode=latest_delivery_mode,
                    latest_email_status=latest_send.status.value
                    if latest_send is not None
                    else None,
                    latest_email_error=latest_send.error_details
                    if latest_send is not None
                    else None,
                    last_sent_at=latest_send.created_at if latest_send is not None else None,
                    email_send_count=send_count_by_participant.get(participant.id, 0),
                    has_active_secure_link=active_invite is not None,
                    active_secure_link_expires_at=active_invite.expires_at
                    if active_invite is not None
                    else None,
                    active_secure_link_url=build_task_url(active_invite.token, settings)
                    if active_invite is not None
                    else None,
                )
            )

        return statuses

    async def _list_active_assignments_for_participant(
        self,
        company_id: UUID,
        participant: ParticipantProfile,
    ) -> list:
        from codrut.modules.assignments.models import AssignmentStatus

        assignments = await self.repository.list_assignments_for_participant(participant.id)
        active_statuses = {
            AssignmentStatus.assigned,
            AssignmentStatus.invited,
            AssignmentStatus.started,
        }
        return [
            assignment
            for assignment in assignments
            if assignment.company_id == company_id and assignment.status in active_statuses
        ]

    async def resend_invite(
        self,
        user_id: UUID,
        company_id: UUID,
        participant_id: UUID,
    ) -> RosterImportResponse:
        company = await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)

        participant = await self.repository.get_participant_by_id(participant_id)
        if participant is None or participant.company_id != company_id:
            raise DomainError("Participant not found.", code="participant_not_found")

        result = await self._dispatch_participant_invites(
            user_id=user_id,
            company=company,
            participants=[participant],
            mode="email",
            force_rotate=False,
        )
        return RosterImportResponse(
            participants=[participant],
            email_results=result.results,
            total_imported=1,
            emails_sent=result.emails_sent,
            emails_failed=result.emails_failed,
        )

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
            reports_to_name = _clean_reports_to_name(participant.reports_to_name)
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
        if membership is not None and membership.role in {
            CompanyMembershipRole.owner,
            CompanyMembershipRole.trainer,
        }:
            return

        user = await self.identity_repository.get_user_by_id(user_id)
        if user is not None and user.role == UserRole.trainer:
            return

        raise DomainError(
            "You do not have access to manage this company.",
            code="company_access_denied",
        )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_project_dates(starts_at: datetime | None, due_at: datetime | None) -> None:
    if starts_at is not None and due_at is not None and due_at < starts_at:
        raise DomainError(
            "Project due date cannot be before its start date.",
            code="invalid_project_dates",
        )


_TOP_LEVEL_REPORTS_TO_VALUES = {
    "radacina",
    "root",
    "top",
    "top level",
    "nivel superior",
    "fara manager",
    "fara sef",
    "none",
    "n/a",
    "na",
    "-",
    "—",
}


def _clean_reports_to_name(value: str | None) -> str | None:
    cleaned = _clean_optional(value)
    if cleaned is None:
        return None
    normalized = _normalize_reports_to_token(cleaned)
    return None if normalized in _TOP_LEVEL_REPORTS_TO_VALUES else cleaned


def _normalize_reports_to_token(value: str) -> str:
    without_diacritics = "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_diacritics.casefold().split())


def _normalize_roster_row(row: RosterImportRow) -> RosterImportRow:
    return RosterImportRow(
        full_name=row.full_name.strip(),
        reports_to_name=_clean_reports_to_name(row.reports_to_name),
        position=_clean_optional(row.position),
        location=_clean_optional(row.location),
        email=row.email.lower(),
        pcm_profile=_clean_optional(row.pcm_profile),
    )


def _infer_roster_role_group(row: RosterImportRow) -> str:
    position = (row.position or "").casefold()
    if row.reports_to_name is None:
        return "leadership"
    if any(token in position for token in ("manager", "director", "lead")):
        return "leadership"
    return "member"


def _derive_company_stage(
    assignment_count: int,
    completed_count: int,
) -> Literal["setup", "invites", "completion", "reporting"]:
    if assignment_count == 0:
        return "setup"
    if completed_count == assignment_count:
        return "reporting"
    if completed_count > 0:
        return "completion"
    return "invites"


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
