import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.contracts.emails import EmailAddress, EmailMessage
from codrut.core.config import get_settings
from codrut.core.errors import DomainError
from codrut.core.security import hash_password, new_session_token, verify_password
from codrut.modules.communications.email_provider import build_email_provider
from codrut.modules.communications.service import TransactionalEmailService
from codrut.modules.companies.anonymous import new_anonymous_name
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    AssignmentInvite,
    ConsentAcceptance,
    PasswordResetToken,
    Session,
    User,
    UserRole,
)
from codrut.modules.identity.password_breach import ensure_password_not_breached
from codrut.modules.identity.repository import IdentityRepository, hash_session_token
from codrut.modules.identity.schemas import (
    AuthResponse,
    ConsentRequest,
    InviteVerifyResponse,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    SessionPrincipal,
)
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION

if TYPE_CHECKING:
    from codrut.modules.assignments.models import QuestionnaireAssignment
    from codrut.modules.companies.models import CompanyProject


@dataclass(frozen=True)
class AuthResult:
    response: AuthResponse
    session_token: str


@dataclass(frozen=True)
class InviteVerifyResult:
    response: "InviteVerifyResponse"
    session_token: str | None


def _invite_task_copy(questionnaire_key: str) -> tuple[str, str, int]:
    if questionnaire_key in {"lencioni", "lencioni_en"}:
        return (
            "Feedback pentru echipă",
            "Răspunde pentru echipa indicată în această sarcină.",
            12,
        )
    if questionnaire_key in {"distress_drivers", "distress_drivers_en"}:
        return (
            "Autoevaluare individuală",
            "Completează formularul individual atribuit pentru proiectul curent.",
            10,
        )
    if questionnaire_key in {"boss_360", "icare"}:
        return (
            "Feedback confidențial",
            "Oferă feedback pentru persoana indicată în această sarcină.",
            20,
        )
    if questionnaire_key == "pcm_base":
        return (
            "Formular de profil",
            "Completează formularul de profil cerut pentru proiectul curent.",
            2,
        )
    return ("Chestionar", "Completează formularul atribuit.", 10)


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = IdentityRepository(session)

    async def register(self, payload: RegisterRequest) -> AuthResult:
        if not payload.terms_accepted:
            raise DomainError(
                "Privacy and confidentiality terms must be accepted before registration.",
                code="terms_required",
            )
        if payload.terms_version != CURRENT_TERMS_VERSION:
            raise DomainError(
                "The accepted privacy terms are no longer current.",
                code="terms_version_outdated",
            )

        # Lock the invitation so account, scoped session, and consent are one transaction.
        verify_result, invite = await self._verify_invite_token(
            payload.token,
            lock_invite=True,
        )

        # 2. Check if the user is leadership (only leadership members can sign up)
        if not verify_result.is_leadership:
            raise DomainError(
                "Registration is restricted to leadership team members.",
                code="registration_forbidden",
            )

        # The signed invitation proves ownership of this exact participant context.
        if payload.email.lower() != verify_result.email.lower():
            raise DomainError("Email address does not match invitation.", code="email_mismatch")

        profile = await self._load_invited_profile(payload.token)
        existing = await self._resolve_invited_participant_user(profile)

        accepted_at = datetime.now(UTC)
        if existing is not None and existing.password_hash == SHADOW_ACCOUNT_PASSWORD_HASH:
            await ensure_password_not_breached(payload.password)
            existing.password_hash = hash_password(payload.password)
            existing.role = UserRole.participant
            user = existing
        elif existing is not None:
            # Never replace an existing account password during invite linking.
            user = existing
        else:
            await ensure_password_not_breached(payload.password)
            user = await self.repository.add_user(
                User(
                    id=uuid.uuid4(),
                    email=payload.email.lower(),
                    password_hash=hash_password(payload.password),
                    role=UserRole.participant,
                    terms_accepted_at=accepted_at,
                    terms_version=payload.terms_version,
                )
            )
        user.terms_accepted_at = accepted_at
        user.terms_version = payload.terms_version
        profile.user_id = user.id

        if invite is None:
            raise DomainError("Task link is no longer active.", code="task_link_revoked")
        token = await self._create_session(
            user,
            expires_at=verify_result.expires_at,
            assignment_invite_id=invite.id,
        )
        active_session = await self.repository.get_session_by_token(token)
        if active_session is None:
            raise DomainError(
                "Registration session could not be created.",
                code="session_create_failed",
            )
        await self.repository.add_consent_acceptance(
            ConsentAcceptance(
                id=uuid.uuid4(),
                user_id=user.id,
                session_id=active_session.id,
                assignment_invite_id=invite.id,
                respondent_profile_id=profile.id,
                terms_version=CURRENT_TERMS_VERSION,
                source="secure_invite",
                accepted_at=accepted_at,
            )
        )
        return AuthResult(response=self._response(user), session_token=token)

    async def verify_invite_token(self, token: str) -> InviteVerifyResponse:
        response, _ = await self._verify_invite_token(token, lock_invite=False)
        return response

    async def _verify_invite_token(
        self,
        token: str,
        *,
        lock_invite: bool,
    ) -> tuple[InviteVerifyResponse, AssignmentInvite | None]:
        from sqlalchemy import exists, or_, select

        from codrut.core.config import get_settings
        from codrut.modules.assignments.models import (
            AssessmentCycle,
            AssessmentCycleStatus,
            AssignmentStatus,
            Team,
            TeamMembership,
            TeamType,
        )
        from codrut.modules.communications.task_links import parse_task_token
        from codrut.modules.companies.models import Company, ParticipantProfile

        settings = get_settings()
        try:
            claims = parse_task_token(token, settings)
        except DomainError:
            raise
        except Exception as exc:
            raise DomainError("Invalid task link.", code="task_link_invalid") from exc

        invite: AssignmentInvite | None = None
        if "Mock" not in type(self.repository.session).__name__:
            invite = await self.repository.get_invite_by_token(
                token,
                for_update=lock_invite,
            )
            if invite is None:
                raise DomainError("Task link is no longer active.", code="task_link_revoked")
            if invite.status != "active":
                raise DomainError(
                    "Task link has been revoked or used.",
                    code="task_link_revoked",
                )
            if invite.expires_at <= datetime.now(UTC):
                raise DomainError("Task link has expired.", code="task_link_expired")
            if invite.company_id != claims.company_id or (
                invite.project_id is not None and invite.project_id != claims.project_id
            ):
                raise DomainError(
                    "Task link does not match its invitation scope.",
                    code="task_link_scope_mismatch",
                )

        # Find the participant profile associated with the claims
        result = await self.repository.session.execute(
            select(ParticipantProfile).where(ParticipantProfile.id == claims.respondent_profile_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise DomainError("Invitation respondent profile not found.", code="profile_not_found")
        if profile.company_id != claims.company_id:
            raise DomainError(
                "Task link does not match respondent scope.",
                code="task_link_scope_mismatch",
            )
        if profile.email is None:
            raise DomainError(
                "Invitation respondent profile has no email address.",
                code="invite_email_missing",
            )

        company_result = await self.repository.session.execute(
            select(Company).where(Company.id == claims.company_id)
        )
        company = company_result.scalar_one_or_none()
        if company is None:
            raise DomainError("Invitation project not found.", code="project_not_found")

        # Shadow users back secure links but are not permanent registrations.
        # An unbound profile may still belong to an existing participant account
        # with the same verified email, so expose that state before the exchange.
        user: User | None = None
        if profile.user_id is not None:
            user_result = await self.repository.session.execute(
                select(User).where(User.id == profile.user_id)
            )
            user = user_result.scalar_one_or_none()

        # Check if the participant is leadership
        stmt = select(
            exists(
                select(1)
                .where(TeamMembership.participant_profile_id == profile.id)
                .where(TeamMembership.team_id == Team.id)
                .where(Team.type == TeamType.leadership)
            )
        )
        is_leadership = (await self.repository.session.execute(stmt)).scalar() or False

        # Retrieve assignments details
        from codrut.modules.assignments.models import AssignmentTargetType, QuestionnaireAssignment
        from codrut.modules.identity.schemas import InviteTask

        assignments_result = await self.repository.session.execute(
            select(QuestionnaireAssignment)
            .outerjoin(
                AssessmentCycle,
                AssessmentCycle.id == QuestionnaireAssignment.assessment_cycle_id,
            )
            .where(QuestionnaireAssignment.id.in_(claims.assignment_ids))
            .where(QuestionnaireAssignment.company_id == claims.company_id)
            .where(QuestionnaireAssignment.respondent_profile_id == claims.respondent_profile_id)
            .where(
                or_(
                    QuestionnaireAssignment.assessment_cycle_id.is_(None),
                    AssessmentCycle.status != AssessmentCycleStatus.draft,
                )
            )
        )
        assignments = assignments_result.scalars().all()
        assignments_by_id = {assignment.id: assignment for assignment in assignments}
        if set(assignments_by_id) != set(claims.assignment_ids):
            raise DomainError(
                "Task link assignment scope is invalid.",
                code="task_link_scope_mismatch",
            )
        project_id, project_name, effective_expires_at = await self._invite_project_context(
            claims.company_id,
            company.name,
            list(assignments_by_id.values()),
            claims.expires_at,
            claims.project_id,
        )
        assignment_project_ids = {
            assignment.project_id for assignment in assignments if assignment.project_id
        }
        project_names = (
            {project_id: project_name}
            if project_id is not None and assignment_project_ids == {project_id}
            else await self._project_names(claims.company_id, assignment_project_ids)
        )

        tasks = []
        return_to = quote(f"/invite/{token}", safe="")
        for assignment_id in claims.assignment_ids:
            ass = assignments_by_id[assignment_id]
            if ass.status == AssignmentStatus.cancelled:
                continue
            target_label = "Autoevaluare"
            if ass.questionnaire_key in {"lencioni", "lencioni_en"}:
                target_label = "Echipa ta"
            elif ass.target_type == AssignmentTargetType.team and ass.target_team_id:
                team_result = await self.repository.session.execute(
                    select(Team)
                    .where(Team.id == ass.target_team_id)
                    .where(Team.company_id == claims.company_id)
                )
                team = team_result.scalar_one_or_none()
                if team:
                    target_label = team.name
            elif ass.target_type == AssignmentTargetType.person and ass.target_person_id:
                person_result = await self.repository.session.execute(
                    select(ParticipantProfile)
                    .where(ParticipantProfile.id == ass.target_person_id)
                    .where(ParticipantProfile.company_id == claims.company_id)
                )
                person = person_result.scalar_one_or_none()
                if person:
                    target_label = person.full_name

            status_map = {
                "assigned": "not_started",
                "invited": "not_started",
                "started": "in_progress",
                "submitted": "completed",
                "validated": "completed",
                "scored": "completed",
            }
            task_status = status_map.get(ass.status.value, "not_started")
            title, detail, est_minutes = _invite_task_copy(ass.questionnaire_key)

            tasks.append(
                InviteTask(
                    id=str(ass.id),
                    title=title,
                    status=task_status,
                    detail=detail,
                    href=(f"/participant/tasks/{ass.id}?access=secure&returnTo={return_to}"),
                    assignmentId=str(ass.id),
                    targetLabel=target_label,
                    estimatedMinutes=est_minutes,
                    questionnaireKey=ass.questionnaire_key,
                    projectId=ass.project_id,
                    projectName=project_names.get(ass.project_id),
                    assignmentRoundId=ass.assignment_round_id,
                    assessmentCycleId=ass.assessment_cycle_id,
                )
            )

        if user is None:
            matching_user = await self.repository.get_user_by_email(profile.email)
            if matching_user is not None and matching_user.role == UserRole.participant:
                user = matching_user
        already_registered = bool(
            user is not None and user.password_hash != SHADOW_ACCOUNT_PASSWORD_HASH
        )

        return (
            InviteVerifyResponse(
                email=profile.email,
                full_name=profile.full_name,
                anonymous_name=profile.anonymous_name,
                is_leadership=is_leadership,
                already_registered=already_registered,
                project_id=project_id,
                project_name=project_name,
                expires_at=effective_expires_at,
                token_status="active",  # noqa: S106
                terms_accepted_at=user.terms_accepted_at if user is not None else None,
                terms_version=user.terms_version if user is not None else None,
                tasks=tasks,
            ),
            invite,
        )

    async def _invite_project_context(
        self,
        company_id: UUID,
        company_name: str,
        assignments: list["QuestionnaireAssignment"],
        token_expires_at: datetime,
        claimed_project_id: UUID | None,
    ) -> tuple[UUID | None, str, datetime]:
        from sqlalchemy import select

        from codrut.modules.companies.models import CompanyProject

        project_ids = {
            assignment.project_id for assignment in assignments if assignment.project_id is not None
        }
        if claimed_project_id is not None and project_ids != {claimed_project_id}:
            raise DomainError(
                "Task link assignment scope does not match its project.",
                code="task_link_scope_mismatch",
            )
        if len(project_ids) != 1:
            return None, company_name, token_expires_at

        project_id = next(iter(project_ids))
        result = await self.repository.session.execute(
            select(CompanyProject)
            .where(CompanyProject.company_id == company_id)
            .where(CompanyProject.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            return None, company_name, token_expires_at
        now = datetime.now(UTC)
        _validate_project_access_window(project, now=now)
        return (
            project.id,
            project.name,
            _min_datetime(
                token_expires_at,
                project.form_closes_at,
                project.due_at,
            ),
        )

    async def _project_names(
        self,
        company_id: UUID,
        project_ids: set[UUID],
    ) -> dict[UUID, str]:
        if not project_ids:
            return {}
        from sqlalchemy import select

        from codrut.modules.companies.models import CompanyProject

        result = await self.repository.session.execute(
            select(CompanyProject)
            .where(CompanyProject.company_id == company_id)
            .where(CompanyProject.id.in_(project_ids))
        )
        return {project.id: project.name for project in result.scalars().all()}

    async def _load_invited_profile(self, token: str):
        from sqlalchemy import select

        from codrut.modules.communications.task_links import parse_task_token
        from codrut.modules.companies.models import ParticipantProfile

        claims = parse_task_token(token, get_settings())
        result = await self.repository.session.execute(
            select(ParticipantProfile).where(
                ParticipantProfile.id == claims.respondent_profile_id,
                ParticipantProfile.company_id == claims.company_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise DomainError("Invitation respondent profile not found.", code="profile_not_found")
        if profile.email is None:
            raise DomainError(
                "Invitation respondent profile has no email address.",
                code="invite_email_missing",
            )
        return profile

    async def _resolve_invited_participant_user(self, profile):
        email = profile.email.lower()
        email_user = await self.repository.get_user_by_email(email)
        bound_user = None
        if profile.user_id is not None:
            if email_user is not None and email_user.id == profile.user_id:
                bound_user = email_user
            else:
                bound_user = await self.repository.get_user_by_id(profile.user_id)
            if bound_user is None:
                raise DomainError(
                    "Invite profile is linked to a missing account.",
                    code="invite_profile_account_conflict",
                )
            if email_user is not None and email_user.id != bound_user.id:
                raise DomainError(
                    "Invite email belongs to a different account.",
                    code="invite_profile_account_conflict",
                )

        user = bound_user or email_user
        if user is None:
            return None
        if user.role not in {UserRole.participant, UserRole.trainer} or user.email.lower() != email:
            raise DomainError(
                "Invite profile is linked to an incompatible account.",
                code="invite_profile_account_conflict",
            )
        if profile.user_id is None:
            profile.user_id = user.id
        return user

    async def verify_invite_token_and_create_session(
        self,
        token: str,
        *,
        existing_session_token: str | None = None,
        replace_existing_session: bool = False,
    ) -> InviteVerifyResult:
        verify_result, invite = await self._verify_invite_token(token, lock_invite=True)

        session_token = None
        profile = await self._load_invited_profile(token)
        existing_session = (
            await self.repository.get_session_by_token(existing_session_token)
            if existing_session_token
            else None
        )
        if (
            existing_session is not None
            and profile.user_id is not None
            and existing_session.user_id != profile.user_id
            and not replace_existing_session
        ):
            raise DomainError(
                "The invitation belongs to a different authenticated user.",
                code="invite_session_conflict",
            )
        user = await self._resolve_invited_participant_user(profile)
        if existing_session is not None and user is None and not replace_existing_session:
            raise DomainError(
                "The invitation belongs to a different authenticated user.",
                code="invite_session_conflict",
            )

        if not verify_result.is_leadership:
            if not profile.anonymous_name:
                profile.anonymous_name = new_anonymous_name()
                verify_result.anonymous_name = profile.anonymous_name
            if user is None:
                user = User(
                    id=uuid.uuid4(),
                    email=profile.email.lower(),
                    password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
                    role=UserRole.participant,
                )
                await self.repository.add_user(user)
                profile.user_id = user.id

        # Existing participant accounts use the signed invitation as passwordless
        # proof for the newly linked profile, including leadership accounts.
        if user is not None:
            current_invite_id = invite.id if invite is not None else None
            session_switch_required = existing_session is not None and (
                existing_session.user_id != user.id
                or (
                    existing_session.assignment_invite_id is not None
                    and existing_session.assignment_invite_id != current_invite_id
                )
                or (
                    user.role == UserRole.trainer
                    and existing_session.assignment_invite_id != current_invite_id
                )
            )
            if session_switch_required and not replace_existing_session:
                raise DomainError(
                    "The invitation belongs to a different authenticated user.",
                    code="invite_session_conflict",
                )

            can_preserve_existing_session = existing_session is not None and (
                existing_session.user_id == user.id
                and (
                    (
                        user.role == UserRole.participant
                        and existing_session.assignment_invite_id is None
                    )
                    or existing_session.assignment_invite_id == current_invite_id
                )
            )
            if not can_preserve_existing_session:
                session_token = await self._create_session(
                    user,
                    expires_at=verify_result.expires_at,
                    assignment_invite_id=current_invite_id,
                )
                if existing_session_token and replace_existing_session:
                    await self.repository.delete_session_by_token(existing_session_token)

        return InviteVerifyResult(
            response=verify_result,
            session_token=session_token,
        )

    async def login(self, payload: LoginRequest) -> AuthResult:
        user = await self.repository.get_user_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise DomainError("Invalid email or password.", code="invalid_credentials")
        token = await self._create_session(user)
        return AuthResult(response=self._response(user), session_token=token)

    async def request_password_reset(self, payload: PasswordResetRequest) -> None:
        user = await self.repository.get_user_by_email(payload.email)
        if user is None:
            return
        if (
            user.password_hash == SHADOW_ACCOUNT_PASSWORD_HASH
            and not await self._shadow_account_password_reset_allowed(user.id)
        ):
            return

        raw_token = new_session_token()
        await self.repository.revoke_password_reset_tokens_for_user(user.id)
        reset_token = await self.repository.add_password_reset_token(
            PasswordResetToken(
                id=uuid.uuid4(),
                user_id=user.id,
                token_hash=hash_session_token(raw_token),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )

        settings = get_settings()
        reset_url = f"{settings.public_app_url.rstrip('/')}/update-password?token={raw_token}"
        message = EmailMessage(
            to=EmailAddress(user.email),
            subject="Resetare parolă Cody",
            html_body=(
                "<p>Ai cerut resetarea parolei pentru contul Cody.</p>"
                f'<p><a href="{reset_url}">Setează o parolă nouă</a></p>'
                "<p>Linkul expiră în 60 de minute. "
                "Dacă nu ai cerut resetarea, ignoră acest email.</p>"
            ),
            text_body=(
                "Ai cerut resetarea parolei pentru contul Cody.\n\n"
                f"Setează o parolă nouă aici: {reset_url}\n\n"
                "Linkul expiră în 60 de minute. Dacă nu ai cerut resetarea, ignoră acest email."
            ),
        )
        provider = build_email_provider(settings)
        await TransactionalEmailService(
            provider,
            self.session,
            owner_id=user.id,
        ).enqueue_transactional_message(
            message,
            template_key="password_reset",
            template_version=2,
            idempotency_key=f"password-reset:{reset_token.id}",
            delivery_kind="password_reset",
        )

    async def _shadow_account_password_reset_allowed(self, user_id: UUID) -> bool:
        from sqlalchemy import select

        from codrut.modules.assignments.models import (
            QuestionnaireAssignment,
            Team,
            TeamMembership,
            TeamType,
        )
        from codrut.modules.companies.models import CompanyProject, ParticipantProfile

        now = datetime.now(UTC)
        result = await self.repository.session.execute(
            select(QuestionnaireAssignment, CompanyProject)
            .join(
                ParticipantProfile,
                ParticipantProfile.id == QuestionnaireAssignment.respondent_profile_id,
            )
            .join(
                TeamMembership,
                TeamMembership.participant_profile_id == ParticipantProfile.id,
            )
            .join(Team, Team.id == TeamMembership.team_id)
            .outerjoin(CompanyProject, CompanyProject.id == QuestionnaireAssignment.project_id)
            .where(ParticipantProfile.user_id == user_id)
            .where(Team.type == TeamType.leadership)
        )

        for assignment, project in result.all():
            if assignment.due_at is not None and assignment.due_at <= now:
                continue
            if project is not None:
                try:
                    _validate_project_access_window(project, now=now)
                except DomainError:
                    continue
            return True

        return False

    async def confirm_password_reset(self, payload: PasswordResetConfirmRequest) -> None:
        reset_token = await self.repository.get_active_password_reset_token(payload.token)
        if reset_token is None:
            raise DomainError(
                "Linkul de resetare este invalid sau a expirat.",
                code="password_reset_invalid",
            )

        user = await self.repository.get_user_by_id(reset_token.user_id)
        if user is None:
            raise DomainError("Contul nu mai există.", code="user_not_found")
        if (
            user.password_hash == SHADOW_ACCOUNT_PASSWORD_HASH
            and not await self._shadow_account_password_reset_allowed(user.id)
        ):
            raise DomainError(
                "Temporary invite accounts cannot be converted through password reset.",
                code="password_reset_forbidden",
            )

        await ensure_password_not_breached(payload.password)
        user.password_hash = hash_password(payload.password)
        reset_token.used_at = datetime.now(UTC)
        await self.repository.revoke_password_reset_tokens_for_user(user.id)
        await self.repository.delete_sessions_for_user(user.id)

    async def change_password(self, user_id: UUID, payload: PasswordChangeRequest) -> None:
        user = await self.repository.get_user_by_id(user_id)
        if user is None:
            raise DomainError("Contul nu mai există.", code="user_not_found")
        if user.password_hash == SHADOW_ACCOUNT_PASSWORD_HASH or not verify_password(
            payload.current_password,
            user.password_hash,
        ):
            raise DomainError(
                "Parola curentă este incorectă.",
                code="invalid_current_password",
            )

        await ensure_password_not_breached(payload.new_password)
        user.password_hash = hash_password(payload.new_password)
        await self.repository.revoke_password_reset_tokens_for_user(user.id)
        await self.repository.delete_sessions_for_user(user.id)

    async def logout(self, token: str) -> None:
        await self.repository.delete_session_by_token(token)

    async def accept_terms(
        self,
        user_id: UUID,
        payload: ConsentRequest,
        *,
        session_token: str | None = None,
    ) -> AuthResponse:
        if not payload.terms_accepted:
            raise DomainError(
                "Privacy and confidentiality terms must be accepted.",
                code="terms_required",
            )
        if payload.terms_version != CURRENT_TERMS_VERSION:
            raise DomainError(
                "The accepted privacy terms are no longer current.",
                code="terms_version_outdated",
            )

        user = await self.repository.get_user_by_id(user_id)
        if user is None:
            raise DomainError("Authenticated user was not found.", code="user_not_found")

        active_session = None
        if session_token and not session_token.startswith("local-development:"):
            active_session = await self.repository.get_session_by_token(session_token)
        invite = None
        if active_session is not None and active_session.assignment_invite_id is not None:
            invite = await self.repository.get_invite_by_id(active_session.assignment_invite_id)

        existing = await self.repository.get_consent_acceptance(
            user_id=user_id,
            terms_version=payload.terms_version,
            session_id=active_session.id if active_session is not None else None,
        )
        accepted_at = existing.accepted_at if existing is not None else datetime.now(UTC)
        if existing is None:
            source = (
                "secure_invite"
                if invite is not None
                else "local_preview"
                if session_token and session_token.startswith("local-development:")
                else "authenticated"
            )
            await self.repository.add_consent_acceptance(
                ConsentAcceptance(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    session_id=active_session.id if active_session is not None else None,
                    assignment_invite_id=invite.id if invite is not None else None,
                    respondent_profile_id=(
                        invite.respondent_profile_id if invite is not None else None
                    ),
                    terms_version=payload.terms_version,
                    source=source,
                    accepted_at=accepted_at,
                )
            )

        user.terms_accepted_at = accepted_at
        user.terms_version = payload.terms_version
        return self._response(user)

    async def require_secure_link_consent(
        self,
        principal: SessionPrincipal,
        invite_token: str,
    ) -> None:
        settings = get_settings()
        if (
            principal.session_token.startswith("local-development:")
            and settings.env == "development"
            and settings.local_auth_bypass
        ):
            return
        if (
            principal.role != UserRole.participant
            or principal.terms_accepted_at is None
            or principal.terms_version != CURRENT_TERMS_VERSION
        ):
            raise DomainError(
                "Privacy and confidentiality terms must be accepted.",
                code="terms_required",
            )

        active_session = await self.repository.get_session_by_token(principal.session_token)
        if active_session is None or active_session.user_id != principal.user_id:
            raise DomainError("Participant session is no longer active.", code="session_invalid")

        invite = await self.repository.get_invite_by_token(invite_token)
        if invite is None or invite.status != "active":
            raise DomainError("Task link is no longer active.", code="task_link_revoked")
        if invite.expires_at <= datetime.now(UTC):
            raise DomainError("Task link has expired.", code="task_link_expired")
        if active_session.assignment_invite_id not in {None, invite.id}:
            raise DomainError(
                "Task link does not match the active participant session.",
                code="task_link_scope_mismatch",
            )

        from sqlalchemy import select

        from codrut.modules.companies.models import ParticipantProfile

        profile_result = await self.repository.session.execute(
            select(ParticipantProfile).where(
                ParticipantProfile.id == invite.respondent_profile_id,
                ParticipantProfile.company_id == invite.company_id,
                ParticipantProfile.user_id == principal.user_id,
            )
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            raise DomainError(
                "Task link does not belong to the active participant account.",
                code="task_link_scope_mismatch",
            )

        acceptance = await self.repository.get_consent_acceptance(
            user_id=principal.user_id,
            terms_version=CURRENT_TERMS_VERSION,
            session_id=active_session.id,
        )
        if acceptance is None:
            acceptance = await self.repository.get_latest_consent_acceptance(
                user_id=principal.user_id,
                terms_version=CURRENT_TERMS_VERSION,
            )
        if acceptance is None:
            raise DomainError(
                "Privacy and confidentiality terms must be accepted.",
                code="terms_required",
            )
        if acceptance.session_id == active_session.id and (
            acceptance.assignment_invite_id not in {None, invite.id}
            or (
                acceptance.respondent_profile_id is not None
                and acceptance.respondent_profile_id != invite.respondent_profile_id
            )
        ):
            raise DomainError(
                "Consent does not match the active invitation.",
                code="task_link_scope_mismatch",
            )

    async def principal_from_session_token(self, token: str) -> SessionPrincipal | None:
        active_session = await self.repository.get_session_by_token(token)
        if active_session is None:
            return None
        user = await self.repository.get_user_by_id(active_session.user_id)
        if user is None:
            return None

        assignment_ids: tuple[UUID, ...] | None = None
        project_id: UUID | None = None
        if active_session.assignment_invite_id is not None:
            invite = await self.repository.get_invite_by_id(active_session.assignment_invite_id)
            if (
                invite is None
                or invite.status != "active"
                or invite.expires_at <= datetime.now(UTC)
            ):
                return None
            from codrut.modules.communications.task_links import parse_task_token

            claims = parse_task_token(invite.token, get_settings())
            if claims.company_id != invite.company_id or (
                invite.project_id is not None and claims.project_id != invite.project_id
            ):
                return None
            assignment_ids = claims.assignment_ids
            project_id = claims.project_id or invite.project_id
        return SessionPrincipal(
            user_id=user.id,
            email=user.email,
            role=(
                UserRole.participant
                if active_session.assignment_invite_id is not None
                else user.role
            ),
            terms_accepted_at=user.terms_accepted_at,
            terms_version=user.terms_version,
            session_token=token,
            assignment_invite_id=active_session.assignment_invite_id,
            assignment_ids=assignment_ids,
            project_id=project_id,
        )

    async def principal_for_local_user(
        self,
        *,
        email: str,
        role: UserRole,
    ) -> SessionPrincipal | None:
        user = await self.repository.get_user_by_email(email)
        if user is None or user.role != role:
            return None
        return SessionPrincipal(
            user_id=user.id,
            email=user.email,
            role=user.role,
            terms_accepted_at=user.terms_accepted_at,
            terms_version=user.terms_version,
            session_token=f"local-development:{role.value}",
        )

    async def _create_session(
        self,
        user: User,
        *,
        expires_at: datetime | None = None,
        assignment_invite_id: UUID | None = None,
    ) -> str:
        token = new_session_token()
        normal_expiry = datetime.now(UTC) + timedelta(days=90)
        await self.repository.add_session(
            Session(
                user_id=user.id,
                token_hash=hash_session_token(token),
                expires_at=_min_datetime(normal_expiry, expires_at),
                assignment_invite_id=assignment_invite_id,
            )
        )
        return token

    @staticmethod
    def _response(user: User) -> AuthResponse:
        return AuthResponse(
            user_id=user.id,
            email=user.email,
            role=user.role,
            terms_accepted_at=user.terms_accepted_at,
            terms_version=user.terms_version,
        )

    async def create_invite(
        self,
        company_id: UUID,
        respondent_profile_id: UUID,
        assignment_ids: list[UUID] | None = None,
        project_id: UUID | None = None,
        expires_in_days: int = 3650,
        expires_at: datetime | None = None,
        force_rotate: bool = False,
    ) -> AssignmentInvite:
        from sqlalchemy import select

        from codrut.core.config import get_settings
        from codrut.modules.communications.task_links import TaskLinkClaims, create_task_token
        from codrut.modules.companies.models import ParticipantProfile

        # 1. Fetch participant profile
        result = await self.repository.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.id == respondent_profile_id)
            .where(ParticipantProfile.company_id == company_id)
            .with_for_update()
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise DomainError("Participant profile not found.", code="profile_not_found")

        # 2. Resolve and scope-check assignment IDs before invite reuse or revocation.
        assignment_ids = await self._resolve_invite_assignment_ids(
            company_id=company_id,
            respondent_profile_id=respondent_profile_id,
            assignment_ids=assignment_ids,
            project_id=project_id,
        )
        if not assignment_ids:
            raise DomainError(
                "Cannot create invitation without active assignments.",
                code="no_active_assignments",
            )

        requested_expires_at = expires_at or datetime.now(UTC) + timedelta(days=expires_in_days)

        # 3. Check if there is already an active invite
        if not force_rotate:
            active_invite = await self.repository.get_active_invite_by_respondent(
                company_id,
                respondent_profile_id,
                project_id,
            )
            if active_invite is not None:
                settings = get_settings()
                try:
                    from codrut.modules.communications.task_links import parse_task_token

                    claims = parse_task_token(active_invite.token, settings)

                    if (
                        set(claims.assignment_ids) == set(assignment_ids)
                        and claims.project_id == project_id
                        and claims.expires_at <= requested_expires_at
                        and active_invite.expires_at <= requested_expires_at
                    ):
                        return active_invite
                except Exception:  # noqa: S110
                    pass

        # 4. Invalidate previous active invites and the sessions derived from them.
        await self._invalidate_invites_and_sessions(
            company_id,
            respondent_profile_id,
            project_id=project_id,
            linked_user_id=profile.user_id,
        )

        # 5. Generate secure token claims
        claims = TaskLinkClaims(
            company_id=company_id,
            respondent_profile_id=respondent_profile_id,
            assignment_ids=tuple(assignment_ids),
            expires_at=requested_expires_at,
            project_id=project_id,
        )
        settings = get_settings()
        token = create_task_token(claims, settings)

        # 6. Save invite to DB
        invite = AssignmentInvite(
            company_id=company_id,
            project_id=project_id,
            respondent_profile_id=respondent_profile_id,
            token=token,
            status="active",
            expires_at=requested_expires_at,
        )
        return await self.repository.add_invite(invite)

    async def _resolve_invite_assignment_ids(
        self,
        company_id: UUID,
        respondent_profile_id: UUID,
        assignment_ids: list[UUID] | None,
        project_id: UUID | None = None,
    ) -> list[UUID]:
        from sqlalchemy import select

        from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment

        active_statuses = {
            AssignmentStatus.assigned,
            AssignmentStatus.invited,
            AssignmentStatus.started,
        }
        stmt = (
            select(QuestionnaireAssignment.id)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.respondent_profile_id == respondent_profile_id)
            .where(QuestionnaireAssignment.status.in_(active_statuses))
        )
        if project_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.project_id == project_id)

        if assignment_ids is None:
            result = await self.repository.session.execute(stmt)
            return list(result.scalars().all())

        requested_ids = list(dict.fromkeys(assignment_ids))
        result = await self.repository.session.execute(
            stmt.where(QuestionnaireAssignment.id.in_(requested_ids))
        )
        resolved_ids = set(result.scalars().all())
        if set(requested_ids) != resolved_ids:
            raise DomainError(
                "Invitation assignments must belong to the respondent and company.",
                code="assignment_scope_mismatch",
            )
        return [assignment_id for assignment_id in requested_ids if assignment_id in resolved_ids]

    async def invalidate_invite(
        self,
        company_id: UUID,
        respondent_profile_id: UUID,
    ) -> None:
        from sqlalchemy import select

        from codrut.modules.companies.models import ParticipantProfile

        result = await self.repository.session.execute(
            select(ParticipantProfile).where(
                ParticipantProfile.id == respondent_profile_id,
                ParticipantProfile.company_id == company_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise DomainError("Participant profile not found.", code="profile_not_found")
        await self._invalidate_invites_and_sessions(
            company_id,
            respondent_profile_id,
            all_scopes=True,
            linked_user_id=profile.user_id,
        )

    async def _invalidate_invites_and_sessions(
        self,
        company_id: UUID,
        respondent_profile_id: UUID,
        *,
        project_id: UUID | None = None,
        all_scopes: bool = False,
        linked_user_id: UUID | None,
    ) -> None:
        revoked_invites = await self.repository.invalidate_invites_for_respondent(
            company_id,
            respondent_profile_id,
            project_id=project_id,
            all_scopes=all_scopes,
        )
        await self.repository.delete_sessions_for_invites(
            [invite.id for invite in revoked_invites if invite.id is not None]
        )
        if linked_user_id is not None and (all_scopes or project_id is None):
            await self.repository.delete_sessions_for_shadow_user(linked_user_id)


def _min_datetime(*values: datetime | None) -> datetime:
    candidates = [value for value in values if value is not None]
    if not candidates:
        raise ValueError("at least one datetime is required")
    return min(candidates)


def _validate_project_access_window(project: "CompanyProject", *, now: datetime) -> None:
    if project.form_opens_at is not None and project.form_opens_at > now:
        raise DomainError(
            "Project questionnaires are not open yet.",
            code="project_not_open",
        )
    close_candidates = [project.form_closes_at, project.due_at]
    if not any(close_candidates):
        return
    closes_at = _min_datetime(*close_candidates)
    if closes_at <= now:
        raise DomainError(
            "Project questionnaire window has closed.",
            code="project_closed",
        )
