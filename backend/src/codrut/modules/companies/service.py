import hashlib
import logging
import secrets
import string
from datetime import UTC, datetime
from typing import Literal, NoReturn
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssessmentCycle, AssessmentCycleStatus
from codrut.modules.companies.anonymous import (
    allocate_anonymous_name,
)
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
    CompanyProjectStatus,
    ParticipantAccountLinkAudit,
    ParticipantProfile,
    ParticipantReportingRelationship,
    ProjectLifecycleAction,
    ProjectLifecycleEvent,
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
    ParticipantAccountLinkRepairRequest,
    ParticipantAccountLinkStatusResponse,
    ParticipantAccountSummary,
    ParticipantCreateRequest,
    ParticipantInvitationStatusResponse,
    ParticipantInviteBatchRequest,
    ParticipantInviteBatchResponse,
    ParticipantRemovalRequest,
    ParticipantUpdateRequest,
    ProjectLifecycleEventResponse,
    ProjectParticipantResponse,
    ProjectPermanentDeleteRequest,
    ReportingRelationshipImportResponse,
    ReportingRelationshipIssue,
    RosterImportEmailResult,
    RosterImportRequest,
    RosterImportResponse,
    RosterImportRow,
)
from codrut.modules.identity.models import User
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
        *,
        include_archived: bool = False,
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
                archived_at=project.archived_at,
                archived_by_user_id=project.archived_by_user_id,
                archived_from_status=project.archived_from_status,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
            for project, company_name in await self.repository.list_projects_with_company(
                user_id=user_id,
                include_archived=include_archived,
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
            archived_at=project.archived_at,
            archived_by_user_id=project.archived_by_user_id,
            archived_from_status=project.archived_from_status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def list_projects(
        self,
        user_id: UUID,
        company_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[CompanyProject]:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        return await self.repository.list_projects(
            company_id,
            include_archived=include_archived,
        )

    async def _validate_project_template_key(
        self,
        key: str | None,
        owner_id: UUID,
        field_name: str,
    ) -> str | None:
        if key is None:
            return None
        cleaned = key.strip()
        if not cleaned:
            return None
        from codrut.modules.communications.templates import TransactionalTemplateKey

        if cleaned in TransactionalTemplateKey.__members__:
            return cleaned
        from codrut.modules.communications.repository import CommunicationsRepository
        from codrut.modules.communications.service import (
            INVITATION_TEMPLATE_ALLOWED_VARS,
            extract_placeholders,
        )

        comm_repo = CommunicationsRepository(self.repository.session)
        template = await comm_repo.get_template(cleaned, owner_id=owner_id)
        if template is None:
            raise DomainError(
                f"Șablonul '{cleaned}' pentru {field_name} nu a fost găsit.",
                code="template_not_found",
            )
        if not template.active:
            raise DomainError(
                f"Șablonul '{cleaned}' pentru {field_name} este inactiv.",
                code="template_inactive",
            )
        if template.audience and str(template.audience).startswith("campaign"):
            raise DomainError(
                f"Șablonul de campanie '{cleaned}' nu poate fi folosit pentru {field_name}.",
                code="campaign_template_not_allowed",
            )
        placeholders = (
            extract_placeholders(template.subject)
            | extract_placeholders(template.html_body)
            | extract_placeholders(template.text_body)
        )
        if "action_url" not in placeholders:
            raise DomainError(
                f"Șablonul '{cleaned}' nu conține linkul de acces (action_url).",
                code="email_template_missing_action_url",
            )
        unsupported = placeholders - INVITATION_TEMPLATE_ALLOWED_VARS
        if unsupported:
            vars_str = ", ".join(sorted(unsupported))
            raise DomainError(
                f"Șablonul '{cleaned}' conține variabile nesuportate: {vars_str}",
                code="email_template_unsupported_variables",
            )
        return cleaned

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
        if payload.status == CompanyProjectStatus.archived:
            raise DomainError(
                "Create the project before archiving it.",
                code="project_archive_action_required",
            )
        _validate_date_window(payload.starts_at, payload.due_at, "invalid_project_dates")
        _validate_date_window(
            payload.form_opens_at,
            payload.form_closes_at,
            "invalid_form_window",
        )
        leadership_inv_key = await self._validate_project_template_key(
            payload.leadership_invitation_template_key,
            user_id,
            "invitația de leadership",
        )
        member_inv_key = await self._validate_project_template_key(
            payload.member_invitation_template_key,
            user_id,
            "invitația de membri",
        )
        leadership_rem_key = await self._validate_project_template_key(
            payload.leadership_reminder_template_key,
            user_id,
            "reminderul de leadership",
        )
        member_rem_key = await self._validate_project_template_key(
            payload.member_reminder_template_key,
            user_id,
            "reminderul de membri",
        )
        project = await self.repository.add_project(
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
                leadership_invitation_template_key=leadership_inv_key,
                member_invitation_template_key=member_inv_key,
                leadership_reminder_template_key=leadership_rem_key,
                member_reminder_template_key=member_rem_key,
            )
        )
        self.repository.session.add(
            AssessmentCycle(
                company_id=company_id,
                project_id=project.id,
                sequence=1,
                name="Evaluare inițială",
                status=AssessmentCycleStatus.draft,
                starts_at=project.starts_at,
                due_at=project.due_at,
                created_by_user_id=user_id,
            )
        )
        await self.repository.session.flush()
        return project

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
        if project.status == CompanyProjectStatus.archived:
            raise DomainError(
                "Restore the project before changing its settings.",
                code="project_restore_required",
            )

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
            if payload.status == CompanyProjectStatus.archived:
                raise DomainError(
                    "Archive projects using the archive action.",
                    code="project_archive_action_required",
                )
            project.status = payload.status
        if "starts_at" in payload.model_fields_set:
            project.starts_at = payload.starts_at
        if "due_at" in payload.model_fields_set:
            project.due_at = payload.due_at
        if "form_opens_at" in payload.model_fields_set:
            project.form_opens_at = payload.form_opens_at
        if "form_closes_at" in payload.model_fields_set:
            project.form_closes_at = payload.form_closes_at
        if "leadership_invitation_template_key" in payload.model_fields_set:
            project.leadership_invitation_template_key = (
                await self._validate_project_template_key(
                    payload.leadership_invitation_template_key,
                    user_id,
                    "invitația de leadership",
                )
            )
        if "member_invitation_template_key" in payload.model_fields_set:
            project.member_invitation_template_key = (
                await self._validate_project_template_key(
                    payload.member_invitation_template_key,
                    user_id,
                    "invitația de membri",
                )
            )
        if "leadership_reminder_template_key" in payload.model_fields_set:
            project.leadership_reminder_template_key = (
                await self._validate_project_template_key(
                    payload.leadership_reminder_template_key,
                    user_id,
                    "reminderul de leadership",
                )
            )
        if "member_reminder_template_key" in payload.model_fields_set:
            project.member_reminder_template_key = (
                await self._validate_project_template_key(
                    payload.member_reminder_template_key,
                    user_id,
                    "reminderul de membri",
                )
            )

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
        if project.status == CompanyProjectStatus.archived:
            return

        previous_status = project.status
        project.status = CompanyProjectStatus.archived
        project.archived_at = datetime.now(UTC)
        project.archived_by_user_id = user_id
        project.archived_from_status = previous_status
        await self.repository.add_project_lifecycle_event(
            ProjectLifecycleEvent(
                company_id=company_id,
                project_id=project.id,
                actor_user_id=user_id,
                action=ProjectLifecycleAction.archived.value,
                project_name=project.name,
                previous_status=previous_status.value,
                next_status=CompanyProjectStatus.archived.value,
            )
        )
        await self.repository.session.flush()

    async def restore_project(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
    ) -> CompanyProject:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        project = await self.repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError("Project not found.", code="project_not_found")
        if project.status != CompanyProjectStatus.archived:
            raise DomainError("Project is not archived.", code="project_not_archived")

        restored_status = project.archived_from_status or CompanyProjectStatus.draft
        if restored_status == CompanyProjectStatus.archived:
            restored_status = CompanyProjectStatus.draft
        project.status = restored_status
        project.archived_at = None
        project.archived_by_user_id = None
        project.archived_from_status = None
        await self.repository.add_project_lifecycle_event(
            ProjectLifecycleEvent(
                company_id=company_id,
                project_id=project.id,
                actor_user_id=user_id,
                action=ProjectLifecycleAction.restored.value,
                project_name=project.name,
                previous_status=CompanyProjectStatus.archived.value,
                next_status=restored_status.value,
            )
        )
        await self.repository.session.flush()
        return project

    async def permanently_delete_project(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
        payload: ProjectPermanentDeleteRequest,
    ) -> None:
        await self._require_company(company_id)
        await self._require_company_owner(user_id, company_id)
        project = await self.repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError("Project not found.", code="project_not_found")
        if project.status != CompanyProjectStatus.archived:
            raise DomainError(
                "Archive the project before permanently deleting it.",
                code="project_archive_required",
            )
        if payload.project_name.strip() != project.name:
            raise DomainError(
                "Project name confirmation does not match.",
                code="project_name_confirmation_mismatch",
            )

        await self.repository.add_project_lifecycle_event(
            ProjectLifecycleEvent(
                company_id=company_id,
                project_id=project.id,
                actor_user_id=user_id,
                action=ProjectLifecycleAction.permanently_deleted.value,
                project_name=project.name,
                previous_status=CompanyProjectStatus.archived.value,
                next_status=None,
            )
        )
        await self.repository.delete_project(project)

    async def list_project_lifecycle_events(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
    ) -> list[ProjectLifecycleEventResponse]:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        project = await self.repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError("Project not found.", code="project_not_found")
        return [
            ProjectLifecycleEventResponse(
                id=event.id,
                company_id=event.company_id,
                project_id=event.project_id,
                actor_user_id=event.actor_user_id,
                actor_email=actor_email,
                action=event.action,
                project_name=event.project_name,
                previous_status=event.previous_status,
                next_status=event.next_status,
                created_at=event.created_at,
            )
            for event, actor_email in await self.repository.list_project_lifecycle_events(
                company_id,
                project_id,
            )
        ]

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

    async def get_participant_account_link_status(
        self,
        company_id: UUID,
        participant_id: UUID,
    ) -> ParticipantAccountLinkStatusResponse:
        await self._require_company(company_id)
        participant = await self.repository.get_participant(company_id, participant_id)
        if participant is None:
            raise DomainError("Participant not found.", code="participant_not_found")
        if participant.email is None:
            raise DomainError(
                "Participant has no email address.",
                code="participant_email_missing",
            )

        linked_account = (
            await self.identity_repository.get_user_by_id(participant.user_id)
            if participant.user_id is not None
            else None
        )
        matching_account = await self.identity_repository.get_user_by_email(
            participant.email.lower()
        )
        return _participant_account_link_status(
            participant,
            linked_account,
            matching_account,
        )

    async def repair_participant_account_link(
        self,
        actor_user_id: UUID,
        company_id: UUID,
        participant_id: UUID,
        payload: ParticipantAccountLinkRepairRequest,
    ) -> ParticipantAccountLinkStatusResponse:
        # This operation is intentionally platform-trainer scoped. The router
        # authenticates the actor as a trainer; exact email confirmation, a
        # reason, row locking, and an immutable audit record constrain the edit.
        await self._require_company(company_id)
        participant = await self.repository.get_participant_for_update(
            company_id,
            participant_id,
        )
        if participant is None:
            raise DomainError("Participant not found.", code="participant_not_found")
        if participant.email is None:
            raise DomainError(
                "Participant has no email address.",
                code="participant_email_missing",
            )

        participant_email = participant.email.lower()
        if str(payload.confirmation_email).lower() != participant_email:
            raise DomainError(
                "Confirmation email does not match the participant.",
                code="account_link_confirmation_mismatch",
            )
        reason = payload.reason.strip()
        if len(reason) < 10:
            raise DomainError(
                "Repair reason must contain at least 10 characters.",
                code="account_link_reason_too_short",
            )

        previous_user_id = participant.user_id
        previous_user = (
            await self.identity_repository.get_user_by_id(participant.user_id)
            if participant.user_id is not None
            else None
        )
        matching_user = await self.identity_repository.get_user_by_email(participant_email)
        new_user: User | None

        if payload.action == "link_matching_email":
            if matching_user is None:
                raise DomainError(
                    "No platform account uses the participant email.",
                    code="matching_account_not_found",
                )
            if participant.user_id == matching_user.id:
                raise DomainError(
                    "Participant is already linked to the matching account.",
                    code="account_already_linked",
                )
            participant.user_id = matching_user.id
            new_user = matching_user
        else:
            if participant.user_id is None:
                raise DomainError(
                    "Participant is not linked to an account.",
                    code="account_not_linked",
                )
            participant.user_id = None
            new_user = None

        await self.repository.add_participant_account_link_audit(
            ParticipantAccountLinkAudit(
                company_id=company_id,
                participant_profile_id=participant.id,
                actor_user_id=actor_user_id,
                action=payload.action,
                previous_user_id=previous_user_id,
                previous_user_email=previous_user.email if previous_user is not None else None,
                new_user_id=new_user.id if new_user is not None else None,
                new_user_email=new_user.email if new_user is not None else None,
                reason=reason,
            )
        )
        invites = await self.identity_repository.list_invites_for_respondent(
            company_id,
            participant.id,
        )
        await self.identity_repository.delete_sessions_for_invites(
            [invite.id for invite in invites]
        )

        return _participant_account_link_status(
            participant,
            new_user,
            matching_user,
        )

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
                anonymous_name=await self._allocate_anonymous_name(),
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
            await self._require_company_project(
                company_id,
                payload.project_id,
                allow_archived=False,
            )

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

    async def remove_project_participant(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
        participant_id: UUID,
        payload: ParticipantRemovalRequest,
    ) -> None:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, project_id, allow_archived=False)

        participant = await self.repository.get_participant_for_update(
            company_id,
            participant_id,
        )
        if participant is None:
            raise DomainError("Participant not found.", code="participant_not_found")

        membership = await self.repository.get_project_membership(project_id, participant_id)
        if membership is None or membership.company_id != company_id or not membership.active:
            raise DomainError(
                "Participant is not a member of this project.",
                code="project_membership_not_found",
            )

        project_memberships = await self.repository.list_project_memberships(
            company_id,
            project_id,
        )
        direct_reports = [
            (direct_membership, direct_participant)
            for direct_membership, direct_participant in project_memberships
            if direct_participant.id != participant.id
            and manager_reference_key(direct_membership.reports_to_name)
            == manager_reference_key(participant.full_name)
        ]
        _require_expected_direct_reports(
            payload,
            [direct_participant for _membership, direct_participant in direct_reports],
        )

        for direct_membership, _direct_participant in direct_reports:
            direct_membership.reports_to_name = None
        await self.repository.delete_project_membership(membership)

    async def delete_company_participant(
        self,
        user_id: UUID,
        company_id: UUID,
        participant_id: UUID,
        payload: ParticipantRemovalRequest,
    ) -> None:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        participant = await self.repository.get_participant_for_update(
            company_id,
            participant_id,
        )
        if participant is None:
            raise DomainError("Participant not found.", code="participant_not_found")
        if participant.user_id is not None:
            raise DomainError(
                "Participantul are un cont asociat și nu poate fi șters din companie.",
                code="participant_has_account",
            )

        project_memberships = await self.repository.list_all_project_memberships(company_id)
        participant_memberships = [
            membership
            for membership, member in project_memberships
            if member.id == participant.id
        ]
        if participant_memberships:
            raise DomainError(
                "Elimină participantul din proiectele companiei înainte de ștergere.",
                code="participant_has_project_memberships",
                details={
                    "project_ids": sorted(
                        {str(membership.project_id) for membership in participant_memberships}
                    )
                },
            )

        blockers = await self.repository.participant_deletion_blockers(participant.id)
        if blockers:
            raise DomainError(
                "Participantul are istoric protejat și nu poate fi șters din companie.",
                code="participant_has_protected_history",
                details={"blockers": blockers},
            )

        participants = await self.repository.list_participants(company_id)
        direct_reports_by_id = {
            direct_participant.id: direct_participant
            for direct_participant in participants
            if direct_participant.id != participant.id
            and manager_reference_key(direct_participant.reports_to_name)
            == manager_reference_key(participant.full_name)
        }
        for direct_membership, direct_participant in project_memberships:
            if (
                direct_participant.id != participant.id
                and manager_reference_key(direct_membership.reports_to_name)
                == manager_reference_key(participant.full_name)
            ):
                direct_reports_by_id[direct_participant.id] = direct_participant
        for relationship in await self.repository.list_reporting_relationships(company_id):
            if relationship.manager_profile_id == participant.id:
                direct_report = next(
                    (
                        candidate
                        for candidate in participants
                        if candidate.id == relationship.participant_profile_id
                    ),
                    None,
                )
                if direct_report is not None:
                    direct_reports_by_id[direct_report.id] = direct_report

        direct_reports = list(direct_reports_by_id.values())
        _require_expected_direct_reports(payload, direct_reports)

        for direct_report in direct_reports:
            if (
                manager_reference_key(direct_report.reports_to_name)
                == manager_reference_key(participant.full_name)
            ):
                direct_report.reports_to_name = None
        for direct_membership, direct_participant in project_memberships:
            if (
                direct_participant.id in direct_reports_by_id
                and manager_reference_key(direct_membership.reports_to_name)
                == manager_reference_key(participant.full_name)
            ):
                direct_membership.reports_to_name = None

        await self.repository.delete_participant(participant)

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
        await self._require_company_project(
            company_id,
            payload.project_id,
            allow_archived=False,
        )
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
        reserved_anonymous_names: set[str] = set()
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
                        anonymous_name=await self._allocate_anonymous_name(
                            reserved_anonymous_names
                        ),
                    )
                )
            elif not participant.anonymous_name:
                participant.anonymous_name = await self._allocate_anonymous_name(
                    reserved_anonymous_names
                )

            if participant.anonymous_name:
                reserved_anonymous_names.add(participant.anonymous_name)

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
            None,
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
            assessment_cycle_id=None,
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
        await self._require_company_project(
            company_id,
            payload.project_id,
            allow_archived=False,
        )
        await self._require_invitation_assessment_cycle(
            company_id,
            payload.project_id,
            payload.assessment_cycle_id,
        )
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
                payload.assessment_cycle_id,
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
            assessment_cycle_id=payload.assessment_cycle_id,
            mode=payload.mode,
            force_rotate=payload.force_rotate,
            idempotency_key=idempotency_key,
        )

    async def _ensure_anonymous_names(self, participants: list[ParticipantProfile]) -> None:
        changed = False
        reserved_anonymous_names = {
            participant.anonymous_name
            for participant in participants
            if participant.anonymous_name
        }
        for participant in participants:
            if participant.anonymous_name:
                continue
            participant.anonymous_name = await self._allocate_anonymous_name(
                reserved_anonymous_names
            )
            reserved_anonymous_names.add(participant.anonymous_name)
            changed = True
        if changed:
            await self.repository.session.flush()

    async def _allocate_anonymous_name(
        self,
        reserved: set[str] | None = None,
    ) -> str:
        reserved_names = reserved or set()

        async def is_taken(candidate: str) -> bool:
            return await self.repository.anonymous_name_exists(candidate)

        return await allocate_anonymous_name(
            is_taken,
            reserved=reserved_names,
        )

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
        assessment_cycle_id: UUID | None,
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
            await self.repository.get_project(company.id, project_id, for_update=True)
            if project_id is not None
            else None
        )
        if project_id is not None and project is None:
            raise DomainError("Project not found.", code="project_not_found")
        if project is not None and project.status == CompanyProjectStatus.archived:
            raise DomainError(
                "Restore the project before sending invitations.",
                code="project_restore_required",
            )
        if project is not None and project.status == CompanyProjectStatus.completed:
            raise DomainError(
                "Completed projects cannot send invitations.",
                code="project_completed",
            )
        cycle = (
            await self._get_assessment_cycle(
                company.id,
                project_id,
                assessment_cycle_id,
                for_update=True,
            )
            if project_id is not None and assessment_cycle_id is not None
            else None
        )
        if cycle is not None and cycle.status == AssessmentCycleStatus.closed:
            raise DomainError(
                "Assessment cycle is closed.",
                code="assessment_cycle_closed",
            )
        invite_expires_at = _assessment_invite_expires_at(project, cycle)
        active_assignments_by_participant = await self._list_active_assignments_for_participants(
            company.id,
            participants,
            project_id,
            assessment_cycle_id,
        )
        active_assignment_ids = {
            assignment.id
            for assignments in active_assignments_by_participant.values()
            for assignment in assignments
        }
        project_was_draft = (
            project is not None and project.status == CompanyProjectStatus.draft
        )
        cycle_was_draft = cycle is not None and cycle.status == AssessmentCycleStatus.draft
        cycle_original_starts_at = cycle.starts_at if cycle is not None else None
        if project_was_draft and active_assignment_ids:
            project.status = CompanyProjectStatus.active
        if assessment_cycle_id is not None and active_assignment_ids:
            assert project_id is not None
            from codrut.modules.assignments.service import AssignmentService

            cycle = await AssignmentService(
                self.repository.session
            ).activate_assessment_cycle_for_invitation(
                company.id,
                project_id,
                assessment_cycle_id,
            )
            invite_expires_at = _assessment_invite_expires_at(project, cycle)
        successfully_delivered_assignment_ids = (
            await communications_repository.list_successfully_delivered_assignment_ids(
                active_assignment_ids
            )
            if mode == "email"
            else set()
        )

        results: list[RosterImportEmailResult] = []
        has_sendable_email = any(participant.email is not None for participant in participants)
        if (
            mode == "email"
            and has_sendable_email
            and hasattr(communications_repository, "acquire_email_capacity_lock")
        ):
            await communications_repository.acquire_email_capacity_lock()
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
            new_email_reserved = False
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
                        queued = await email_service.enqueue_assignment_invitation(
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
                                assessment_cycle_id=assessment_cycle_id,
                                participant_id=participant.id,
                            ),
                            assignment_ids=[assignment.id for assignment in assignments],
                            reminder_assignment_ids=(
                                reminder_assignment_ids if has_prior_delivery else None
                            ),
                            allow_new=remaining_sends > 0,
                            leadership_invitation_template_key=(
                                project.leadership_invitation_template_key if project else None
                            ),
                            member_invitation_template_key=(
                                project.member_invitation_template_key if project else None
                            ),
                            leadership_reminder_template_key=(
                                project.leadership_reminder_template_key if project else None
                            ),
                            member_reminder_template_key=(
                                project.member_reminder_template_key if project else None
                            ),
                        )
                        result = queued.delivery
                        new_email_reserved = queued.created
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
                send_error = _invite_batch_error_message(
                    exc.code,
                    role_group=participant.role_group,
                )
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
            if mode == "email" and send_error is None and new_email_reserved:
                remaining_sends -= 1

        emails_sent = sum(1 for result in results if result.email_sent)
        emails_queued = sum(1 for result in results if result.email_queued)
        links_generated = sum(
            1
            for result in results
            if result.delivery_mode == "secure_links" and result.invite_url is not None
        )
        delivery_succeeded = bool(emails_sent or emails_queued or links_generated)
        if not delivery_succeeded:
            if project is not None and project_was_draft:
                project.status = CompanyProjectStatus.draft
            if cycle is not None and cycle_was_draft:
                cycle.status = AssessmentCycleStatus.draft
                cycle.starts_at = cycle_original_starts_at
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
        assessment_cycle_id: UUID | None,
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
        if assessment_cycle_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id)
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
        assessment_cycle_id: UUID | None = None,
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
        await self._require_invitation_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
        )

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
        if assessment_cycle_id is not None:
            sends_stmt = sends_stmt.where(
                QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id
            )
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
            assignments_stmt = (
                select(QuestionnaireAssignment.id, QuestionnaireAssignment.respondent_profile_id)
                .where(QuestionnaireAssignment.company_id == company_id)
                .where(QuestionnaireAssignment.project_id == project_id)
                .where(QuestionnaireAssignment.respondent_profile_id.in_(participant_ids))
            )
            if assessment_cycle_id is not None:
                assignments_stmt = assignments_stmt.where(
                    QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id
                )
            assignments_result = await self.repository.session.execute(assignments_stmt)
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
                    latest_template_key=latest_send.template_key
                    if latest_send is not None
                    else None,
                    latest_template_version=latest_send.template_version
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
        assessment_cycle_id: UUID | None = None,
    ) -> list:
        assignments_by_participant = await self._list_active_assignments_for_participants(
            company_id,
            [participant],
            project_id,
            assessment_cycle_id,
        )
        return assignments_by_participant.get(participant.id, [])

    async def _list_active_assignments_for_participants(
        self,
        company_id: UUID,
        participants: list[ParticipantProfile],
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
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
                and (
                    assessment_cycle_id is None
                    or assignment.assessment_cycle_id == assessment_cycle_id
                )
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
        assessment_cycle_id: UUID | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> RosterImportResponse:
        company = await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(
            company_id,
            project_id,
            allow_archived=False,
        )
        await self._require_invitation_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
        )

        participant = await self.repository.get_participant_by_id(participant_id)
        if participant is None or participant.company_id != company_id:
            raise DomainError("Participant not found.", code="participant_not_found")

        result = await self._dispatch_participant_invites(
            user_id=user_id,
            company=company,
            participants=[participant],
            project_id=project_id,
            assessment_cycle_id=assessment_cycle_id,
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

    async def _require_invitation_assessment_cycle(
        self,
        company_id: UUID,
        project_id: UUID | None,
        assessment_cycle_id: UUID | None,
    ) -> None:
        if assessment_cycle_id is None:
            return
        if project_id is None:
            raise DomainError(
                "A project is required for an assessment cycle.",
                code="assessment_cycle_project_required",
            )
        cycle = await self._get_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
        )
        if cycle is None:
            raise DomainError(
                "Assessment cycle not found in this project.",
                code="assessment_cycle_not_found",
            )

    async def _get_assessment_cycle(
        self,
        company_id: UUID,
        project_id: UUID,
        assessment_cycle_id: UUID,
        *,
        for_update: bool = False,
    ) -> AssessmentCycle | None:
        statement = select(AssessmentCycle).where(
            AssessmentCycle.id == assessment_cycle_id,
            AssessmentCycle.company_id == company_id,
            AssessmentCycle.project_id == project_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.repository.session.scalar(statement)

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
        *,
        allow_archived: bool = True,
    ) -> None:
        if project_id is None:
            return
        project = await self.repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError("Project not found in this company.", code="project_not_found")
        if not allow_archived and project.status == CompanyProjectStatus.archived:
            raise DomainError(
                "Restore the project before changing its data.",
                code="project_restore_required",
            )

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

    async def _require_company_owner(self, user_id: UUID, company_id: UUID) -> None:
        membership = await self.repository.get_membership(company_id, user_id)
        if membership is not None and membership.role == CompanyMembershipRole.owner:
            return

        raise DomainError(
            "Only a company owner can permanently delete a project.",
            code="company_owner_required",
        )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _participant_account_summary(user: User | None) -> ParticipantAccountSummary | None:
    if user is None:
        return None
    return ParticipantAccountSummary(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
        account_type="registered" if user.is_registered else "guest",
        is_shadow_account=not user.is_registered,
    )


