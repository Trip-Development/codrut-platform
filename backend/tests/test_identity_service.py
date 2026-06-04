# ruff: noqa: S106
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from codrut.core.config import get_settings
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.task_links import TaskLinkClaims, create_task_token
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import RegisterRequest
from codrut.modules.identity.service import IdentityService


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
        mock_result_leadership,
        mock_result_assignments,
    ]

    service = IdentityService(mock_session)
    result = await service.verify_invite_token(token)

    assert result.email == "test@example.com"
    assert result.full_name == "Test User"
    assert result.is_leadership is True
    assert result.already_registered is False
    assert len(result.tasks) == 1
    assert result.tasks[0].id == str(mock_assignment.id)


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

    # 6. select(ParticipantProfile) in register (to link the user_id)
    mock_result_profile_link = MagicMock()
    mock_result_profile_link.scalar_one_or_none.return_value = mock_profile

    mock_session.execute.side_effect = [
        mock_result_profile,
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
    )
    auth_result = await service.register(payload)

    assert auth_result.response.email == "test@example.com"
    assert auth_result.response.role == UserRole.participant
    assert mock_profile.user_id is not None


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
        mock_result_leadership,
        mock_result_assignments,
    ]

    service = IdentityService(mock_session)
    payload = RegisterRequest(
        email="test@example.com",
        password="securepassword123",
        token=token,
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
        mock_result_leadership,
        mock_result_assignments,
    ]

    service = IdentityService(mock_session)
    payload = RegisterRequest(
        email="attacker@example.com",
        password="securepassword123",
        token=token,
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

    mock_session.execute.side_effect = [
        mock_result_profile,
        mock_result_leadership,
        mock_result_assignments,
        mock_result_profile_again,
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
        mock_result_leadership,
        mock_result_assignments,
        mock_result_profile_again,
    ]

    service = IdentityService(mock_session)
    result = await service.verify_invite_token_and_create_session(token)

    assert result.response.email == "leader@example.com"
    assert result.response.is_leadership is True
    assert result.session_token is None  # Leadership must register manually to get a session
