# ruff: noqa: S106
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from codrut.contracts.emails import (
    EmailDeliveryStatus,
    EmailProviderKey,
    EmailSendResult,
    make_test_message_id,
)
from codrut.core.config import get_settings
from codrut.core.errors import DomainError
from codrut.core.security import hash_password, verify_password
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.models import EmailSend
from codrut.modules.communications.task_links import TaskLinkClaims, create_task_token
from codrut.modules.companies.models import Company, CompanyProject, ParticipantProfile
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    AssignmentInvite,
    ConsentAcceptance,
    PasswordResetToken,
    Session,
    User,
    UserRole,
)
from codrut.modules.identity.repository import hash_session_token
from codrut.modules.identity.schemas import (
    ConsentRequest,
    InviteVerifyResponse,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    SessionPrincipal,
)
from codrut.modules.identity.service import IdentityService
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION


@pytest.mark.asyncio
async def test_accept_terms_records_secure_invite_audit_context() -> None:
    user = User(
        id=uuid.uuid4(),
        email="participant@example.com",
        password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        role=UserRole.participant,
    )
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        token="invite-token",
        status="active",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    active_session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hash_session_token("secure-session"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        assignment_invite_id=invite.id,
    )
    repository = MagicMock()
    repository.get_user_by_id = AsyncMock(return_value=user)
    repository.get_session_by_token = AsyncMock(return_value=active_session)
    repository.get_invite_by_id = AsyncMock(return_value=invite)
    repository.get_consent_acceptance = AsyncMock(return_value=None)
    repository.add_consent_acceptance = AsyncMock()
    service = IdentityService(AsyncMock())
    service.repository = repository

    response = await service.accept_terms(
        user.id,
        ConsentRequest(terms_accepted=True, terms_version=CURRENT_TERMS_VERSION),
        session_token="secure-session",
    )

    acceptance = repository.add_consent_acceptance.await_args.args[0]
    assert isinstance(acceptance, ConsentAcceptance)
    assert acceptance.user_id == user.id
    assert acceptance.session_id == active_session.id
    assert acceptance.assignment_invite_id == invite.id
    assert acceptance.respondent_profile_id == invite.respondent_profile_id
    assert acceptance.terms_version == CURRENT_TERMS_VERSION
    assert acceptance.source == "secure_invite"
    assert response.terms_version == CURRENT_TERMS_VERSION
    assert response.terms_accepted_at == acceptance.accepted_at