def _participant_account_link_status(
    participant: ParticipantProfile,
    linked_account: User | None,
    matching_account: User | None,
) -> ParticipantAccountLinkStatusResponse:
    if participant.email is None:
        raise ValueError("Participant email is required for account-link status.")
    return ParticipantAccountLinkStatusResponse(
        participant_id=participant.id,
        participant_email=participant.email,
        linked_account=_participant_account_summary(linked_account),
        matching_email_account=_participant_account_summary(matching_account),
        matching_account_is_linked=bool(
            linked_account is not None
            and matching_account is not None
            and linked_account.id == matching_account.id
        ),
    )


def _project_participant_response(
    membership: ProjectMembership,
    participant: ParticipantProfile,
) -> ProjectParticipantResponse:
    return ProjectParticipantResponse(
        id=participant.id,
        company_id=participant.company_id,
        user_id=participant.user_id,
        avatar_palette_key=participant.avatar_palette_key,
        account_type=participant.account_type,
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


def _assessment_invite_expires_at(
    project: CompanyProject | None,
    cycle: AssessmentCycle | None,
) -> datetime | None:
    project_expiry = _project_invite_expires_at(project)
    if cycle is None or cycle.due_at is None:
        return project_expiry

    now = datetime.now(UTC)
    if cycle.due_at <= now:
        raise DomainError(
            "Assessment cycle questionnaire window has closed.",
            code="assessment_cycle_closed",
        )
    return min(project_expiry, cycle.due_at) if project_expiry is not None else cycle.due_at


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


def _require_expected_direct_reports(
    payload: ParticipantRemovalRequest,
    direct_reports: list[ParticipantProfile],
) -> None:
    expected_ids = set(payload.expected_direct_report_ids)
    actual_ids = {participant.id for participant in direct_reports}
    if expected_ids == actual_ids:
        return
    raise DomainError(
        "Lista persoanelor care raportează acestui participant s-a modificat. "
        "Reîncarcă și verifică din nou.",
        code="participant_direct_reports_changed",
        details={
            "direct_reports": [
                {"id": str(participant.id), "full_name": participant.full_name}
                for participant in sorted(direct_reports, key=lambda item: item.full_name)
            ]
        },
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
    assessment_cycle_id: UUID | None,
    participant_id: UUID,
) -> str | None:
    if not request_key:
        return None
    scope = (
        f"invite:{company_id}:{project_id or 'all'}:{assessment_cycle_id or 'all'}:{participant_id}"
    )
    return hashlib.sha256(f"{request_key}:{scope}".encode()).hexdigest()


def _invite_batch_error_message(code: str, role_group: str | None = None) -> str:
    if code == "template_inactive":
        if role_group == "leadership":
            return (
                "Șablonul ales pentru echipa de direcție este dezactivat. "
                "Activează-l din secțiunea Șabloane, apoi reia trimiterea."
            )
        if role_group == "member":
            return (
                "Șablonul ales pentru membrii echipei este dezactivat. "
                "Activează-l din secțiunea Șabloane, apoi reia trimiterea."
            )
        return (
            "Șablonul ales este dezactivat. "
            "Activează-l din secțiunea Șabloane, apoi reia trimiterea."
        )
    if code == "template_not_found":
        return "Șablonul ales nu mai există. Alege altul din lista de la Șabloane."
    if code in ("action_url_missing", "email_template_missing_action_url"):
        return (
            "Șablonul ales nu conține butonul de acces. "
            "Fără el, destinatarii nu ar avea unde intra. "
            "Adaugă butonul și reia."
        )
    if code == "campaign_template_not_allowed":
        return (
            "Ai ales un șablon de campanie. "
            "Pentru invitații e nevoie de un șablon de sistem."
        )
    if code in ("unsupported_placeholders", "email_template_unsupported_variables"):
        return (
            "Șablonul ales conține variabile nepermise. "
            "Verifică textul din secțiunea Șabloane și reia."
        )
    if code == "template_owner_mismatch":
        return "Șablonul ales aparține altui cont. Alege un șablon propriu din secțiunea Șabloane."

    messages = {
        "reminder_not_due": (
            "Reminderul nu este încă disponibil sau cele două runde au fost trimise."
        ),
        "no_active_assignments": "Participantul nu are sarcini active pentru acest proiect.",
        "project_not_open": "Chestionarele proiectului nu sunt încă deschise.",
        "project_closed": "Perioada de completare a proiectului s-a încheiat.",
        "profile_not_found": "Participantul nu mai este disponibil în acest proiect.",
    }
    return messages.get(
        code,
        "Invitația nu a putut fi pregătită din cauza configurării șablonului. "
        "Verifică secțiunea Șabloane.",
    )


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
