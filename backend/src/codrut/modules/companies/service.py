import hashlib
import logging
import secrets
import string
from datetime import UTC, datetime
from typing import Literal, NoReturn
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.companies.anonymous import new_anonymous_name
from codrut.modules.companies.manager_matching import (
    clean_manager_reference,
    manager_reference_key,
)
from codrut.modules.companies.models import (
    Company,
    CompanyAccessCode,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    ParticipantProfile,
    ParticipantReportingRelationship,
    ProjectMembership,
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
    ParticipantUpdateRequest,
    ProjectParticipantResponse,
    ReportingRelationshipImportResponse,
    ReportingRelationshipIssue,
    RosterImportEmailResult,
    RosterImportRequest,
    RosterImportResponse,
    RosterImportRow,
)
from codrut.modules.identity.repository import IdentityRepository

logger = logging.getLogger(__name__)


class CompanyService:
    def __init__(self, session: AsyncSession) -> None:
        self.identity_repository = IdentityRepository(session)
        self.repository = CompanyRepository(session)

    async def list_companies(self, user_id: UUID) -> list[Company]:
        return await self.repository.list_companies_for_user(user_id)

    async def list_all_companies(self) -> list[Company]:
        return await self.repository.list_all_companies()

    async def list_company_summaries(
        self,
        user_id: UUID | None = None,
    ) -> list[CompanySummaryResponse]:
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
            ) in await self.repository.list_company_summaries(user_id)
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

    async def list_all_projects(
        self,
        user_id: UUID | None = None,
    ) -> list[CompanyProjectListItemResponse]:
        return [
            CompanyProjectListItemResponse(
                id=project.id,
                company_id=project.company_id,
                company_name=company_name,
                name=project.name,
                description=project.description,
                project_type=project.project_type,
                status=project.status,
                starts_at=project.starts_at,
                due_at=project.due_at,
                form_opens_at=project.form_opens_at,
                form_closes_at=project.form_closes_at,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
            for project, company_name in await self.repository.list_projects_with_company(
                user_id=user_id
            )
        ]

    async def get_project_by_id(
        self,
        project_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> CompanyProjectListItemResponse:
        result = await self.repository.get_project_by_id(project_id, user_id=user_id)
        if result is None:
            raise DomainError("Project not found.", code="project_not_found")
        project, company_name = result
        return CompanyProjectListItemResponse(
            id=project.id,
            company_id=project.company_id,
            company_name=company_name,
            name=project.name,
            description=project.description,
            project_type=project.project_type,
            status=project.status,
            starts_at=project.starts_at,
            due_at=project.due_at,
            form_opens_at=project.form_opens_at,
            form_closes_at=project.form_closes_at,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

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
        _validate_date_window(payload.starts_at, payload.due_at, "invalid_project_dates")
        _validate_date_window(
            payload.form_opens_at,
            payload.form_closes_at,
            "invalid_form_window",
        )
        return await self.repository.add_project(
            CompanyProject(
                company_id=company_id,
                name=name,
                description=_clean_optional(payload.description),
                project_type=_clean_optional(payload.project_type),
                status=payload.status,
                starts_at=payload.starts_at,
                due_at=payload.due_at,
                form_opens_at=payload.form_opens_at,
                form_closes_at=payload.form_closes_at,
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
        if "project_type" in payload.model_fields_set:
            project.project_type = _clean_optional(payload.project_type)
        if "status" in payload.model_fields_set and payload.status is not None:
            project.status = payload.status
        if "starts_at" in payload.model_fields_set:
            project.starts_at = payload.starts_at
        if "due_at" in payload.model_fields_set:
            project.due_at = payload.due_at
        if "form_opens_at" in payload.model_fields_set:
            project.form_opens_at = payload.form_opens_at
        if "form_closes_at" in payload.model_fields_set:
            project.form_closes_at = payload.form_closes_at

        _validate_date_window(project.starts_at, project.due_at, "invalid_project_dates")
        _validate_date_window(project.form_opens_at, project.form_closes_at, "invalid_form_window")
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
        participants = await self.repository.list_participants(company_id)
        await self._ensure_anonymous_names(participants)
        return participants

    async def list_project_participants(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
    ) -> list[ProjectParticipantResponse]:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, project_id)
        memberships = await self.repository.list_project_memberships(company_id, project_id)
        participants = [participant for _membership, participant in memberships]
        await self._ensure_anonymous_names(participants)
        return [
            _project_participant_response(membership, participant)
            for membership, participant in memberships
        ]

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
        participant = await self.repository.add_participant(
            ParticipantProfile(
                company_id=company_id,
                full_name=payload.full_name.strip(),
                email=email,
                reports_to_name=clean_manager_reference(payload.reports_to_name),
                position=_clean_optional(payload.position),
                location=_clean_optional(payload.location),
                role_group=_normalize_role_group(payload.role_group),
                pcm_profile=_clean_optional(payload.pcm_profile),
                pcm_base=_clean_optional(payload.pcm_base),
                pcm_phase=_clean_optional(payload.pcm_phase),
                anonymous_name=new_anonymous_name(),
            )
        )
        await self._sync_leadership_team_membership(company_id, participant)
        return participant

    async def update_participant(
        self,
        user_id: UUID,
        company_id: UUID,
        participant_id: UUID,
        payload: ParticipantUpdateRequest,
    ) -> ParticipantProfile:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        participant = await self.repository.get_participant(company_id, participant_id)
        if participant is None:
            raise DomainError("Participant not found.", code="participant_not_found")

        if payload.project_id is not None:
            await self._require_company_project(company_id, payload.project_id)

        fields_set = payload.model_fields_set
        if "email" in fields_set and payload.email is not None:
            email = payload.email.lower()
            email_changed = participant.email is None or email != participant.email.lower()
            if participant.user_id is not None and email_changed:
                raise DomainError(
                    "Claimed participant account email cannot be changed by a trainer.",
                    code="participant_email_claimed",
                )
            existing = await self.repository.get_participant_by_company_email(company_id, email)
            if existing is not None and existing.id != participant.id:
                raise DomainError(
                    "A participant with this email already exists for this company.",
                    code="participant_exists",
                )
            participant.email = email

        if "full_name" in fields_set and payload.full_name is not None:
            full_name = payload.full_name.strip()
            if not full_name:
                raise DomainError(
                    "Participant name cannot be empty.",
                    code="participant_name_required",
                )
            participant.full_name = full_name
        if "reports_to_name" in fields_set:
            participant.reports_to_name = clean_manager_reference(payload.reports_to_name)
        if "position" in fields_set:
            participant.position = _clean_optional(payload.position)
        if "location" in fields_set:
            participant.location = _clean_optional(payload.location)
        if "role_group" in fields_set:
            participant.role_group = _normalize_role_group(payload.role_group)

        if payload.project_id is not None:
            membership = await self.repository.get_project_membership(
                payload.project_id,
                participant.id,
            )
            if membership is None or membership.company_id != company_id:
                raise DomainError(
                    "Participant is not a member of this project.",
                    code="project_membership_not_found",
                )
            if "reports_to_name" in fields_set:
                membership.reports_to_name = participant.reports_to_name
            if "position" in fields_set:
                membership.position = participant.position
            if "location" in fields_set:
                membership.location = participant.location
            if "role_group" in fields_set:
                membership.role_group = participant.role_group

        if "role_group" in fields_set:
            await self._sync_leadership_team_membership(company_id, participant)

        return participant

    async def import_roster(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: RosterImportRequest,
        *,
        idempotency_key: str | None = None,
    ) -> RosterImportResponse:
        company = await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, payload.project_id)
        rows = [_normalize_roster_row(row) for row in payload.rows]
        manager_names = {
            manager_key
            for row in rows
            if row.reports_to_name is not None
            for manager_key in (manager_reference_key(row.reports_to_name),)
            if manager_key
        }
        seen_emails: set[str] = set()
        for row in rows:
            if row.email is None:
                continue
            if row.email in seen_emails:
                raise DomainError(
                    f"Duplicate roster email: {row.email}",
                    code="roster_duplicate_email",
                )
            seen_emails.add(row.email)

        participants: list[ParticipantProfile] = []
        for row in rows:
            participant = (
                await self.repository.get_participant_by_company_email(
                    company_id,
                    row.email,
                )
                if row.email is not None
                else await self.repository.get_unemailed_participant_by_roster_identity(
                    company_id,
                    full_name=row.full_name,
                    reports_to_name=row.reports_to_name,
                    position=row.position,
                    location=row.location,
                )
            )
            if participant is None:
                participant = await self.repository.add_participant(
                    ParticipantProfile(
                        company_id=company_id,
                        full_name=row.full_name,
                        email=row.email,
                        reports_to_name=row.reports_to_name,
                        position=row.position,
                        location=row.location,
                        role_group=_infer_roster_role_group(row, manager_names),
                        pcm_profile=row.pcm_profile or row.pcm_base,
                        pcm_base=row.pcm_base,
                        pcm_phase=row.pcm_phase,
                        anonymous_name=new_anonymous_name(),
                    )
                )
            elif not participant.anonymous_name:
                participant.anonymous_name = new_anonymous_name()

            if payload.project_id is not None:
                await self._upsert_project_membership(
                    company_id,
                    payload.project_id,
                    participant,
                    row,
                    manager_names,
                )
            participants.append(participant)

        if payload.project_id is None:
            reporting_result = await self.import_reporting_relationships(user_id, company_id)
            if reporting_result.issues:
                first_issue = reporting_result.issues[0]
                raise DomainError(
                    f"Roster reporting relationships are invalid: {first_issue.message}",
                    code=first_issue.code,
                )

        for participant in participants:
            await self._sync_leadership_team_membership(company.id, participant)

        if not payload.send_invites:
            return RosterImportResponse(
                participants=participants,
                email_results=[],
                total_imported=len(participants),
                emails_sent=0,
                emails_failed=0,
            )

        invite_participants = await self._filter_participants_without_accepted_email(
            company.id,
            participants,
            payload.project_id,
        )
        if not invite_participants:
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
            participants=invite_participants,
            project_id=payload.project_id,
            mode="email",
            force_rotate=False,
            idempotency_key=idempotency_key,
        )
        return RosterImportResponse(
            participants=participants,
            email_results=invite_result.results,
            total_imported=len(participants),
            emails_sent=invite_result.emails_sent,
            emails_queued=invite_result.emails_queued,
            emails_failed=invite_result.emails_failed,
        )

    async def send_participant_invites(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: ParticipantInviteBatchRequest,
        *,
        idempotency_key: str | None = None,
    ) -> ParticipantInviteBatchResponse:
        company = await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, payload.project_id)
        participants = await self.repository.list_participants(company_id)
        if payload.project_id is not None:
            project_memberships = await self.repository.list_project_memberships(
                company_id,
                payload.project_id,
            )
            project_participant_ids = {
                participant.id for _membership, participant in project_memberships
            }
            participants = [
                participant
                for participant in participants
                if participant.id in project_participant_ids
            ]

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

        had_invite_candidates = bool(participants)
        if payload.mode == "email" and payload.target_mode == "unsent":
            participants = await self._filter_participants_without_accepted_email(
                company.id,
                participants,
                payload.project_id,
            )
            if not participants and had_invite_candidates:
                return ParticipantInviteBatchResponse(
                    results=[],
                    total=0,
                    emails_sent=0,
                    emails_failed=0,
                    links_generated=0,
                )

        if not participants:
            raise DomainError("No participants found for invite delivery.", code="no_participants")

        return await self._dispatch_participant_invites(
            user_id=user_id,
            company=company,
            participants=participants,
            project_id=payload.project_id,
            mode=payload.mode,
            force_rotate=payload.force_rotate,
            idempotency_key=idempotency_key,
        )

    async def _ensure_anonymous_names(self, participants: list[ParticipantProfile]) -> None:
        changed = False
        for participant in participants:
            if participant.anonymous_name:
                continue
            participant.anonymous_name = new_anonymous_name()
            changed = True
        if changed:
            await self.repository.session.flush()

    async def _sync_leadership_team_membership(
        self,
        company_id: UUID,
        participant: ParticipantProfile,
    ) -> None:
        from codrut.modules.assignments.models import (
            Team,
            TeamMembership,
            TeamMembershipRole,
            TeamType,
        )

        should_be_leadership = _is_leadership_role(participant.role_group)
        if not should_be_leadership:
            memberships = await self.repository.list_project_memberships_for_participant(
                company_id,
                participant.id,
            )
            should_be_leadership = any(
                _is_leadership_role(membership.role_group) for membership in memberships
            )

        leadership_team = await self.repository.get_team_by_company_name(
            company_id,
            "Leadership",
        )
        if not should_be_leadership and leadership_team is None:
            return

        if leadership_team is None:
            leadership_team = Team(
                company_id=company_id,
                name="Leadership",
                type=TeamType.leadership,
            )
            self.repository.session.add(leadership_team)
            await self.repository.session.flush()

        existing_membership = next(
            (
                membership
                for membership in await self.repository.list_team_memberships_by_team(
                    leadership_team.id
                )
                if membership.participant_profile_id == participant.id
            ),
            None,
        )
        if should_be_leadership:
            if existing_membership is not None:
                existing_membership.role = TeamMembershipRole.leader
            else:
                self.repository.session.add(
                    TeamMembership(
                        team_id=leadership_team.id,
                        participant_profile_id=participant.id,
                        role=TeamMembershipRole.leader,
                    )
                )
            await self.repository.session.flush()
            return

        if existing_membership is not None:
            await self.repository.session.delete(existing_membership)
            await self.repository.session.flush()

    async def _upsert_project_membership(
        self,
        company_id: UUID,
        project_id: UUID,
        participant: ParticipantProfile,
        row: RosterImportRow,
        manager_names: set[str],
    ) -> ProjectMembership:
        membership = await self.repository.get_project_membership(project_id, participant.id)
        if membership is None:
            membership = await self.repository.add_project_membership(
                ProjectMembership(
                    company_id=company_id,
                    project_id=project_id,
                    participant_profile_id=participant.id,
                    reports_to_name=row.reports_to_name,
                    position=row.position,
                    location=row.location,
                    role_group=_infer_roster_role_group(row, manager_names),
                    active=True,
                )
            )
        else:
            membership.reports_to_name = row.reports_to_name
            membership.position = row.position
            membership.location = row.location
            membership.role_group = _infer_roster_role_group(row, manager_names)
            membership.active = True
            await self.repository.session.flush()
        return membership

    async def _dispatch_participant_invites(
        self,
        *,
        user_id: UUID,
        company: Company,
        participants: list[ParticipantProfile],
        project_id: UUID | None,
        mode: Literal["email", "secure_links"],
        force_rotate: bool,
        idempotency_key: str | None = None,
    ) -> ParticipantInviteBatchResponse:
        from codrut.core.config import get_settings
        from codrut.modules.assignments.models import AssignmentStatus
        from codrut.modules.communications.email_provider import build_email_provider
        from codrut.modules.communications.reminders import reminder_candidates
        from codrut.modules.communications.repository import CommunicationsRepository
        from codrut.modules.communications.service import (
            AssignmentInvitationContext,
            TransactionalEmailService,
            _remaining_email_sends_today,
        )
        from codrut.modules.communications.task_links import build_task_url
        from codrut.modules.identity.service import IdentityService

        trainer = await self.identity_repository.get_user_by_id(user_id)
        trainer_name = trainer.email.split("@", 1)[0] if trainer is not None else "trainer"
        settings = get_settings()
        email_service = (
            TransactionalEmailService(
                build_email_provider(settings),
                self.repository.session,
                owner_id=user_id,
            )
            if mode == "email"
            else None
        )
        identity_service = IdentityService(self.repository.session)
        communications_repository = CommunicationsRepository(self.repository.session)
        project = (
            await self.repository.get_project(company.id, project_id)
            if project_id is not None
            else None
        )
        invite_expires_at = _project_invite_expires_at(project)
        active_assignments_by_participant = await self._list_active_assignments_for_participants(
            company.id,
            participants,
            project_id,
        )
        active_assignment_ids = {
            assignment.id
            for assignments in active_assignments_by_participant.values()
            for assignment in assignments
        }
        successfully_delivered_assignment_ids = (
            await communications_repository.list_successfully_delivered_assignment_ids(
                active_assignment_ids
            )
            if mode == "email"
            else set()
        )

        results: list[RosterImportEmailResult] = []
        has_sendable_email = any(participant.email is not None for participant in participants)
        remaining_sends = (
            await _remaining_email_sends_today(communications_repository, settings)
            if mode == "email" and has_sendable_email
            else 0
        )
        for participant in participants:
            if participant.email is None:
                results.append(
                    RosterImportEmailResult(
                        participant_id=participant.id,
                        email=None,
                        full_name=participant.full_name,
                        delivery_mode=mode,
                        email_sent=False,
                        error_code="participant_email_missing",
                        error="Participantul nu are un email valid pentru invitații.",
                        invite_url=None,
                    )
                )
                continue

            assignments = active_assignments_by_participant.get(participant.id, [])
            if not assignments:
                results.append(
                    RosterImportEmailResult(
                        participant_id=participant.id,
                        email=participant.email,
                        full_name=participant.full_name,
                        delivery_mode=mode,
                        email_sent=False,
                        error_code="no_assignments",
                        error="Participantul nu are sarcini active pentru acest proiect.",
                        invite_url=None,
                    )
                )
                continue

            invite_url: str | None = None
            send_error: str | None = None
            send_error_code: str | None = None
            delivery_status: str | None = None
            try:
                async with self.repository.session.begin_nested():
                    invite = await identity_service.create_invite(
                        company_id=company.id,
                        respondent_profile_id=participant.id,
                        assignment_ids=[assignment.id for assignment in assignments],
                        project_id=project_id,
                        expires_at=invite_expires_at,
                        force_rotate=force_rotate,
                    )
                    invite_url = build_task_url(invite.token, settings)

                    if mode == "secure_links":
                        now = datetime.now(UTC)
                        for assignment in assignments:
                            if assignment.status == AssignmentStatus.assigned:
                                assignment.status = AssignmentStatus.invited
                            assignment.invited_at = assignment.invited_at or now
                    elif remaining_sends <= 0:
                        send_error_code = "daily_send_cap_reached"
                        send_error = "Limita zilnică de emailuri a fost atinsă."
                    else:
                        assert email_service is not None
                        reminder_assignment_ids = [
                            assignment.id for assignment in reminder_candidates(assignments)
                        ]
                        has_prior_delivery = any(
                            assignment.id in successfully_delivered_assignment_ids
                            for assignment in assignments
                        )
                        if has_prior_delivery and not reminder_assignment_ids:
                            raise DomainError(
                                "Reminderul nu este încă disponibil sau cele două runde au fost "
                                "trimise.",
                                code="reminder_not_due",
                            )
                        result = await email_service.send_assignment_invitation(
                            assignments[0],
                            participant,
                            AssignmentInvitationContext(
                                company_name=company.name,
                                trainer_name=trainer_name,
                                action_url=invite_url,
                                task_count=len(assignments),
                            ),
                            idempotency_key=_participant_invite_idempotency_key(
                                idempotency_key,
                                company_id=company.id,
                                project_id=project_id,
                                participant_id=participant.id,
                            ),
                            assignment_ids=[assignment.id for assignment in assignments],
                            reminder_assignment_ids=(
                                reminder_assignment_ids if has_prior_delivery else None
                            ),
                        )
                        delivery_status = result.status.value
                        if result.status == "accepted":
                            now = datetime.now(UTC)
                            for assignment in assignments:
                                assignment.status = AssignmentStatus.invited
                                assignment.invited_at = now
                        elif result.status != "queued":
                            send_error_code = "email_provider_rejected"
                            send_error = "Furnizorul de email a refuzat mesajul."
            except DomainError as exc:
                invite_url = None
                send_error_code = exc.code
                send_error = _invite_batch_error_message(exc.code)
            except SQLAlchemyError as exc:
                invite_url = None
                send_error_code = "invitation_persistence_error"
                send_error = "Invitația nu a putut fi salvată. Încearcă din nou."
                _log_invitation_batch_failure(settings.is_production, participant.id, exc)
            except Exception as exc:  # noqa: BLE001
                invite_url = None
                send_error_code = "invitation_delivery_error"
                send_error = "Invitația nu a putut fi pregătită. Încearcă din nou."
                _log_invitation_batch_failure(settings.is_production, participant.id, exc)

            results.append(
                RosterImportEmailResult(
                    participant_id=participant.id,
                    email=participant.email,
                    full_name=participant.full_name,
                    delivery_mode=mode,
                    email_sent=send_error is None and delivery_status == "accepted",
                    email_queued=send_error is None and delivery_status == "queued",
                    error_code=send_error_code,
                    error=send_error,
                    invite_url=invite_url,
                )
            )
            if mode == "email" and send_error is None:
                remaining_sends -= 1

        emails_sent = sum(1 for result in results if result.email_sent)
        emails_queued = sum(1 for result in results if result.email_queued)
        links_generated = sum(
            1
            for result in results
            if result.delivery_mode == "secure_links" and result.invite_url is not None
        )
        return ParticipantInviteBatchResponse(
            results=results,
            total=len(results),
            emails_sent=emails_sent,
            emails_queued=emails_queued,
            emails_failed=sum(
                1
                for result in results
                if result.delivery_mode == "email"
                and not result.email_sent
                and not result.email_queued
            ),
            links_generated=links_generated,
        )

    async def _filter_participants_without_accepted_email(
        self,
        company_id: UUID,
        participants: list[ParticipantProfile],
        project_id: UUID | None,
    ) -> list[ParticipantProfile]:
        from sqlalchemy import select

        from codrut.modules.assignments.models import QuestionnaireAssignment
        from codrut.modules.communications.models import EmailSend, EmailSendStatus

        if not participants:
            return []

        participant_ids = {participant.id for participant in participants}
        stmt = (
            select(QuestionnaireAssignment.respondent_profile_id)
            .join(EmailSend, EmailSend.assignment_id == QuestionnaireAssignment.id)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.respondent_profile_id.in_(participant_ids))
            .where(
                EmailSend.status.in_(
                    (
                        EmailSendStatus.queued,
                        EmailSendStatus.dispatching,
                        EmailSendStatus.accepted,
                        EmailSendStatus.delivered,
                    )
                )
            )
        )
        if project_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.project_id == project_id)
        result = await self.repository.session.execute(stmt)
        sent_participant_ids = set(result.scalars().all())
        return [
            participant
            for participant in participants
            if participant.id not in sent_participant_ids
        ]

    async def list_participant_invitation_statuses(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID | None = None,
    ) -> list[ParticipantInvitationStatusResponse]:
        from sqlalchemy import select

        from codrut.core.config import get_settings
        from codrut.modules.assignments.models import QuestionnaireAssignment
        from codrut.modules.communications.models import EmailSend
        from codrut.modules.communications.task_links import build_task_url, parse_task_token
        from codrut.modules.identity.models import AssignmentInvite

        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, project_id)

        participants = await self.repository.list_participants(company_id)
        if project_id is not None:
            project_memberships = await self.repository.list_project_memberships(
                company_id,
                project_id,
            )
            participants = [participant for _membership, participant in project_memberships]
        if not participants:
            return []

        participant_ids = {participant.id for participant in participants}

        sends_stmt = (
            select(EmailSend, QuestionnaireAssignment.respondent_profile_id)
            .join(QuestionnaireAssignment, EmailSend.assignment_id == QuestionnaireAssignment.id)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.respondent_profile_id.in_(participant_ids))
            .order_by(EmailSend.created_at.desc())
        )
        if project_id is not None:
            sends_stmt = sends_stmt.where(QuestionnaireAssignment.project_id == project_id)
        sends_result = await self.repository.session.execute(sends_stmt)

        latest_send_by_participant: dict[UUID, EmailSend] = {}
        send_count_by_participant: dict[UUID, int] = {}
        for send, participant_id in sends_result.all():
            send_count_by_participant[participant_id] = (
                send_count_by_participant.get(participant_id, 0) + 1
            )
            latest_send_by_participant.setdefault(participant_id, send)

        project_assignment_ids_by_participant: dict[UUID, set[UUID]] = {}
        if project_id is not None:
            assignments_result = await self.repository.session.execute(
                select(QuestionnaireAssignment.id, QuestionnaireAssignment.respondent_profile_id)
                .where(QuestionnaireAssignment.company_id == company_id)
                .where(QuestionnaireAssignment.project_id == project_id)
                .where(QuestionnaireAssignment.respondent_profile_id.in_(participant_ids))
            )
            for assignment_id, participant_id in assignments_result.all():
                project_assignment_ids_by_participant.setdefault(participant_id, set()).add(
                    assignment_id
                )

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
        settings = get_settings()
        for invite in invites_result.scalars().all():
            if project_id is not None:
                try:
                    claims = parse_task_token(invite.token, settings)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Skipping invalid participant invite token: %s", exc)
                    continue
                project_assignment_ids = project_assignment_ids_by_participant.get(
                    invite.respondent_profile_id,
                    set(),
                )
                if not project_assignment_ids.intersection(claims.assignment_ids):
                    continue
            latest_invite_by_participant.setdefault(invite.respondent_profile_id, invite)

        statuses: list[ParticipantInvitationStatusResponse] = []
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
        project_id: UUID | None = None,
    ) -> list:
        assignments_by_participant = await self._list_active_assignments_for_participants(
            company_id,
            [participant],
            project_id,
        )
        return assignments_by_participant.get(participant.id, [])

    async def _list_active_assignments_for_participants(
        self,
        company_id: UUID,
        participants: list[ParticipantProfile],
        project_id: UUID | None = None,
    ) -> dict[UUID, list]:
        from codrut.modules.assignments.models import AssignmentStatus

        participant_ids = [participant.id for participant in participants]
        participant_id_set = set(participant_ids)
        assignments = await self.repository.list_assignments_for_participants(participant_ids)
        active_statuses = {
            AssignmentStatus.assigned,
            AssignmentStatus.invited,
            AssignmentStatus.started,
        }
        active_assignments_by_participant = {
            participant_id: [] for participant_id in participant_ids
        }
        for assignment in assignments:
            if (
                assignment.respondent_profile_id in participant_id_set
                and assignment.company_id == company_id
                and assignment.status in active_statuses
                and (project_id is None or assignment.project_id == project_id)
            ):
                active_assignments_by_participant[assignment.respondent_profile_id].append(
                    assignment
                )
        return active_assignments_by_participant

    async def resend_invite(
        self,
        user_id: UUID,
        company_id: UUID,
        participant_id: UUID,
        project_id: UUID | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> RosterImportResponse:
        company = await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, project_id)

        participant = await self.repository.get_participant_by_id(participant_id)
        if participant is None or participant.company_id != company_id:
            raise DomainError("Participant not found.", code="participant_not_found")

        result = await self._dispatch_participant_invites(
            user_id=user_id,
            company=company,
            participants=[participant],
            project_id=project_id,
            mode="email",
            force_rotate=False,
            idempotency_key=idempotency_key,
        )
        return RosterImportResponse(
            participants=[participant],
            email_results=result.results,
            total_imported=1,
            emails_sent=result.emails_sent,
            emails_queued=result.emails_queued,
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
    ) -> NoReturn:
        _ = payload
        raise DomainError(
            "Company access-code registration is disabled. "
            "Use the secure invite flow to claim participant accounts.",
            code="access_code_registration_disabled",
        )

    async def import_reporting_relationships(
        self,
        user_id: UUID,
        company_id: UUID,
    ) -> ReportingRelationshipImportResponse:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        participants = await self.repository.list_participants(company_id)
        participants_by_name: dict[str, ParticipantProfile] = {}
        duplicate_name_keys: set[str] = set()
        for participant in participants:
            name_key = manager_reference_key(participant.full_name)
            if not name_key:
                continue
            if name_key in participants_by_name:
                duplicate_name_keys.add(name_key)
            else:
                participants_by_name[name_key] = participant
        manager_by_participant: dict[UUID, ParticipantProfile] = {}
        issues: list[ReportingRelationshipIssue] = []

        for participant in participants:
            reports_to_name = clean_manager_reference(participant.reports_to_name)
            if reports_to_name is None:
                continue
            manager_key = manager_reference_key(reports_to_name)
            if manager_key in duplicate_name_keys:
                issues.append(
                    _relationship_issue(
                        participant,
                        reports_to_name,
                        "manager_name_ambiguous",
                        "Manager name is ambiguous in this company roster.",
                    )
                )
                continue
            manager = participants_by_name.get(manager_key)
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

    async def _require_company_project(
        self,
        company_id: UUID,
        project_id: UUID | None,
    ) -> None:
        if project_id is None:
            return
        project = await self.repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError("Project not found in this company.", code="project_not_found")

    async def _require_company_manager(self, user_id: UUID, company_id: UUID) -> None:
        membership = await self.repository.get_membership(company_id, user_id)
        if membership is not None and membership.role in {
            CompanyMembershipRole.owner,
            CompanyMembershipRole.trainer,
        }:
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


