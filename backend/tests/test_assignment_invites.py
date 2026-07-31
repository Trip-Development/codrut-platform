import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.task_links import TaskLinkClaims, create_task_token
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
)
from codrut.modules.forms.service import FormsService
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    AssignmentInvite,
    Session,
    User,
    UserAccountType,
    UserRole,
)
from codrut.modules.identity.repository import hash_session_token
from codrut.modules.identity.service import IdentityService
from codrut.modules.participants.service import ParticipantWorkspaceService


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
        self.executed_queries: list[Any] = []
        self.flushed = False

    async def execute(self, query: Any) -> Any:
        self.executed_queries.append(query)
        if not self.side_effects:
            raise RuntimeError("No mock result configured in FakeSession")
        return self.side_effects.pop(0)

    def add(self, model: Any) -> None:
        self.added_models.append(model)

    async def flush(self) -> None:
        self.flushed = True


async def test_invite_bound_trainer_account_has_participant_only_effective_role() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            company = Company(id=uuid.uuid4(), name=f"Trainer Invite {uuid.uuid4().hex[:8]}")
            user = User(
                id=uuid.uuid4(),
                email=f"trainer-invite-{uuid.uuid4().hex[:8]}@example.com",
                password_hash="registered-password-hash",  # noqa: S106
                role=UserRole.trainer,
            )
            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                email=user.email,
                full_name="Trainer As Participant",
            )
            session.add_all([company, user])
            await session.flush()
            session.add(profile)
            await session.flush()
            expires_at = datetime.now(UTC) + timedelta(hours=1)
            invite_token = create_task_token(
                TaskLinkClaims(
                    company_id=company.id,
                    respondent_profile_id=profile.id,
                    assignment_ids=(uuid.uuid4(),),
                    expires_at=expires_at,
                ),
                get_settings(),
            )
            invite = AssignmentInvite(
                id=uuid.uuid4(),
                company_id=company.id,
                respondent_profile_id=profile.id,
                token=invite_token,
                status="active",
                expires_at=expires_at,
            )
            session.add(invite)
            await session.flush()
            session.add_all(
                [
                    Session(
                        user_id=user.id,
                        token_hash=hash_session_token("normal-trainer-session"),
                        expires_at=expires_at,
                    ),
                    Session(
                        user_id=user.id,
                        token_hash=hash_session_token("invite-bound-session"),
                        expires_at=expires_at,
                        assignment_invite_id=invite.id,
                    ),
                ]
            )
            await session.flush()

            service = IdentityService(session)
            normal_principal = await service.principal_from_session_token(
                "normal-trainer-session"
            )
            invite_principal = await service.principal_from_session_token(
                "invite-bound-session"
            )

            assert normal_principal is not None
            assert normal_principal.role == UserRole.trainer
            assert invite_principal is not None
            assert invite_principal.role == UserRole.participant
            assert invite_principal.assignment_ids is not None
            await session.rollback()
    finally:
        await engine.dispose()


