import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from codrut.core.config import get_settings
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.task_links import TaskLinkClaims, create_task_token
from codrut.modules.companies.models import Company, ParticipantProfile
from codrut.modules.identity.models import AssignmentInvite, Session, User
from codrut.modules.identity.service import IdentityService


class FakeScalarResult:
    def __init__(self, val: Any = None) -> None:
        self.val = val

    def scalars(self) -> Any:
        return self

    def scalar_one_or_none(self) -> Any:
        return self.val

    def first(self) -> Any:
        return self.val

    def scalar(self) -> Any:
        return self.val

    def all(self) -> list[Any]:
        return [self.val] if self.val is not None else []


class FakeScalarsResult:
    def __init__(self, val: Any = None) -> None:
        self.val = val

    def scalars(self) -> Any:
        return self

    def first(self) -> Any:
        return self.val

    def all(self) -> list[Any]:
        if isinstance(self.val, list):
            return self.val
        return [self.val] if self.val is not None else []


class FakeSession:
    def __init__(self) -> None:
        self.side_effects: list[Any] = []
        self.added_models: list[Any] = []
        self.flushed = False

    async def execute(self, query: Any) -> Any:
        if not self.side_effects:
            raise RuntimeError("No mock result configured in FakeSession")
        return self.side_effects.pop(0)

    def add(self, model: Any) -> None:
        self.added_models.append(model)

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
async def test_create_invite_success() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    session = FakeSession()

    # 1. ParticipantProfile lookup
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        email="test@example.com",
        full_name="Test User",
    )
    result_profile = FakeScalarResult(profile)

    # 2. QuestionnaireAssignment scope lookup
    result_assignments = FakeScalarsResult([assignment_id])

    # 3. get_active_invite_by_respondent lookup -> None
    result_active_invite = FakeScalarsResult(None)

    # 4. invalidate_invites_for_respondent lookup -> returns empty list
    result_invalidate_invite = FakeScalarsResult([])

    session.side_effects = [
        result_profile,
        result_assignments,
        result_active_invite,
        result_invalidate_invite,
    ]

    service = IdentityService(session)
    invite = await service.create_invite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
    )

    assert invite.company_id == company_id
    assert invite.respondent_profile_id == respondent_id
    assert invite.status == "active"
    assert invite.token is not None
    assert invite.expires_at > datetime.now(UTC)
    assert len(session.added_models) == 1
    assert isinstance(session.added_models[0], AssignmentInvite)


@pytest.mark.asyncio
async def test_create_invite_idempotency_reuses_active_invite() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    session = FakeSession()

    # 1. ParticipantProfile lookup
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        email="test@example.com",
        full_name="Test User",
    )
    result_profile = FakeScalarResult(profile)

    # 2. QuestionnaireAssignment scope lookup
    result_assignments = FakeScalarsResult([assignment_id])

    # 3. get_active_invite_by_respondent lookup -> returns existing active invite
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        assignment_ids=(assignment_id,),
        expires_at=datetime.now(UTC) + timedelta(days=10),
    )
    token = create_task_token(claims, settings)
    existing_invite = AssignmentInvite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=token,
        status="active",
        expires_at=claims.expires_at,
    )
    result_active_invite = FakeScalarsResult(existing_invite)

    session.side_effects = [
        result_profile,
        result_assignments,
        result_active_invite,
    ]

    service = IdentityService(session)
    invite = await service.create_invite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        assignment_ids=[assignment_id],
    )

    assert invite == existing_invite
    assert len(session.added_models) == 0  # No new model added


@pytest.mark.asyncio
async def test_create_invite_force_rotate_invalidates_previous_invites() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    session = FakeSession()

    # 1. ParticipantProfile lookup
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        email="test@example.com",
        full_name="Test User",
    )
    result_profile = FakeScalarResult(profile)

    # 2. QuestionnaireAssignment scope lookup
    result_assignments = FakeScalarsResult([assignment_id])

    # 3. invalidate_invites_for_respondent lookup -> returns existing active invite to revoke
    existing_invite = AssignmentInvite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token="some_token",  # noqa: S106
        status="active",
        expires_at=datetime.now(UTC) + timedelta(days=5),
    )
    result_to_invalidate = FakeScalarsResult([existing_invite])

    session.side_effects = [
        result_profile,
        result_assignments,
        result_to_invalidate,
    ]

    service = IdentityService(session)
    invite = await service.create_invite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        assignment_ids=[assignment_id],
        force_rotate=True,
    )

    assert existing_invite.status == "revoked"
    assert invite.status == "active"
    assert invite != existing_invite
    assert len(session.added_models) == 1


@pytest.mark.asyncio
async def test_create_invite_rejects_explicit_assignment_outside_respondent_scope() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    other_assignment_id = uuid.uuid4()

    session = FakeSession()
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        email="test@example.com",
        full_name="Test User",
    )
    session.side_effects = [
        FakeScalarResult(profile),
        FakeScalarsResult([]),
    ]

    service = IdentityService(session)
    with pytest.raises(DomainError) as exc_info:
        await service.create_invite(
            company_id=company_id,
            respondent_profile_id=respondent_id,
            assignment_ids=[other_assignment_id],
        )

    assert exc_info.value.code == "assignment_scope_mismatch"
    assert session.added_models == []