def _project_participant_response(
    membership: ProjectMembership,
    participant: ParticipantProfile,
) -> ProjectParticipantResponse:
    return ProjectParticipantResponse(
        id=participant.id,
        company_id=participant.company_id,
        user_id=participant.user_id,
        is_shadow_account=participant.is_shadow_account,
        full_name=participant.full_name,
        email=participant.email,
        reports_to_name=membership.reports_to_name,
        position=membership.position,
        location=membership.location,
        role_group=membership.role_group,
        pcm_profile=participant.pcm_profile,
        pcm_base=participant.pcm_base,
        pcm_phase=participant.pcm_phase,
        anonymous_name=participant.anonymous_name,
        project_membership_id=membership.id,
    )


def _validate_date_window(
    starts_at: datetime | None,
    due_at: datetime | None,
    code: str,
) -> None:
    if starts_at is not None and due_at is not None and due_at < starts_at:
        message = (
            "Project due date cannot be before its start date."
            if code == "invalid_project_dates"
            else "Form close date cannot be before its open date."
        )
        raise DomainError(
            message,
            code=code,
        )


def _project_invite_expires_at(project: CompanyProject | None) -> datetime | None:
    if project is None:
        return None

    now = datetime.now(UTC)
    if project.form_opens_at is not None and project.form_opens_at > now:
        raise DomainError(
            "Project questionnaires are not open yet.",
            code="project_not_open",
        )

    close_candidates = [
        value for value in (project.form_closes_at, project.due_at) if value is not None
    ]
    if not close_candidates:
        return None

    expires_at = min(close_candidates)
    if expires_at <= now:
        raise DomainError(
            "Project questionnaire window has closed.",
            code="project_closed",
        )
    return expires_at