@pytest.mark.asyncio
async def test_accept_terms_reuses_existing_audit_record_for_same_session() -> None:
    accepted_at = datetime.now(UTC) - timedelta(minutes=5)
    user = User(
        id=uuid.uuid4(),
        email="participant@example.com",
        password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        role=UserRole.participant,
    )
    active_session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hash_session_token("secure-session"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    existing = ConsentAcceptance(
        id=uuid.uuid4(),
        user_id=user.id,
        session_id=active_session.id,
        terms_version=CURRENT_TERMS_VERSION,
        source="authenticated",
        accepted_at=accepted_at,
    )
    repository = MagicMock()
    repository.get_user_by_id = AsyncMock(return_value=user)
    repository.get_session_by_token = AsyncMock(return_value=active_session)
    repository.get_consent_acceptance = AsyncMock(return_value=existing)
    repository.add_consent_acceptance = AsyncMock()
    service = IdentityService(AsyncMock())
    service.repository = repository

    await service.accept_terms(
        user.id,
        ConsentRequest(terms_accepted=True, terms_version=CURRENT_TERMS_VERSION),
        session_token="secure-session",
    )

    repository.add_consent_acceptance.assert_not_awaited()
    assert user.terms_accepted_at == accepted_at


@pytest.mark.asyncio
async def test_accept_terms_rejects_retired_legal_version() -> None:
    repository = MagicMock()
    repository.get_user_by_id = AsyncMock()
    service = IdentityService(AsyncMock())
    service.repository = repository

    with pytest.raises(DomainError) as exc_info:
        await service.accept_terms(
            uuid.uuid4(),
            ConsentRequest(terms_accepted=True, terms_version="retired-version"),
            session_token="secure-session",
        )

    assert exc_info.value.code == "terms_version_outdated"
    repository.get_user_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_secure_link_requires_persisted_current_consent() -> None:
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    profile = ParticipantProfile(
        id=uuid.uuid4(),
        company_id=company_id,
        user_id=user_id,
        email="participant@example.com",
        full_name="Participant Test",
    )
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=profile.id,
        token="invite-token",
        status="active",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    active_session = Session(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=hash_session_token("secure-session"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        assignment_invite_id=invite.id,
    )
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = profile
    mock_session = AsyncMock()
    mock_session.execute.return_value = profile_result
    repository = MagicMock()
    repository.session = mock_session
    repository.get_session_by_token = AsyncMock(return_value=active_session)
    repository.get_invite_by_token = AsyncMock(return_value=invite)
    repository.get_consent_acceptance = AsyncMock(return_value=None)
    repository.get_latest_consent_acceptance = AsyncMock(return_value=None)
    service = IdentityService(mock_session)
    service.repository = repository
    principal = SessionPrincipal(
        user_id=user_id,
        email=profile.email,
        role=UserRole.participant,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
        session_token="secure-session",
        assignment_invite_id=invite.id,
    )

    with pytest.raises(DomainError) as exc_info:
        await service.require_secure_link_consent(principal, invite.token)

    assert exc_info.value.code == "terms_required"
    repository.get_consent_acceptance.assert_awaited_once_with(
        user_id=user_id,
        terms_version=CURRENT_TERMS_VERSION,
        session_id=active_session.id,
    )


@pytest.mark.asyncio
async def test_secure_link_accepts_matching_current_consent() -> None:
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    profile = ParticipantProfile(
        id=uuid.uuid4(),
        company_id=company_id,
        user_id=user_id,
        email="participant@example.com",
        full_name="Participant Test",
    )
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=profile.id,
        token="invite-token",
        status="active",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    active_session = Session(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=hash_session_token("secure-session"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        assignment_invite_id=invite.id,
    )
    acceptance = ConsentAcceptance(
        id=uuid.uuid4(),
        user_id=user_id,
        session_id=active_session.id,
        assignment_invite_id=invite.id,
        respondent_profile_id=profile.id,
        terms_version=CURRENT_TERMS_VERSION,
        source="secure_invite",
        accepted_at=datetime.now(UTC),
    )
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = profile
    mock_session = AsyncMock()
    mock_session.execute.return_value = profile_result
    repository = MagicMock()
    repository.session = mock_session
    repository.get_session_by_token = AsyncMock(return_value=active_session)
    repository.get_invite_by_token = AsyncMock(return_value=invite)
    repository.get_consent_acceptance = AsyncMock(return_value=acceptance)
    repository.get_latest_consent_acceptance = AsyncMock()
    service = IdentityService(mock_session)
    service.repository = repository
    principal = SessionPrincipal(
        user_id=user_id,
        email=profile.email,
        role=UserRole.participant,
        terms_accepted_at=acceptance.accepted_at,
        terms_version=CURRENT_TERMS_VERSION,
        session_token="secure-session",
        assignment_invite_id=invite.id,
    )

    await service.require_secure_link_consent(principal, invite.token)

    repository.get_consent_acceptance.assert_awaited_once_with(
        user_id=user_id,
        terms_version=CURRENT_TERMS_VERSION,
        session_id=active_session.id,
    )
    repository.get_latest_consent_acceptance.assert_not_awaited()


@pytest.mark.asyncio
async def test_secure_link_accepts_persisted_current_consent_from_prior_session() -> None:
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    profile = ParticipantProfile(
        id=uuid.uuid4(),
        company_id=company_id,
        user_id=user_id,
        email="participant@example.com",
        full_name="Participant Test",
    )
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=profile.id,
        token="invite-token",
        status="active",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    active_session = Session(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=hash_session_token("current-session"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        assignment_invite_id=invite.id,
    )
    prior_acceptance = ConsentAcceptance(
        id=uuid.uuid4(),
        user_id=user_id,
        session_id=uuid.uuid4(),
        assignment_invite_id=uuid.uuid4(),
        respondent_profile_id=profile.id,
        terms_version=CURRENT_TERMS_VERSION,
        source="secure_invite",
        accepted_at=datetime.now(UTC) - timedelta(days=1),
    )
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = profile
    mock_session = AsyncMock()
    mock_session.execute.return_value = profile_result
    repository = MagicMock()
    repository.session = mock_session
    repository.get_session_by_token = AsyncMock(return_value=active_session)
    repository.get_invite_by_token = AsyncMock(return_value=invite)
    repository.get_consent_acceptance = AsyncMock(return_value=None)
    repository.get_latest_consent_acceptance = AsyncMock(return_value=prior_acceptance)
    service = IdentityService(mock_session)
    service.repository = repository
    principal = SessionPrincipal(
        user_id=user_id,
        email=profile.email,
        role=UserRole.participant,
        terms_accepted_at=prior_acceptance.accepted_at,
        terms_version=CURRENT_TERMS_VERSION,
        session_token="current-session",
        assignment_invite_id=invite.id,
    )

    await service.require_secure_link_consent(principal, invite.token)

    repository.get_latest_consent_acceptance.assert_awaited_once_with(
        user_id=user_id,
        terms_version=CURRENT_TERMS_VERSION,
    )


def _company_result(company_id: uuid.UUID, name: str = "Intake Iunie") -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = Company(id=company_id, name=name)
    return result


def _invite_verify_response(email: str, expires_at: datetime) -> InviteVerifyResponse:
    return InviteVerifyResponse(
        email=email,
        full_name="Invite Participant",
        is_leadership=False,
        already_registered=True,
        project_name="Invite Project",
        expires_at=expires_at,
        token_status="active",  # noqa: S106
        tasks=[],
    )


class FakeResetRepository:
    def __init__(self, user: User) -> None:
        self.user = user
        self.tokens: list[PasswordResetToken] = []
        self.deleted_session_user_ids: list[uuid.UUID] = []

    async def get_user_by_email(self, email: str) -> User | None:
        return self.user if self.user.email == email.lower() else None

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.user if self.user.id == user_id else None

    async def revoke_password_reset_tokens_for_user(self, user_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        for token in self.tokens:
            if token.user_id == user_id and token.used_at is None:
                token.used_at = now

    async def add_password_reset_token(self, token: PasswordResetToken) -> PasswordResetToken:
        self.tokens.append(token)
        return token

    async def get_active_password_reset_token(self, token: str) -> PasswordResetToken | None:
        token_hash = hash_session_token(token)
        now = datetime.now(UTC)
        return next(
            (
                reset_token
                for reset_token in self.tokens
                if reset_token.token_hash == token_hash
                and reset_token.expires_at > now
                and reset_token.used_at is None
            ),
            None,
        )

    async def delete_sessions_for_user(self, user_id: uuid.UUID) -> None:
        self.deleted_session_user_ids.append(user_id)


class FakeAcceptedEmailProvider:
    def __init__(self) -> None:
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        return EmailSendResult(
            provider=EmailProviderKey.test,
            status=EmailDeliveryStatus.accepted,
            message_id=make_test_message_id(),
            recipient=message.to,
        )


class FakeResetOutboxRepository:
    def __init__(self) -> None:
        self.sends: list[EmailSend] = []

    async def enqueue_email_send(self, send: EmailSend) -> tuple[EmailSend, bool]:
        self.sends.append(send)
        return send, True


class FakeSessionRepository:
    def __init__(self) -> None:
        self.sessions: list[Session] = []

    async def add_session(self, session: Session) -> Session:
        self.sessions.append(session)
        return session


@pytest.mark.asyncio
async def test_principal_for_local_user_requires_matching_seeded_role() -> None:
    user = User(
        id=uuid.uuid4(),
        email="trainer@example.com",
        password_hash=hash_password("local-development-password"),
        role=UserRole.trainer,
    )
    repository = MagicMock()
    repository.get_user_by_email = AsyncMock(return_value=user)
    service = IdentityService(AsyncMock())
    service.repository = repository

    principal = await service.principal_for_local_user(
        email=user.email,
        role=UserRole.trainer,
    )
    mismatched = await service.principal_for_local_user(
        email=user.email,
        role=UserRole.participant,
    )

    assert principal is not None
    assert principal.user_id == user.id
    assert principal.role == UserRole.trainer
    assert principal.session_token == "local-development:trainer"  # noqa: S105
    assert mismatched is None


@pytest.mark.asyncio
async def test_verify_invite_token_success() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_session = AsyncMock()
    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=claims.company_id,
        user_id=None,
        email="test@example.com",
        full_name="Test User",
    )
    mock_result_profile = MagicMock()
    mock_result_profile.scalar_one_or_none.return_value = mock_profile

    mock_result_leadership = MagicMock()
    mock_result_leadership.scalar.return_value = True

    mock_assignment = QuestionnaireAssignment(
        id=claims.assignment_ids[0],
        company_id=claims.company_id,
        respondent_profile_id=claims.respondent_profile_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )
    mock_result_assignments = MagicMock()
    mock_result_assignments.scalars.return_value.all.return_value = [mock_assignment]

    mock_session.execute.side_effect = [
        mock_result_profile,
        _company_result(claims.company_id),
        mock_result_leadership,
        mock_result_assignments,
    ]

    service = IdentityService(mock_session)
    result = await service.verify_invite_token(token)

    assert result.email == "test@example.com"
    assert result.full_name == "Test User"
    assert result.is_leadership is True
    assert result.already_registered is False
    assert result.project_id is None
    assert result.project_name == "Intake Iunie"
    assert result.expires_at.timestamp() == int(claims.expires_at.timestamp())
    assert result.token_status == "active"  # noqa: S105
    assert len(result.tasks) == 1
    assert result.tasks[0].id == str(mock_assignment.id)
    assert result.tasks[0].href.endswith(
        f"/participant/tasks/{mock_assignment.id}?access=secure&returnTo=%2Finvite%2F{token}"
    )
    assert mock_profile.anonymous_name is None
    mock_session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_password_reset_request_sends_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        id=uuid.uuid4(),
        email="ana@example.com",
        password_hash=hash_password("old-password-123"),
        role=UserRole.trainer,
    )
    repository = FakeResetRepository(user)
    provider = FakeAcceptedEmailProvider()
    outbox = FakeResetOutboxRepository()
    monkeypatch.setattr(
        "codrut.modules.identity.service.build_email_provider",
        lambda _settings: provider,
    )
    monkeypatch.setattr(
        "codrut.modules.communications.service.CommunicationsRepository",
        lambda _session: outbox,
    )

    service = IdentityService(AsyncMock())
    service.repository = repository

    await service.request_password_reset(PasswordResetRequest(email=user.email))

    assert len(repository.tokens) == 1
    assert repository.tokens[0].user_id == user.id
    assert repository.tokens[0].used_at is None
    assert provider.messages == []
    assert len(outbox.sends) == 1
    assert outbox.sends[0].owner_id == user.id
    assert outbox.sends[0].message_payload is not None
    assert "/update-password?token=" in str(outbox.sends[0].message_payload["text_body"])


@pytest.mark.asyncio
async def test_change_password_verifies_current_password_and_updates_hash() -> None:
    user = User(
        id=uuid.uuid4(),
        email="ana@example.com",
        password_hash=hash_password("old-password-123"),
        role=UserRole.trainer,
    )
    repository = FakeResetRepository(user)
    service = IdentityService(AsyncMock())
    service.repository = repository

    await service.change_password(
        user.id,
        PasswordChangeRequest(
            current_password="old-password-123",
            new_password="New-password-123",
        ),
    )

    assert verify_password("New-password-123", user.password_hash)
    assert repository.deleted_session_user_ids == [user.id]


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current_password() -> None:
    user = User(
        id=uuid.uuid4(),
        email="ana@example.com",
        password_hash=hash_password("old-password-123"),
        role=UserRole.trainer,
    )
    repository = FakeResetRepository(user)
    service = IdentityService(AsyncMock())
    service.repository = repository

    with pytest.raises(DomainError, match="Parola curentă"):
        await service.change_password(
            user.id,
            PasswordChangeRequest(
                current_password="wrong-password",
                new_password="New-password-123",
            ),
        )

    assert verify_password("old-password-123", user.password_hash)


@pytest.mark.asyncio
async def test_password_reset_request_sends_link_for_shadow_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        id=uuid.uuid4(),
        email="shadow@example.com",
        password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        role=UserRole.participant,
    )
    repository = FakeResetRepository(user)
    provider = FakeAcceptedEmailProvider()
    outbox = FakeResetOutboxRepository()
    monkeypatch.setattr(
        "codrut.modules.identity.service.build_email_provider",
        lambda _settings: provider,
    )
    monkeypatch.setattr(
        "codrut.modules.communications.service.CommunicationsRepository",
        lambda _session: outbox,
    )

    service = IdentityService(AsyncMock())
    service.repository = repository
    service._shadow_account_password_reset_allowed = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await service.request_password_reset(PasswordResetRequest(email=user.email))

    assert len(repository.tokens) == 1
    assert provider.messages == []
    assert len(outbox.sends) == 1


@pytest.mark.asyncio
async def test_password_reset_request_skips_shadow_user_after_access_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        id=uuid.uuid4(),
        email="shadow@example.com",
        password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        role=UserRole.participant,
    )
    repository = FakeResetRepository(user)
    provider = FakeAcceptedEmailProvider()
    monkeypatch.setattr(
        "codrut.modules.identity.service.build_email_provider",
        lambda _settings: provider,
    )

    service = IdentityService(AsyncMock())
    service.repository = repository
    service._shadow_account_password_reset_allowed = AsyncMock(return_value=False)  # type: ignore[method-assign]

    await service.request_password_reset(PasswordResetRequest(email=user.email))

    assert repository.tokens == []
    assert provider.messages == []


@pytest.mark.asyncio
async def test_shadow_password_reset_allowed_only_for_open_leadership_assignment_window() -> None:
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    expired_assignment = QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
        due_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    closed_project_assignment = QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        project_id=project_id,
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
        due_at=datetime.now(UTC) + timedelta(days=2),
    )
    open_assignment = QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="pcm_base",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
        due_at=datetime.now(UTC) + timedelta(days=1),
    )
    closed_project = CompanyProject(
        id=project_id,
        company_id=closed_project_assignment.company_id,
        name="Closed project",
        form_closes_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    query_result = MagicMock()
    query_result.all.return_value = [
        (expired_assignment, None),
        (closed_project_assignment, closed_project),
        (open_assignment, None),
    ]
    mock_session = AsyncMock()
    mock_session.execute.return_value = query_result
    service = IdentityService(mock_session)

    assert await service._shadow_account_password_reset_allowed(user_id) is True


@pytest.mark.asyncio
async def test_shadow_password_reset_rejects_when_all_windows_closed() -> None:
    user_id = uuid.uuid4()
    expired_assignment = QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
        due_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    query_result = MagicMock()
    query_result.all.return_value = [(expired_assignment, None)]
    mock_session = AsyncMock()
    mock_session.execute.return_value = query_result
    service = IdentityService(mock_session)

    assert await service._shadow_account_password_reset_allowed(user_id) is False


@pytest.mark.asyncio
async def test_password_reset_confirm_updates_password_and_consumes_token() -> None:
    user = User(
        id=uuid.uuid4(),
        email="ana@example.com",
        password_hash=hash_password("old-password-123"),
        role=UserRole.trainer,
    )
    repository = FakeResetRepository(user)
    raw_token = "reset-token-" + uuid.uuid4().hex
    repository.tokens.append(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )

    service = IdentityService(AsyncMock())
    service.repository = repository

    await service.confirm_password_reset(
        PasswordResetConfirmRequest(token=raw_token, password="New-password-123")
    )

    assert verify_password("New-password-123", user.password_hash)
    assert repository.tokens[0].used_at is not None
    assert repository.deleted_session_user_ids == [user.id]

    with pytest.raises(DomainError, match="invalid"):
        await service.confirm_password_reset(
            PasswordResetConfirmRequest(token=raw_token, password="Another-password-123")
        )


@pytest.mark.asyncio
async def test_password_reset_confirm_rejects_temporary_shadow_user() -> None:
    user = User(
        id=uuid.uuid4(),
        email="shadow@example.com",
        password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        role=UserRole.participant,
    )
    repository = FakeResetRepository(user)
    raw_token = "reset-token-" + uuid.uuid4().hex
    repository.tokens.append(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )

    service = IdentityService(AsyncMock())
    service.repository = repository
    service._shadow_account_password_reset_allowed = AsyncMock(return_value=False)  # type: ignore[method-assign]

    with pytest.raises(DomainError) as exc_info:
        await service.confirm_password_reset(
            PasswordResetConfirmRequest(token=raw_token, password="New-password-123")
        )

    assert exc_info.value.code == "password_reset_forbidden"
    assert user.password_hash == SHADOW_ACCOUNT_PASSWORD_HASH


@pytest.mark.asyncio
async def test_create_session_defaults_to_90_days() -> None:
    user = User(
        id=uuid.uuid4(),
        email="ana@example.com",
        password_hash=hash_password("participant-password-123"),
        role=UserRole.participant,
    )
    repository = FakeSessionRepository()
    service = IdentityService(AsyncMock())
    service.repository = repository
    before = datetime.now(UTC)

    token = await service._create_session(user)

    assert token
    assert len(repository.sessions) == 1
    expires_at = repository.sessions[0].expires_at
    assert expires_at >= before + timedelta(days=90) - timedelta(seconds=2)
    assert expires_at <= before + timedelta(days=90, seconds=2)


@pytest.mark.asyncio
async def test_verify_invite_token_uses_assignment_project_context() -> None:
    settings = get_settings()
    project_id = uuid.uuid4()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_session = AsyncMock()
    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=claims.company_id,
        user_id=None,
        email="test@example.com",
        full_name="Test User",
    )
    mock_result_profile = MagicMock()
    mock_result_profile.scalar_one_or_none.return_value = mock_profile

    mock_result_leadership = MagicMock()
    mock_result_leadership.scalar.return_value = False

    mock_assignment = QuestionnaireAssignment(
        id=claims.assignment_ids[0],
        company_id=claims.company_id,
        project_id=project_id,
        respondent_profile_id=claims.respondent_profile_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )
    mock_result_assignments = MagicMock()
    mock_result_assignments.scalars.return_value.all.return_value = [mock_assignment]

    mock_project = CompanyProject(
        id=project_id,
        company_id=claims.company_id,
        name="Leadership septembrie",
    )
    mock_result_project = MagicMock()
    mock_result_project.scalar_one_or_none.return_value = mock_project

    mock_session.execute.side_effect = [
        mock_result_profile,
        _company_result(claims.company_id, name="Michelin"),
        mock_result_leadership,
        mock_result_assignments,
        mock_result_project,
    ]

    service = IdentityService(mock_session)
    result = await service.verify_invite_token(token)

    assert result.project_id == project_id
    assert result.project_name == "Leadership septembrie"
    assert result.tasks[0].href.endswith(f"?access=secure&returnTo=%2Finvite%2F{token}")