@pytest.mark.asyncio
async def test_verify_invite_token_revoked() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    session = FakeSession()

    # Create a revoked invite
    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        assignment_ids=(assignment_id,),
        expires_at=datetime.now(UTC) + timedelta(days=5),
    )
    token = create_task_token(claims, settings)
    revoked_invite = AssignmentInvite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=token,
        status="revoked",
        expires_at=claims.expires_at,
    )
    result_invite = FakeScalarResult(revoked_invite)

    session.side_effects = [
        result_invite,
    ]

    service = IdentityService(session)
    with pytest.raises(DomainError, match="revoked or used"):
        await service.verify_invite_token(token)


@pytest.mark.asyncio
async def test_verify_invite_token_expired() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    session = FakeSession()

    # To test the DB expiration check specifically:
    # let's set claims.expires_at to future, but make the DB invite expires_at past.
    settings = get_settings()
    claims_future = TaskLinkClaims(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        assignment_ids=(assignment_id,),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token_future = create_task_token(claims_future, settings)
    expired_invite = AssignmentInvite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=token_future,
        status="active",
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    result_invite = FakeScalarResult(expired_invite)

    session.side_effects = [
        result_invite,
    ]

    service = IdentityService(session)
    with pytest.raises(DomainError, match="expired"):
        await service.verify_invite_token(token_future)


@pytest.mark.asyncio
async def test_verify_invite_token_rejects_missing_persisted_invite() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    settings = get_settings()
    claims = TaskLinkClaims(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        assignment_ids=(assignment_id,),
        expires_at=datetime.now(UTC) + timedelta(days=5),
    )
    token = create_task_token(claims, settings)
    session = FakeSession()
    session.side_effects = [FakeScalarResult(None)]

    service = IdentityService(session)
    with pytest.raises(DomainError) as exc_info:
        await service.verify_invite_token(token)

    assert exc_info.value.code == "task_link_revoked"


@pytest.mark.asyncio
async def test_verify_invite_for_non_leadership_creates_scoped_shadow_session() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    session = FakeSession()
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(days=5)
    claims = TaskLinkClaims(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        assignment_ids=(assignment_id,),
        expires_at=expires_at,
    )
    token = create_task_token(claims, settings)
    invite = AssignmentInvite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=token,
        status="active",
        expires_at=expires_at,
    )
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        email="same.person@example.com",
        full_name="Same Person",
    )
    company = Company(id=company_id, name="Michelin")
    assignment = QuestionnaireAssignment(
        id=assignment_id,
        company_id=company_id,
        respondent_profile_id=respondent_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )

    class ScopedFakeSession(FakeSession):
        async def execute(self, query: Any) -> Any:
            if len(self.side_effects) == 2:
                where_text = " ".join(str(clause) for clause in query._where_criteria)
                assert "participant_profiles.email" not in where_text
                assert "participant_profiles.id" in where_text
                assert "participant_profiles.company_id" in where_text
            return await super().execute(query)

    session = ScopedFakeSession()
    session.side_effects = [
        FakeScalarResult(invite),
        FakeScalarResult(profile),
        FakeScalarResult(company),
        FakeScalarResult(False),
        FakeScalarsResult([assignment]),
        FakeScalarResult(profile),
        FakeScalarResult(None),
    ]

    result = await IdentityService(session).verify_invite_token_and_create_session(token)

    assert result.response.email == profile.email
    assert result.response.is_leadership is False
    assert result.session_token
    assert len(result.response.tasks) == 1
    assert profile.user_id is not None
    assert any(isinstance(model, User) for model in session.added_models)
    assert any(isinstance(model, Session) for model in session.added_models)


@pytest.mark.asyncio
async def test_verify_invite_for_non_leadership_reuses_existing_email_user() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    user_id = uuid.uuid4()

    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(days=5)
    token = create_task_token(
        TaskLinkClaims(
            company_id=company_id,
            respondent_profile_id=respondent_id,
            assignment_ids=(assignment_id,),
            expires_at=expires_at,
        ),
        settings,
    )
    invite = AssignmentInvite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=token,
        status="active",
        expires_at=expires_at,
    )
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        email="known.member@example.com",
        full_name="Known Member",
    )
    existing_user = User(
        id=user_id,
        email="known.member@example.com",
        password_hash="existing",  # noqa: S106
        role="participant",
    )
    assignment = QuestionnaireAssignment(
        id=assignment_id,
        company_id=company_id,
        respondent_profile_id=respondent_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )

    session = FakeSession()
    session.side_effects = [
        FakeScalarResult(invite),
        FakeScalarResult(profile),
        FakeScalarResult(Company(id=company_id, name="Michelin")),
        FakeScalarResult(False),
        FakeScalarsResult([assignment]),
        FakeScalarResult(profile),
        FakeScalarResult(existing_user),
    ]

    result = await IdentityService(session).verify_invite_token_and_create_session(token)

    assert result.session_token
    assert profile.user_id == user_id
    assert not any(isinstance(model, User) for model in session.added_models)
    assert any(isinstance(model, Session) for model in session.added_models)