def _normalize_roster_row(row: RosterImportRow) -> RosterImportRow:
    return RosterImportRow(
        full_name=row.full_name.strip(),
        reports_to_name=clean_manager_reference(row.reports_to_name),
        position=_clean_optional(row.position),
        location=_clean_optional(row.location),
        email=row.email.lower() if row.email is not None else None,
        role_group=_normalize_role_group(row.role_group),
        pcm_profile=_clean_optional(row.pcm_profile),
        pcm_base=_clean_optional(row.pcm_base),
        pcm_phase=_clean_optional(row.pcm_phase),
    )


def _infer_roster_role_group(row: RosterImportRow, manager_names: set[str]) -> str:
    explicit_role = _normalize_role_group(row.role_group)
    if explicit_role is not None:
        return explicit_role
    if row.reports_to_name is None:
        return "leadership"
    if manager_reference_key(row.full_name) in manager_names:
        return "leadership"
    return "member"


def _normalize_role_group(value: str | None) -> str | None:
    cleaned = _clean_optional(value)
    if cleaned is None:
        return None
    normalized = cleaned.casefold().replace("-", "_").replace(" ", "_")
    if normalized in {"leadership", "leader", "manager", "management"}:
        return "leadership"
    if normalized in {"member", "team", "team_member", "non_leadership", "not_leadership"}:
        return "member"
    return cleaned.casefold()