@pytest.mark.asyncio
async def test_verify_invite_token_rejects_profile_company_mismatch() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_session = AsyncMock()
    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=uuid.uuid4(),
        user_id=None,
        email="test@example.com",
        full_name="Test User",
    )
    mock_result_profile = MagicMock()
    mock_result_profile.scalar_one_or_none.return_value = mock_profile
    mock_session.execute.side_effect = [mock_result_profile]

    service = IdentityService(mock_session)
    with pytest.raises(DomainError) as exc_info:
        await service.verify_invite_token(token)

    assert exc_info.value.code == "task_link_scope_mismatch"


@pytest.mark.asyncio
async def test_verify_invite_token_rejects_assignment_scope_mismatch() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_session = AsyncMock()
    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=claims.company_id,
        user_id=None,
        email="test@example.com",
        full_name="Test User",
    )
    mock_result_profile = MagicMock()
    mock_result_profile.scalar_one_or_none.return_value = mock_profile

    mock_result_leadership = MagicMock()
    mock_result_leadership.scalar.return_value = False

    mock_result_assignments = MagicMock()
    mock_result_assignments.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        mock_result_profile,
        _company_result(claims.company_id),
        mock_result_leadership,
        mock_result_assignments,
    ]

    service = IdentityService(mock_session)
    with pytest.raises(DomainError) as exc_info:
        await service.verify_invite_token(token)

    assert exc_info.value.code == "task_link_scope_mismatch"