async def test_project_scoped_invites_and_sessions_are_independent(
    questionnaire_definition_factory,
) -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            company = Company(id=uuid.uuid4(), name="Multi-project Company")
            user = User(
                id=uuid.uuid4(),
                email=f"multi-project-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
                role=UserRole.participant,
                account_type=UserAccountType.guest,
            )
            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                email=user.email,
                full_name="Participant Multi Project",
            )
            project_a = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Project Alpha",
                status=CompanyProjectStatus.active,
            )
            project_b = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Project Beta",
                status=CompanyProjectStatus.active,
            )
            lencioni_definition = questionnaire_definition_factory("lencioni")
            distress_definition = questionnaire_definition_factory("distress_drivers")
            assignment_a = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project_a.id,
                respondent_profile_id=profile.id,
                questionnaire_key="lencioni",
                questionnaire_definition_id=lencioni_definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.assigned,
            )
            assignment_b = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project_b.id,
                respondent_profile_id=profile.id,
                questionnaire_key="distress_drivers",
                questionnaire_definition_id=distress_definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.assigned,
            )
            session.add_all([company, user, lencioni_definition, distress_definition])
            await session.flush()
            session.add_all([profile, project_a, project_b])
            await session.flush()
            session.add_all([assignment_a, assignment_b])
            await session.flush()

            service = IdentityService(session)
            invite_a = await service.create_invite(
                company.id,
                profile.id,
                assignment_ids=[assignment_a.id],
                project_id=project_a.id,
            )
            invite_b = await service.create_invite(
                company.id,
                profile.id,
                assignment_ids=[assignment_b.id],
                project_id=project_b.id,
            )
            session.add_all(
                [
                    Session(
                        user_id=user.id,
                        token_hash=hash_session_token("project-a-session"),
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        assignment_invite_id=invite_a.id,
                    ),
                    Session(
                        user_id=user.id,
                        token_hash=hash_session_token("project-b-session"),
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        assignment_invite_id=invite_b.id,
                    ),
                ]
            )
            await session.flush()

            rotated_a = await service.create_invite(
                company.id,
                profile.id,
                assignment_ids=[assignment_a.id],
                project_id=project_a.id,
                force_rotate=True,
            )

            assert invite_a.status == "revoked"
            assert invite_b.status == "active"
            assert rotated_a.project_id == project_a.id
            assert invite_b.project_id == project_b.id
            remaining_sessions = list(
                (await session.execute(select(Session).where(Session.user_id == user.id)))
                .scalars()
                .all()
            )
            assert {stored.assignment_invite_id for stored in remaining_sessions} == {invite_b.id}

            principal_b = await service.principal_from_session_token("project-b-session")
            assert principal_b is not None
            assert principal_b.project_id == project_b.id
            assert principal_b.assignment_ids == (assignment_b.id,)

            workspace = await ParticipantWorkspaceService(session).get_workspace_summary(
                user.id,
                allowed_assignment_ids=principal_b.assignment_ids,
                scoped_project_id=principal_b.project_id,
            )
            assert [task.assignmentId for task in workspace.tasks] == [str(assignment_b.id)]
            assert workspace.tasks[0].projectId == project_b.id
            assert workspace.tasks[0].projectName == project_b.name
            assert [project.id for project in workspace.questionnaire_projects] == [
                project_b.id
            ]

            with pytest.raises(DomainError) as exc_info:
                await FormsService(session).get_assignment_response(
                    user.id,
                    assignment_a.id,
                    allowed_assignment_ids=principal_b.assignment_ids,
                )
            assert exc_info.value.code == "assignment_not_found"

            await session.rollback()
    finally:
        await engine.dispose()


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
        id=uuid.uuid4(),
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
        expires_at=claims.expires_at,
    )

    assert invite == existing_invite
    assert len(session.added_models) == 0  # No new model added


@pytest.mark.asyncio
async def test_create_invite_rotates_existing_invite_when_expiry_is_shortened() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    session = FakeSession()
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        email="test@example.com",
        full_name="Test User",
    )
    result_profile = FakeScalarResult(profile)
    result_assignments = FakeScalarsResult([assignment_id])

    settings = get_settings()
    old_expiry = datetime.now(UTC) + timedelta(days=10)
    shortened_expiry = datetime.now(UTC) + timedelta(days=2)
    claims = TaskLinkClaims(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        assignment_ids=(assignment_id,),
        expires_at=old_expiry,
    )
    existing_invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=create_task_token(claims, settings),
        status="active",
        expires_at=old_expiry,
    )
    result_active_invite = FakeScalarsResult(existing_invite)
    result_to_invalidate = FakeScalarsResult([existing_invite])

    session.side_effects = [
        result_profile,
        result_assignments,
        result_active_invite,
        result_to_invalidate,
        FakeScalarResult(),
    ]

    service = IdentityService(session)
    invite = await service.create_invite(
        company_id=company_id,
        respondent_profile_id=respondent_id,
        assignment_ids=[assignment_id],
        expires_at=shortened_expiry,
    )

    assert invite != existing_invite
    assert invite.expires_at == shortened_expiry
    assert existing_invite.status == "revoked"
    assert len(session.added_models) == 1


