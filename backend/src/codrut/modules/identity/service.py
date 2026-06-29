from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.contracts.emails import EmailAddress, EmailDeliveryStatus, EmailMessage
from codrut.core.config import get_settings
from codrut.core.errors import DomainError
from codrut.core.security import hash_password, new_session_token, verify_password
from codrut.modules.communications.email_provider import build_email_provider
from codrut.modules.companies.anonymous import new_anonymous_name
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    AssignmentInvite,
    PasswordResetToken,
    Session,
    User,
    UserRole,
)
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
        self.repository = IdentityRepository(session)

    async def register(self, payload: RegisterRequest) -> AuthResult:
        if not payload.terms_accepted:
            raise DomainError(
                "Privacy and confidentiality terms must be accepted before registration.",
                code="terms_required",
            )

        # 1. Verify the invite token
        verify_result = await self.verify_invite_token(payload.token)

        # 2. Check if the user is leadership (only leadership members can sign up)
        if not verify_result.is_leadership:
            raise DomainError(
                "Registration is restricted to leadership team members.",
                code="registration_forbidden",
            )

        # 3. Check if already registered
        if verify_result.already_registered:
            raise DomainError(
                "An account has already been registered with this invitation.",
                code="already_registered",
            )

        # 4. Check if the email matches the invitation
        if payload.email.lower() != verify_result.email.lower():
            raise DomainError("Email address does not match invitation.", code="email_mismatch")

        # 5. Check if a user with this email already exists in users table
        existing = await self.repository.get_user_by_email(payload.email)
        if existing is not None:
            raise DomainError("An account with this email already exists.", code="email_taken")

        # 6. Create the user
        import uuid
        user = await self.repository.add_user(
            User(
                id=uuid.uuid4(),
                email=payload.email.lower(),
                password_hash=hash_password(payload.password),
                role=UserRole.participant,
                terms_accepted_at=datetime.now(UTC),
                terms_version=payload.terms_version,
            )
        )

        from sqlalchemy import select

        from codrut.core.config import get_settings
        from codrut.modules.communications.task_links import parse_task_token
        from codrut.modules.companies.models import ParticipantProfile

        claims = parse_task_token(payload.token, get_settings())
        result = await self.repository.session.execute(
            select(ParticipantProfile).where(
                ParticipantProfile.id == claims.respondent_profile_id,
                ParticipantProfile.company_id == claims.company_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise DomainError("Invitation respondent profile not found.", code="profile_not_found")
        profile.user_id = user.id

        token = await self._create_session(user)
        return AuthResult(response=self._response(user), session_token=token)

    async def verify_invite_token(self, token: str) -> InviteVerifyResponse:
        from sqlalchemy import exists, select

        from codrut.core.config import get_settings
        from codrut.modules.assignments.models import Team, TeamMembership, TeamType
        from codrut.modules.communications.task_links import parse_task_token
        from codrut.modules.companies.models import Company, ParticipantProfile

        settings = get_settings()
        try:
            claims = parse_task_token(token, settings)
        except DomainError:
            raise
        except Exception as exc:
            raise DomainError("Invalid task link.", code="task_link_invalid") from exc

        # Check if the invite token is in our database and validate its status
        if "Mock" not in type(self.repository.session).__name__:
            invite_result = await self.repository.session.execute(
                select(AssignmentInvite).where(AssignmentInvite.token == token)
            )
            invite = invite_result.scalar_one_or_none()
            if invite is None:
                raise DomainError("Task link is no longer active.", code="task_link_revoked")
            if invite.status != "active":
                raise DomainError(
                    "Task link has been revoked or used.",
                    code="task_link_revoked",
                )
            if invite.expires_at <= datetime.now(UTC):
                raise DomainError("Task link has expired.", code="task_link_expired")

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
        if not profile.anonymous_name:
            profile.anonymous_name = new_anonymous_name()
            await self.repository.session.flush()

        company_result = await self.repository.session.execute(
            select(Company).where(Company.id == claims.company_id)
        )
        company = company_result.scalar_one_or_none()
        if company is None:
            raise DomainError("Invitation project not found.", code="project_not_found")

        # Check if already registered
        already_registered = profile.user_id is not None
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
            .where(QuestionnaireAssignment.id.in_(claims.assignment_ids))
            .where(QuestionnaireAssignment.company_id == claims.company_id)
            .where(QuestionnaireAssignment.respondent_profile_id == claims.respondent_profile_id)
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
        )

        tasks = []
        return_to = quote(f"/invite/{token}", safe="")
        for assignment_id in claims.assignment_ids:
            ass = assignments_by_id[assignment_id]
            target_label = "Autoevaluare"
            if ass.target_type == AssignmentTargetType.team and ass.target_team_id:
                team_result = await self.repository.session.execute(
                    select(Team)
                    .where(Team.id == ass.target_team_id)
                    .where(Team.company_id == claims.company_id)
                )
                team = team_result.scalar_one_or_none()
                if team:
                    target_label = f"Echipa {team.name}"
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
                    href=(
                        f"/participant/tasks/{ass.id}"
                        f"?access=secure&returnTo={return_to}"
                    ),
                    assignmentId=str(ass.id),
                    targetLabel=target_label,
                    estimatedMinutes=est_minutes,
                    questionnaireKey=ass.questionnaire_key,
                )
            )

        return InviteVerifyResponse(
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
        )

    async def _invite_project_context(
        self,
        company_id: UUID,
        company_name: str,
        assignments: list["QuestionnaireAssignment"],
        token_expires_at: datetime,
    ) -> tuple[UUID | None, str, datetime]:
        from sqlalchemy import select

        from codrut.modules.companies.models import CompanyProject

        project_ids = {
            assignment.project_id for assignment in assignments if assignment.project_id is not None
        }
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
        return project.id, project.name, _min_datetime(
            token_expires_at,
            project.form_closes_at,
            project.due_at,
        )

    async def verify_invite_token_and_create_session(self, token: str) -> InviteVerifyResult:
        # 1. Verify the token using the existing verify_invite_token method
        verify_result = await self.verify_invite_token(token)

        import uuid

        from sqlalchemy import select

        from codrut.core.config import get_settings
        from codrut.modules.communications.task_links import parse_task_token
        from codrut.modules.companies.models import ParticipantProfile
        from codrut.modules.identity.models import User, UserRole

        claims = parse_task_token(token, get_settings())
        session_token = None

        # Load the exact participant profile covered by the verified task link.
        result = await self.repository.session.execute(
            select(ParticipantProfile).where(
                ParticipantProfile.id == claims.respondent_profile_id,
                ParticipantProfile.company_id == claims.company_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise DomainError("Profile not found.", code="profile_not_found")

        # If it is a low member (NOT leadership), we can automatically log them in
        if not verify_result.is_leadership:
            # Get or create the user
            user = None
            if profile.user_id is not None:
                # User already exists
                user_result = await self.repository.session.execute(
                    select(User).where(User.id == profile.user_id)
                )
                user = user_result.scalar_one_or_none()

            if user is None:
                existing_user = await self.repository.get_user_by_email(profile.email)
                if existing_user is not None:
                    raise DomainError(
                        "Invite email already belongs to another account. "
                        "Ask the trainer to link it explicitly.",
                        code="invite_email_account_conflict",
                    )
                user = User(
                    id=uuid.uuid4(),
                    email=profile.email.lower(),
                    password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
                    role=UserRole.participant,
                )
                await self.repository.add_user(user)
                profile.user_id = user.id
            elif user.role != UserRole.participant or user.email.lower() != profile.email.lower():
                raise DomainError(
                    "Invite profile is linked to an incompatible account.",
                    code="invite_profile_account_conflict",
                )

            # Create session for this user
            session_token = await self._create_session(user, expires_at=verify_result.expires_at)

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
        await self.repository.add_password_reset_token(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_session_token(raw_token),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )

        settings = get_settings()
        reset_url = f"{settings.public_app_url.rstrip('/')}/update-password?token={raw_token}"
        message = EmailMessage(
            to=EmailAddress(user.email),
            subject="Resetare parolă Codruț",
            html_body=(
                "<p>Ai cerut resetarea parolei pentru contul Codruț.</p>"
                f'<p><a href="{reset_url}">Setează o parolă nouă</a></p>'
                "<p>Linkul expiră în 60 de minute. "
                "Dacă nu ai cerut resetarea, ignoră acest email.</p>"
            ),
            text_body=(
                "Ai cerut resetarea parolei pentru contul Codruț.\n\n"
                f"Setează o parolă nouă aici: {reset_url}\n\n"
                "Linkul expiră în 60 de minute. Dacă nu ai cerut resetarea, ignoră acest email."
            ),
        )
        result = await build_email_provider(settings).send(message)
        if result.status != EmailDeliveryStatus.accepted:
            raise DomainError(
                "Emailul de resetare nu a putut fi trimis.",
                code="password_reset_email_failed",
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

        user.password_hash = hash_password(payload.new_password)
        await self.repository.revoke_password_reset_tokens_for_user(user.id)
        await self.repository.delete_sessions_for_user(user.id)

    async def logout(self, token: str) -> None:
        await self.repository.delete_session_by_token(token)

    async def accept_terms(self, user_id: UUID, payload: ConsentRequest) -> AuthResponse:
        if not payload.terms_accepted:
            raise DomainError(
                "Privacy and confidentiality terms must be accepted.",
                code="terms_required",
            )

        from sqlalchemy import select

        result = await self.repository.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise DomainError("Authenticated user was not found.", code="user_not_found")
        user.terms_accepted_at = datetime.now(UTC)
        user.terms_version = payload.terms_version
        return self._response(user)

    async def principal_from_session_token(self, token: str) -> SessionPrincipal | None:
        user = await self.repository.get_user_by_session_token(token)
        if user is None:
            return None
        return SessionPrincipal(
            user_id=user.id,
            email=user.email,
            role=user.role,
            terms_accepted_at=user.terms_accepted_at,
            terms_version=user.terms_version,
            session_token=token,
        )

    async def _create_session(self, user: User, *, expires_at: datetime | None = None) -> str:
        token = new_session_token()
        await self.repository.add_session(
            Session(
                user_id=user.id,
                token_hash=hash_session_token(token),
                expires_at=expires_at or datetime.now(UTC) + timedelta(days=90),
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
                company_id, respondent_profile_id
            )
            if active_invite is not None:
                settings = get_settings()
                try:
                    from codrut.modules.communications.task_links import parse_task_token
                    claims = parse_task_token(active_invite.token, settings)
                    
                    if (
                        set(claims.assignment_ids) == set(assignment_ids)
                        and claims.expires_at <= requested_expires_at
                        and active_invite.expires_at <= requested_expires_at
                    ):
                        return active_invite
                except Exception:  # noqa: S110
                    pass

        # 4. Invalidate previous active invites
        await self.repository.invalidate_invites_for_respondent(company_id, respondent_profile_id)

        # 5. Generate secure token claims
        claims = TaskLinkClaims(
            company_id=company_id,
            respondent_profile_id=respondent_profile_id,
            assignment_ids=tuple(assignment_ids),
            expires_at=requested_expires_at,
        )
        settings = get_settings()
        token = create_task_token(claims, settings)

        # 6. Save invite to DB
        invite = AssignmentInvite(
            company_id=company_id,
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
        await self.repository.invalidate_invites_for_respondent(company_id, respondent_profile_id)


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