@pytest.mark.asyncio
async def test_verify_invite_token_expired() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_session = AsyncMock()
    service = IdentityService(mock_session)

    with pytest.raises(DomainError) as exc_info:
        await service.verify_invite_token(token)
    assert exc_info.value.code == "task_link_expired"


@pytest.mark.asyncio
async def test_verify_invite_token_invalid_signature() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings) + "invalid_signature"

    mock_session = AsyncMock()
    service = IdentityService(mock_session)

    with pytest.raises(DomainError) as exc_info:
        await service.verify_invite_token(token)
    assert exc_info.value.code == "task_link_invalid"


@pytest.mark.asyncio
async def test_register_success() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=claims.company_id,
        user_id=None,
        email="test@example.com",
        full_name="Test User",
    )
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=claims.company_id,
        respondent_profile_id=claims.respondent_profile_id,
        token=token,
        status="active",
        expires_at=claims.expires_at,
    )
    mock_result_profile_link = MagicMock()
    mock_result_profile_link.scalar_one_or_none.return_value = mock_profile
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result_profile_link
    repository = MagicMock()
    repository.session = mock_session
    repository.get_user_by_email = AsyncMock(return_value=None)
    repository.add_user = AsyncMock(side_effect=lambda user: user)
    active_session = Session(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash=hash_session_token("registered-session"),
        expires_at=claims.expires_at,
        assignment_invite_id=invite.id,
    )
    repository.get_session_by_token = AsyncMock(return_value=active_session)
    repository.add_consent_acceptance = AsyncMock()
    service = IdentityService(mock_session)
    service.repository = repository
    service._verify_invite_token = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            InviteVerifyResponse(
                email=mock_profile.email,
                full_name=mock_profile.full_name,
                is_leadership=True,
                already_registered=False,
                project_name="Leadership pilot",
                expires_at=claims.expires_at,
                token_status="active",
                tasks=[],
            ),
            invite,
        )
    )
    service._create_session = AsyncMock(return_value="registered-session")  # type: ignore[method-assign]

    payload = RegisterRequest(
        email="test@example.com",
        password="Securepassword123!",
        token=token,
        terms_accepted=True,
    )
    auth_result = await service.register(payload)

    assert auth_result.response.email == "test@example.com"
    assert auth_result.response.role == UserRole.participant
    assert mock_profile.user_id is not None
    link_query = mock_session.execute.call_args.args[0]
    where_text = " ".join(str(clause) for clause in link_query._where_criteria)
    assert "participant_profiles.email" not in where_text
    assert "participant_profiles.id" in where_text
    assert "participant_profiles.company_id" in where_text
    service._create_session.assert_awaited_once_with(
        repository.add_user.await_args.args[0],
        expires_at=claims.expires_at,
        assignment_invite_id=invite.id,
    )
    acceptance = repository.add_consent_acceptance.await_args.args[0]
    assert acceptance.user_id == mock_profile.user_id
    assert acceptance.session_id == active_session.id
    assert acceptance.assignment_invite_id == invite.id
    assert acceptance.respondent_profile_id == mock_profile.id
    assert acceptance.terms_version == CURRENT_TERMS_VERSION
    assert acceptance.source == "secure_invite"
    assert acceptance.accepted_at == auth_result.response.terms_accepted_at