def _is_leadership_role(value: str | None) -> bool:
    return _normalize_role_group(value) in {"leadership", "manager"}


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


def _participant_invite_idempotency_key(
    request_key: str | None,
    *,
    company_id: UUID,
    project_id: UUID | None,
    participant_id: UUID,
) -> str | None:
    if not request_key:
        return None
    scope = f"invite:{company_id}:{project_id or 'all'}:{participant_id}"
    return hashlib.sha256(f"{request_key}:{scope}".encode()).hexdigest()


def _invite_batch_error_message(code: str) -> str:
    messages = {
        "reminder_not_due": (
            "Reminderul nu este încă disponibil sau cele două runde au fost trimise."
        ),
        "no_active_assignments": "Participantul nu are sarcini active pentru acest proiect.",
        "project_not_open": "Chestionarele proiectului nu sunt încă deschise.",
        "project_closed": "Perioada de completare a proiectului s-a încheiat.",
        "profile_not_found": "Participantul nu mai este disponibil în acest proiect.",
    }
    return messages.get(code, "Invitația nu a putut fi pregătită. Încearcă din nou.")


def _log_invitation_batch_failure(
    production: bool,
    participant_id: UUID,
    exc: Exception,
) -> None:
    context = {
        "participant_id": str(participant_id),
        "error_category": type(exc).__name__,
    }
    if production:
        logger.error(
            "Invitation batch recipient failed participant_id=%s category=%s",
            participant_id,
            type(exc).__name__,
            extra=context,
        )
        return
    logger.exception(
        "Invitation batch recipient failed participant_id=%s category=%s",
        participant_id,
        type(exc).__name__,
        exc_info=exc,
        extra=context,
    )


def _new_access_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


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