@pytest.mark.asyncio
async def test_create_invite_force_rotate_invalidates_previous_invites() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    session = FakeSession()

    # 1. ParticipantProfile lookup
    shadow_user_id = uuid.uuid4()
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        user_id=shadow_user_id,
        email="test@example.com",
        full_name="Test User",
    )
    result_profile = FakeScalarResult(profile)

    # 2. QuestionnaireAssignment scope lookup
    result_assignments = FakeScalarsResult([assignment_id])

    # 3. invalidate_invites_for_respondent lookup -> returns existing active invite to revoke
    existing_invite = AssignmentInvite(
        id=uuid.uuid4(),
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
        FakeScalarResult(),
        FakeScalarResult(),
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
    delete_queries = [
        str(query) for query in session.executed_queries if "DELETE FROM sessions" in str(query)
    ]
    assert any("sessions.assignment_invite_id" in query for query in delete_queries)
    assert any("users.account_type" in query for query in delete_queries)


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
        scope_checked = False

        async def execute(self, query: Any) -> Any:
            where_text = " ".join(str(clause) for clause in query._where_criteria)
            if (
                "participant_profiles.id" in where_text
                and "participant_profiles.company_id" in where_text
            ):
                assert "participant_profiles.email" not in where_text
                assert "participant_profiles.id" in where_text
                assert "participant_profiles.company_id" in where_text
                self.scope_checked = True
            return await super().execute(query)

    session = ScopedFakeSession()
    session.side_effects = [
        FakeScalarResult(invite),
        FakeScalarResult(profile),
        FakeScalarResult(company),
        FakeScalarResult(False),
        FakeScalarsResult([assignment]),
        FakeScalarResult(None),
        FakeScalarResult(profile),
        FakeScalarResult(None),
        FakeScalarResult(False),
    ]

    result = await IdentityService(session).verify_invite_token_and_create_session(token)

    assert result.response.action == "secure_link_ready"
    assert result.response.participant_profile_id == profile.id
    assert result.session_token
    assert session.scope_checked
    assert profile.user_id is not None
    assert any(isinstance(model, User) for model in session.added_models)
    assert any(isinstance(model, Session) for model in session.added_models)
    created_session = next(model for model in session.added_models if isinstance(model, Session))
    assert created_session.assignment_invite_id == invite.id
    assert int(created_session.expires_at.timestamp()) == int(expires_at.timestamp())


@pytest.mark.asyncio
async def test_verify_invite_for_project_uses_project_close_as_effective_expiry() -> None:
    company_id = uuid.uuid4()
    project_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    session = FakeSession()
    settings = get_settings()
    token_expires_at = datetime.now(UTC) + timedelta(days=10)
    project_closes_at = datetime.now(UTC) + timedelta(days=3)
    token = create_task_token(
        TaskLinkClaims(
            company_id=company_id,
            respondent_profile_id=respondent_id,
            assignment_ids=(assignment_id,),
            expires_at=token_expires_at,
        ),
        settings,
    )
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=token,
        status="active",
        expires_at=token_expires_at,
    )
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        email="same.person@example.com",
        full_name="Same Person",
    )
    assignment = QuestionnaireAssignment(
        id=assignment_id,
        company_id=company_id,
        project_id=project_id,
        respondent_profile_id=respondent_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )
    project = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="July Pilot",
        form_closes_at=project_closes_at,
    )
    session.side_effects = [
        FakeScalarResult(invite),
        FakeScalarResult(profile),
        FakeScalarResult(Company(id=company_id, name="Michelin")),
        FakeScalarResult(False),
        FakeScalarsResult([assignment]),
        FakeScalarResult(project),
        FakeScalarResult(None),
        FakeScalarResult(profile),
        FakeScalarResult(None),
        FakeScalarResult(False),
    ]

    result = await IdentityService(session).verify_invite_token_and_create_session(token)

    assert result.response.action == "secure_link_ready"
    assert result.response.project_id == project_id
    created_session = next(model for model in session.added_models if isinstance(model, Session))
    assert created_session.assignment_invite_id == invite.id
    assert created_session.expires_at == project_closes_at


@pytest.mark.asyncio
async def test_verify_invite_rejects_closed_project_window() -> None:
    company_id = uuid.uuid4()
    project_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    settings = get_settings()
    token_expires_at = datetime.now(UTC) + timedelta(days=10)
    token = create_task_token(
        TaskLinkClaims(
            company_id=company_id,
            respondent_profile_id=respondent_id,
            assignment_ids=(assignment_id,),
            expires_at=token_expires_at,
        ),
        settings,
    )
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token=token,
        status="active",
        expires_at=token_expires_at,
    )
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        email="same.person@example.com",
        full_name="Same Person",
    )
    assignment = QuestionnaireAssignment(
        id=assignment_id,
        company_id=company_id,
        project_id=project_id,
        respondent_profile_id=respondent_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
    )
    project = CompanyProject(
        id=project_id,
        company_id=company_id,
        name="July Pilot",
        form_closes_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session = FakeSession()
    session.side_effects = [
        FakeScalarResult(invite),
        FakeScalarResult(profile),
        FakeScalarResult(Company(id=company_id, name="Michelin")),
        FakeScalarResult(False),
        FakeScalarsResult([assignment]),
        FakeScalarResult(project),
    ]

    with pytest.raises(DomainError) as exc_info:
        await IdentityService(session).verify_invite_token_and_create_session(token)

    assert exc_info.value.code == "project_closed"


@pytest.mark.asyncio
async def test_registered_user_must_log_in_before_claiming_unlinked_profile() -> None:
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
        email="known.member@example.com",
        full_name="Known Member",
    )
    existing_user = User(
        id=user_id,
        email="known.member@example.com",
        password_hash="existing",  # noqa: S106
        role=UserRole.participant,
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
        FakeScalarResult(existing_user),
        FakeScalarResult(profile),
        FakeScalarResult(existing_user),
    ]

    result = await IdentityService(session).verify_invite_token_and_create_session(token)

    assert result.response.action == "login_required"
    assert result.session_token is None
    assert profile.user_id is None
    assert not any(isinstance(model, User) for model in session.added_models)
    assert not any(isinstance(model, Session) for model in session.added_models)