@pytest.mark.asyncio
async def test_register_requires_terms_acceptance() -> None:
    mock_session = AsyncMock()
    service = IdentityService(mock_session)
    payload = RegisterRequest(
        email="test@example.com",
        password="Securepassword123!",
        token="token",
    )

    with pytest.raises(DomainError) as exc_info:
        await service.register(payload)

    assert exc_info.value.code == "terms_required"
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_register_forbidden_for_non_leadership() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_session = AsyncMock()

    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=claims.company_id,
        user_id=None,
        email="test@example.com",
        full_name="Test User",
    )
    mock_result_profile = MagicMock()
    mock_result_profile.scalar_one_or_none.return_value = mock_profile

    # Returns False for is_leadership exists query
    mock_result_leadership = MagicMock()
    mock_result_leadership.scalar.return_value = False

    # Mock assignments
    mock_assignment = QuestionnaireAssignment(
        id=claims.assignment_ids[0],
        company_id=claims.company_id,
        respondent_profile_id=claims.respondent_profile_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )
    mock_result_assignments = MagicMock()
    mock_result_assignments.scalars.return_value.all.return_value = [mock_assignment]

    mock_session.execute.side_effect = [
        mock_result_profile,
        _company_result(claims.company_id),
        mock_result_leadership,
        mock_result_assignments,
    ]

    service = IdentityService(mock_session)
    payload = RegisterRequest(
        email="test@example.com",
        password="Securepassword123!",
        token=token,
        terms_accepted=True,
    )

    with pytest.raises(DomainError) as exc_info:
        await service.register(payload)
    assert exc_info.value.code == "registration_forbidden"


