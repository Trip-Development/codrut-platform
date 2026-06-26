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
from codrut.modules.communications.task_links import TaskLinkClaims, create_task_token
from codrut.modules.companies.models import Company, CompanyProject, ParticipantProfile
from codrut.modules.identity.models import PasswordResetToken, User, UserRole
from codrut.modules.identity.repository import hash_session_token
from codrut.modules.identity.schemas import (
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
)
from codrut.modules.identity.service import IdentityService


def _company_result(company_id: uuid.UUID, name: str = "Intake Iunie") -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = Company(id=company_id, name=name)
    return result


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
    monkeypatch.setattr(
        "codrut.modules.identity.service.build_email_provider",
        lambda _settings: provider,
    )

    service = IdentityService(AsyncMock())
    service.repository = repository

    await service.request_password_reset(PasswordResetRequest(email=user.email))

    assert len(repository.tokens) == 1
    assert repository.tokens[0].user_id == user.id
    assert repository.tokens[0].used_at is None
    assert len(provider.messages) == 1
    assert "/update-password?token=" in provider.messages[0].text_body


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
        PasswordResetConfirmRequest(token=raw_token, password="new-password-123")
    )

    assert verify_password("new-password-123", user.password_hash)
    assert repository.tokens[0].used_at is not None
    assert repository.deleted_session_user_ids == [user.id]

    with pytest.raises(DomainError, match="invalid"):
        await service.confirm_password_reset(
            PasswordResetConfirmRequest(token=raw_token, password="another-password-123")
        )


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

    mock_session = AsyncMock()

    # 1. select(ParticipantProfile) in verify_invite_token
    mock_profile = ParticipantProfile(
        id=claims.respondent_profile_id,
        company_id=claims.company_id,
        user_id=None,
        email="test@example.com",
        full_name="Test User",
    )
    mock_result_profile = MagicMock()
    mock_result_profile.scalar_one_or_none.return_value = mock_profile

    # 2. is_leadership exists query in verify_invite_token
    mock_result_leadership = MagicMock()
    mock_result_leadership.scalar.return_value = True

    # 3. select(QuestionnaireAssignment) in verify_invite_token
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
    # (profile fetch in verify_invite_token_and_create_session)
    mock_result_profile_verify = MagicMock()
    mock_result_profile_verify.scalar_one_or_none.return_value = mock_profile

    # 5. select(User) get_user_by_email in register (returns None)
    mock_result_user_exists = MagicMock()
    mock_result_user_exists.scalar_one_or_none.return_value = None

    # 6. select(ParticipantProfile) in register (to link the exact invite profile)
    mock_result_profile_link = MagicMock()
    mock_result_profile_link.scalar_one_or_none.return_value = mock_profile

    mock_session.execute.side_effect = [
        mock_result_profile,
        _company_result(claims.company_id),
        mock_result_leadership,
        mock_result_assignments,
        mock_result_user_exists,
        mock_result_profile_link,
    ]

    service = IdentityService(mock_session)

    payload = RegisterRequest(
        email="test@example.com",
        password="securepassword123",
        token=token,
        terms_accepted=True,
    )
    auth_result = await service.register(payload)

    assert auth_result.response.email == "test@example.com"
    assert auth_result.response.role == UserRole.participant
    assert mock_profile.user_id is not None
    link_query = mock_session.execute.call_args_list[-1].args[0]
    where_text = " ".join(str(clause) for clause in link_query._where_criteria)
    assert "participant_profiles.email" not in where_text
    assert "participant_profiles.id" in where_text
    assert "participant_profiles.company_id" in where_text


@pytest.mark.asyncio
async def test_register_requires_terms_acceptance() -> None:
    mock_session = AsyncMock()
    service = IdentityService(mock_session)
    payload = RegisterRequest(
        email="test@example.com",
        password="securepassword123",
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
        password="securepassword123",
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
        password="securepassword123",
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