@pytest.mark.asyncio
async def test_registered_linked_user_must_log_in_before_dashboard_access() -> None:
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
        email="linked.member@example.com",
        full_name="Linked Member",
    )
    linked_user = User(
        id=user_id,
        email="linked.member@example.com",
        password_hash="existing",  # noqa: S106
        role=UserRole.participant,
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
        FakeScalarResult(linked_user),
        FakeScalarResult(False),
        FakeScalarsResult([assignment]),
        FakeScalarResult(profile),
        FakeScalarResult(linked_user),
    ]

    result = await IdentityService(session).verify_invite_token_and_create_session(token)

    assert result.response.action == "login_required"
    assert result.session_token is None
    assert profile.user_id == user_id
    assert not any(isinstance(model, User) for model in session.added_models)
    assert not any(isinstance(model, Session) for model in session.added_models)


@pytest.mark.asyncio
async def test_revoke_invite_revokes_lineage_and_legacy_shadow_sessions() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    shadow_user_id = uuid.uuid4()
    invite = AssignmentInvite(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=respondent_id,
        token="invite-token",  # noqa: S106
        status="active",
        expires_at=datetime.now(UTC) + timedelta(days=5),
    )
    profile = ParticipantProfile(
        id=respondent_id,
        company_id=company_id,
        user_id=shadow_user_id,
        email="shadow@example.com",
        full_name="Shadow Participant",
    )
    session = FakeSession()
    session.side_effects = [
        FakeScalarResult(profile),
        FakeScalarsResult([invite]),
        FakeScalarResult(),
        FakeScalarResult(),
    ]

    await IdentityService(session).invalidate_invite(company_id, respondent_id)

    assert invite.status == "revoked"
    delete_queries = [
        str(query) for query in session.executed_queries if "DELETE FROM sessions" in str(query)
    ]
    assert any("sessions.assignment_invite_id" in query for query in delete_queries)
    assert any("users.account_type" in query for query in delete_queries)


@pytest.mark.asyncio
async def test_revoke_invite_deletes_only_invite_and_shadow_sessions_in_database() -> None:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    shadow_user_id = uuid.uuid4()
    regular_user_id = uuid.uuid4()
    invite_id = uuid.uuid4()
    lineage_session_id = uuid.uuid4()
    legacy_shadow_session_id = uuid.uuid4()
    regular_session_id = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=5)

    try:
        async with SessionLocal() as session:
            session.add_all(
                [
                    Company(id=company_id, name=f"Invite revoke {uuid.uuid4().hex}"),
                        User(
                            id=shadow_user_id,
                            email=f"shadow-{uuid.uuid4().hex}@example.com",
                            password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
                            role=UserRole.participant,
                            account_type=UserAccountType.guest,
                        ),
                    User(
                        id=regular_user_id,
                        email=f"regular-{uuid.uuid4().hex}@example.com",
                        password_hash="registered-password-hash",  # noqa: S106
                        role=UserRole.participant,
                    ),
                ]
            )
            await session.flush()
            session.add(
                ParticipantProfile(
                    id=respondent_id,
                    company_id=company_id,
                    user_id=shadow_user_id,
                    email=f"participant-{uuid.uuid4().hex}@example.com",
                    full_name="Shadow Participant",
                )
            )
            await session.flush()
            session.add(
                AssignmentInvite(
                    id=invite_id,
                    company_id=company_id,
                    respondent_profile_id=respondent_id,
                    token=f"invite-{uuid.uuid4().hex}",
                    status="active",
                    expires_at=expires_at,
                )
            )
            await session.flush()
            session.add_all(
                [
                    Session(
                        id=lineage_session_id,
                        user_id=shadow_user_id,
                        token_hash=uuid.uuid4().hex * 2,
                        expires_at=expires_at,
                        assignment_invite_id=invite_id,
                    ),
                    Session(
                        id=legacy_shadow_session_id,
                        user_id=shadow_user_id,
                        token_hash=uuid.uuid4().hex * 2,
                        expires_at=expires_at,
                    ),
                    Session(
                        id=regular_session_id,
                        user_id=regular_user_id,
                        token_hash=uuid.uuid4().hex * 2,
                        expires_at=expires_at,
                    ),
                ]
            )
            await session.flush()

            await IdentityService(session).invalidate_invite(company_id, respondent_id)
            remaining_session_ids = set((await session.execute(select(Session.id))).scalars().all())
            persisted_invite = await session.get(AssignmentInvite, invite_id)

            assert persisted_invite is not None
            assert persisted_invite.status == "revoked"
            assert lineage_session_id not in remaining_session_ids
            assert legacy_shadow_session_id not in remaining_session_ids
            assert regular_session_id in remaining_session_ids
            await session.rollback()
    finally:
        await engine.dispose()