@pytest.mark.asyncio
async def test_register_mismatched_email() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_session = AsyncMock()

    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=claims.company_id,
        user_id=None,
        email="invited@example.com",
        full_name="Test User",
    )
    mock_result_profile = MagicMock()
    mock_result_profile.scalar_one_or_none.return_value = mock_profile

    mock_result_leadership = MagicMock()
    mock_result_leadership.scalar.return_value = True

    # Mock assignments
    mock_assignment = QuestionnaireAssignment(
        id=claims.assignment_ids[0],
        company_id=claims.company_id,
        respondent_profile_id=claims.respondent_profile_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )
    mock_result_assignments = MagicMock()
    mock_result_assignments.scalars.return_value.all.return_value = [mock_assignment]

    mock_session.execute.side_effect = [
        mock_result_profile,
        _company_result(claims.company_id),
        mock_result_leadership,
        mock_result_assignments,
    ]

    service = IdentityService(mock_session)
    payload = RegisterRequest(
        email="attacker@example.com",
        password="Securepassword123!",
        token=token,
        terms_accepted=True,
    )

    with pytest.raises(DomainError) as exc_info:
        await service.register(payload)
    assert exc_info.value.code == "email_mismatch"


@pytest.mark.asyncio
async def test_verify_invite_token_and_create_session_for_low_member() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    # 1. verify_invite_token - ParticipantProfile check
    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=claims.company_id,
        user_id=None,
        email="guest@example.com",
        full_name="Guest User",
    )
    mock_result_profile = MagicMock()
    mock_result_profile.scalar_one_or_none.return_value = mock_profile

    # 2. verify_invite_token - is_leadership exists check -> False (low member)
    mock_result_leadership = MagicMock()
    mock_result_leadership.scalar.return_value = False

    # 3. verify_invite_token - QuestionnaireAssignment query
    mock_assignment = QuestionnaireAssignment(
        id=claims.assignment_ids[0],
        company_id=claims.company_id,
        respondent_profile_id=claims.respondent_profile_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )
    mock_result_assignments = MagicMock()
    mock_result_assignments.scalars.return_value.all.return_value = [mock_assignment]

    # 4. verify_invite_token_and_create_session - load profile again
    mock_result_profile_again = MagicMock()
    mock_result_profile_again.scalar_one_or_none.return_value = mock_profile
    mock_result_existing_user = MagicMock()
    mock_result_existing_user.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_result_profile,
        _company_result(claims.company_id),
        mock_result_leadership,
        mock_result_assignments,
        mock_result_profile_again,
        mock_result_existing_user,
    ]

    service = IdentityService(mock_session)
    result = await service.verify_invite_token_and_create_session(token)

    assert result.response.email == "guest@example.com"
    assert result.response.is_leadership is False
    assert result.session_token is not None  # Generates a temporary session
    assert mock_profile.user_id is not None  # Shadow user linked


@pytest.mark.asyncio
async def test_invite_exchange_rejects_another_authenticated_user_session() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=5)
    token = create_task_token(
        TaskLinkClaims(
            company_id=company_id,
            respondent_profile_id=respondent_id,
            assignment_ids=(assignment_id,),
            expires_at=expires_at,
        ),
        get_settings(),
    )
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=token,
        status="active",
        expires_at=expires_at,
    )
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        user_id=target_user_id,
        email="invite@example.com",
        full_name="Invite Participant",
    )
    other_session = Session(
        user_id=uuid.uuid4(),
        token_hash="other-session-hash",  # noqa: S106
        expires_at=expires_at,
    )
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = profile
    mock_session = AsyncMock()
    mock_session.execute.return_value = profile_result
    service = IdentityService(mock_session)
    service._verify_invite_token = AsyncMock(  # type: ignore[method-assign]
        return_value=(_invite_verify_response(profile.email, expires_at), invite)
    )
    service.repository.get_session_by_token = AsyncMock(return_value=other_session)
    service.repository.add_session = AsyncMock()

    with pytest.raises(DomainError) as exc_info:
        await service.verify_invite_token_and_create_session(
            token,
            existing_session_token="other-session",
        )

    assert exc_info.value.code == "invite_session_conflict"
    service.repository.add_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_exchange_preserves_same_user_authenticated_session() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    user_id = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=5)
    token = create_task_token(
        TaskLinkClaims(
            company_id=company_id,
            respondent_profile_id=respondent_id,
            assignment_ids=(assignment_id,),
            expires_at=expires_at,
        ),
        get_settings(),
    )
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=token,
        status="active",
        expires_at=expires_at,
    )
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        user_id=user_id,
        email="invite@example.com",
        full_name="Invite Participant",
    )
    user = User(
        id=user_id,
        email=profile.email,
        password_hash="registered-password-hash",  # noqa: S106
        role=UserRole.participant,
    )
    existing_session = Session(
        user_id=user_id,
        token_hash="existing-session-hash",  # noqa: S106
        expires_at=expires_at,
        assignment_invite_id=None,
    )
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = profile
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user
    mock_session = AsyncMock()
    mock_session.execute.side_effect = [profile_result, user_result]
    service = IdentityService(mock_session)
    service._verify_invite_token = AsyncMock(  # type: ignore[method-assign]
        return_value=(_invite_verify_response(profile.email, expires_at), invite)
    )
    service.repository.get_session_by_token = AsyncMock(return_value=existing_session)
    service.repository.add_session = AsyncMock()

    result = await service.verify_invite_token_and_create_session(
        token,
        existing_session_token="existing-session",
    )

    assert result.session_token is None
    service.repository.add_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_invite_token_and_create_session_for_leadership() -> None:
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = create_task_token(claims, settings)

    mock_session = AsyncMock()

    # 1. verify_invite_token - ParticipantProfile check
    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=claims.company_id,
        user_id=None,
        email="leader@example.com",
        full_name="Leader User",
    )
    mock_result_profile = MagicMock()
    mock_result_profile.scalar_one_or_none.return_value = mock_profile

    # 2. verify_invite_token - is_leadership exists check -> True
    mock_result_leadership = MagicMock()
    mock_result_leadership.scalar.return_value = True

    # 3. verify_invite_token - QuestionnaireAssignment query
    mock_assignment = QuestionnaireAssignment(
        id=claims.assignment_ids[0],
        company_id=claims.company_id,
        respondent_profile_id=claims.respondent_profile_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )
    mock_result_assignments = MagicMock()
    mock_result_assignments.scalars.return_value.all.return_value = [mock_assignment]

    # 4. verify_invite_token_and_create_session - load profile again
    mock_result_profile_again = MagicMock()
    mock_result_profile_again.scalar_one_or_none.return_value = mock_profile

    mock_session.execute.side_effect = [
        mock_result_profile,
        _company_result(claims.company_id),
        mock_result_leadership,
        mock_result_assignments,
        mock_result_profile_again,
    ]

    service = IdentityService(mock_session)
    result = await service.verify_invite_token_and_create_session(token)

    assert result.response.email == "leader@example.com"
    assert result.response.is_leadership is True
    assert result.session_token is None  # Leadership must register manually to get a session
