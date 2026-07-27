import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus, AssignmentTargetType
from codrut.modules.identity.models import Session, User, UserRole
from codrut.modules.identity.schemas import (
    ConsentRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    SessionPrincipal,
)
from codrut.modules.identity.service import (
    IdentityService,
    _invite_task_copy,
    _min_datetime,
    _validate_project_access_window,
)
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.participants.schemas import (
    ParticipantWorkspaceContext,
    ParticipantWorkspaceCycle,
    ParticipantWorkspaceProject,
)
from codrut.modules.participants.service import (
    ParticipantWorkspaceService,
    _definition_scale_max,
    _definition_score_labels,
    _extract_numeric_score,
    _format_deadline,
    _positive_int,
    _prettify_score_key,
    _schema_score_labels,
    _task_status,
)


def _identity_service() -> tuple[IdentityService, MagicMock]:
    session = AsyncMock()
    repository = MagicMock()
    repository.session = session
    service = IdentityService(session)
    service.repository = repository
    return service, repository


@pytest.mark.asyncio
async def test_login_rejects_unknown_and_wrong_password_without_creating_session() -> None:
    service, repository = _identity_service()
    service._create_session = AsyncMock()  # type: ignore[method-assign]
    payload = LoginRequest(
        email="participant@example.com",
        password="wrong password",  # noqa: S106
    )

    repository.get_user_by_email = AsyncMock(return_value=None)
    with pytest.raises(DomainError, match="Invalid email or password") as missing_error:
        await service.login(payload)
    assert missing_error.value.code == "invalid_credentials"

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash="stored-password-hash",  # noqa: S106
        role=UserRole.participant,
    )
    repository.get_user_by_email = AsyncMock(return_value=user)
    with (
        patch("codrut.modules.identity.service.verify_password", return_value=False),
        pytest.raises(DomainError, match="Invalid email or password") as password_error,
    ):
        await service.login(payload)

    assert password_error.value.code == "invalid_credentials"
    service._create_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_creates_session_only_after_password_verification() -> None:
    service, repository = _identity_service()
    user = User(
        id=uuid.uuid4(),
        email="participant@example.com",
        password_hash="stored-password-hash",  # noqa: S106
        role=UserRole.participant,
    )
    repository.get_user_by_email = AsyncMock(return_value=user)
    service._create_session = AsyncMock(return_value="new-session")  # type: ignore[method-assign]

    with patch("codrut.modules.identity.service.verify_password", return_value=True):
        result = await service.login(
            LoginRequest(email=user.email, password="correct password")  # noqa: S106
        )

    assert result.session_token == "new-session"  # noqa: S105
    assert result.response.user_id == user.id
    service._create_session.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_password_mutations_reject_missing_accounts_without_side_effects() -> None:
    service, repository = _identity_service()
    reset_token = SimpleNamespace(user_id=uuid.uuid4())
    repository.get_active_password_reset_token = AsyncMock(return_value=reset_token)
    repository.get_user_by_id = AsyncMock(return_value=None)
    repository.revoke_password_reset_tokens_for_user = AsyncMock()
    repository.delete_sessions_for_user = AsyncMock()

    with pytest.raises(DomainError, match="Contul nu mai există") as reset_error:
        await service.confirm_password_reset(
            PasswordResetConfirmRequest(
                token="r" * 32,
                password="a sufficiently long replacement passphrase",  # noqa: S106
            )
        )
    assert reset_error.value.code == "user_not_found"

    with pytest.raises(DomainError, match="Contul nu mai există") as change_error:
        await service.change_password(
            uuid.uuid4(),
            PasswordChangeRequest(
                current_password="current password",  # noqa: S106
                new_password="a sufficiently long replacement passphrase",  # noqa: S106
            ),
        )
    assert change_error.value.code == "user_not_found"
    repository.revoke_password_reset_tokens_for_user.assert_not_awaited()
    repository.delete_sessions_for_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_terms_acceptance_rejects_missing_consent_and_missing_user() -> None:
    service, repository = _identity_service()
    repository.get_user_by_id = AsyncMock(return_value=None)

    with pytest.raises(DomainError, match="must be accepted") as consent_error:
        await service.accept_terms(
            uuid.uuid4(),
            ConsentRequest(terms_accepted=False, terms_version=CURRENT_TERMS_VERSION),
        )
    assert consent_error.value.code == "terms_required"

    with pytest.raises(DomainError, match="Authenticated user was not found") as user_error:
        await service.accept_terms(
            uuid.uuid4(),
            ConsentRequest(terms_accepted=True, terms_version=CURRENT_TERMS_VERSION),
        )
    assert user_error.value.code == "user_not_found"


@pytest.mark.asyncio
async def test_invite_project_context_rejects_scope_mismatch_and_missing_project() -> None:
    service, repository = _identity_service()
    company_id = uuid.uuid4()
    assignment_project_id = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=1)
    assignment = SimpleNamespace(project_id=assignment_project_id)

    with pytest.raises(DomainError, match="does not match its project") as scope_error:
        await service._invite_project_context(
            company_id,
            "Synthetic company",
            [assignment],
            expires_at,
            uuid.uuid4(),
        )
    assert scope_error.value.code == "task_link_scope_mismatch"

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    repository.session.execute = AsyncMock(return_value=result)
    context = await service._invite_project_context(
        company_id,
        "Synthetic company",
        [assignment],
        expires_at,
        None,
    )
    assert context == (None, "Synthetic company", expires_at)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "accepted_at", "terms_version"),
    [
        (UserRole.trainer, datetime.now(UTC), CURRENT_TERMS_VERSION),
        (UserRole.participant, None, CURRENT_TERMS_VERSION),
        (UserRole.participant, datetime.now(UTC), "retired-version"),
    ],
)
async def test_secure_link_requires_current_participant_consent(
    role: UserRole,
    accepted_at: datetime | None,
    terms_version: str,
) -> None:
    service, repository = _identity_service()
    repository.get_session_by_token = AsyncMock()
    principal = SessionPrincipal(
        user_id=uuid.uuid4(),
        email="participant@example.com",
        role=role,
        terms_accepted_at=accepted_at,
        terms_version=terms_version,
        session_token="database-session",  # noqa: S106
    )

    with pytest.raises(DomainError, match="must be accepted") as error:
        await service.require_secure_link_consent(principal, "invite-token")

    assert error.value.code == "terms_required"
    repository.get_session_by_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_secure_link_rejects_stale_or_cross_scoped_session_state() -> None:
    service, repository = _identity_service()
    user_id = uuid.uuid4()
    principal = SessionPrincipal(
        user_id=user_id,
        email="participant@example.com",
        role=UserRole.participant,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
        session_token="database-session",  # noqa: S106
    )
    repository.get_session_by_token = AsyncMock(return_value=None)

    with pytest.raises(DomainError, match="session is no longer active") as session_error:
        await service.require_secure_link_consent(principal, "invite-token")
    assert session_error.value.code == "session_invalid"

    active_session = Session(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash="token-hash",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    repository.get_session_by_token = AsyncMock(return_value=active_session)
    repository.get_invite_by_token = AsyncMock(return_value=None)
    with pytest.raises(DomainError, match="no longer active") as revoked_error:
        await service.require_secure_link_consent(principal, "invite-token")
    assert revoked_error.value.code == "task_link_revoked"

    invite = SimpleNamespace(
        id=uuid.uuid4(),
        status="active",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        respondent_profile_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
    )
    repository.get_invite_by_token = AsyncMock(return_value=invite)
    with pytest.raises(DomainError, match="has expired") as expired_error:
        await service.require_secure_link_consent(principal, "invite-token")
    assert expired_error.value.code == "task_link_expired"

    invite.expires_at = datetime.now(UTC) + timedelta(hours=1)
    active_session.assignment_invite_id = uuid.uuid4()
    with pytest.raises(DomainError, match="does not match") as invite_scope_error:
        await service.require_secure_link_consent(principal, "invite-token")
    assert invite_scope_error.value.code == "task_link_scope_mismatch"

    active_session.assignment_invite_id = None
    missing_profile_result = MagicMock()
    missing_profile_result.scalar_one_or_none.return_value = None
    repository.session.execute = AsyncMock(return_value=missing_profile_result)
    with pytest.raises(DomainError, match="does not belong") as profile_error:
        await service.require_secure_link_consent(principal, "invite-token")
    assert profile_error.value.code == "task_link_scope_mismatch"

    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = SimpleNamespace(
        id=invite.respondent_profile_id
    )
    repository.session.execute = AsyncMock(return_value=profile_result)
    repository.get_consent_acceptance = AsyncMock(
        return_value=SimpleNamespace(
            session_id=active_session.id,
            assignment_invite_id=uuid.uuid4(),
            respondent_profile_id=invite.respondent_profile_id,
        )
    )
    with pytest.raises(DomainError, match="Consent does not match") as consent_scope_error:
        await service.require_secure_link_consent(principal, "invite-token")
    assert consent_scope_error.value.code == "task_link_scope_mismatch"


@pytest.mark.asyncio
async def test_principal_resolution_rejects_stale_session_user_and_invite() -> None:
    service, repository = _identity_service()
    repository.get_session_by_token = AsyncMock(return_value=None)
    assert await service.principal_from_session_token("stale-session") is None

    active_session = Session(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash="token-hash",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    repository.get_session_by_token = AsyncMock(return_value=active_session)
    repository.get_user_by_id = AsyncMock(return_value=None)
    assert await service.principal_from_session_token("orphaned-session") is None

    user = User(
        id=active_session.user_id,
        email="participant@example.com",
        password_hash="stored-password-hash",  # noqa: S106
        role=UserRole.participant,
    )
    active_session.assignment_invite_id = uuid.uuid4()
    repository.get_user_by_id = AsyncMock(return_value=user)
    repository.get_invite_by_id = AsyncMock(return_value=None)
    assert await service.principal_from_session_token("revoked-invite-session") is None


def test_identity_copy_and_project_window_fallbacks_are_explicit() -> None:
    assert _invite_task_copy("custom_questionnaire") == (
        "Chestionar",
        "Completează formularul atribuit.",
        10,
    )
    with pytest.raises(ValueError, match="at least one datetime"):
        _min_datetime(None, None)

    now = datetime.now(UTC)
    with pytest.raises(DomainError, match="archived") as archived:
        _validate_project_access_window(
            SimpleNamespace(
                status="archived",
                form_opens_at=None,
                form_closes_at=None,
                due_at=None,
            ),
            now=now,
        )
    assert archived.value.code == "project_archived"

    with pytest.raises(DomainError, match="not open yet") as not_open:
        _validate_project_access_window(
            SimpleNamespace(
                form_opens_at=now + timedelta(minutes=1),
                form_closes_at=None,
                due_at=None,
            ),
            now=now,
        )
    assert not_open.value.code == "project_not_open"

    with pytest.raises(DomainError, match="has closed") as closed:
        _validate_project_access_window(
            SimpleNamespace(
                form_opens_at=None,
                form_closes_at=now - timedelta(minutes=1),
                due_at=None,
            ),
            now=now,
        )
    assert closed.value.code == "project_closed"


def _assignment(
    *,
    target_type: AssignmentTargetType = AssignmentTargetType.self_assessment,
    status: AssignmentStatus = AssignmentStatus.assigned,
    project_id: uuid.UUID | None = None,
    target_person_id: uuid.UUID | None = None,
    target_team_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_id=project_id,
        assignment_round_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="synthetic_feedback",
        questionnaire_definition_id=uuid.uuid4(),
        target_type=target_type,
        target_person_id=target_person_id,
        target_team_id=target_team_id,
        status=status,
        due_at=None,
    )


def test_participant_schema_metadata_uses_safe_labels_and_scale_fallbacks() -> None:
    assert _definition_score_labels(None) == {}
    assert _schema_score_labels(None) == {}

    labels = _schema_score_labels(
        {
            "scoring": {
                "groups": [
                    None,
                    {"id": 1, "label": "Invalid"},
                    {"id": "blank", "label": " "},
                    {"id": "clarity", "label": "  Claritate  "},
                ],
                "drivers": [{"id": "support", "label": "Sprijin"}],
            },
            "sections": [
                None,
                {
                    "questions": [
                        None,
                        {"id": "ignored", "type": "text", "label": "Ignored"},
                        {
                            "id": "participant_label",
                            "type": "statement_score_set",
                            "label": "  Colaborare  ",
                        },
                    ]
                },
            ],
        }
    )
    assert labels == {
        "clarity": "Claritate",
        "support": "Sprijin",
        "participant_label": "Colaborare",
    }

    explicit_definition = SimpleNamespace(
        feedback_policy={"scale_max": 7},
        schema={},
        private_config=None,
    )
    assert _definition_scale_max(explicit_definition) == 7.0

    inferred_definition = SimpleNamespace(
        feedback_policy={"scale_max": True},
        schema={
            "sections": [
                None,
                {
                    "questions": [
                        None,
                        {
                            "scale": "invalid",
                            "statements": [
                                None,
                                {
                                    "scale": [
                                        None,
                                        {"value": True},
                                        {"value": 6},
                                    ]
                                },
                            ],
                        },
                    ]
                },
            ]
        },
        private_config={"schema": None},
    )
    assert _definition_scale_max(inferred_definition) == 6.0


def test_participant_value_helpers_cover_user_visible_fallbacks() -> None:
    assert _task_status(AssignmentStatus.submitted) == "completed"
    assert _task_status(AssignmentStatus.started) == "in_progress"
    assert _task_status(AssignmentStatus.assigned) == "not_started"
    assert _format_deadline(None) == "finalul evaluării"
    assert _format_deadline(datetime(2026, 8, 21, tzinfo=UTC)) == "21.08.2026"
    assert _extract_numeric_score({"score": 4}) == 4.0
    assert _extract_numeric_score("invalid") is None
    assert _prettify_score_key("team_support") == "Team Support"
    assert _prettify_score_key("") == ""
    assert _positive_int(True, 3) == 3
    assert _positive_int("invalid", 3) == 3
    assert _positive_int(0, 3) == 3
    assert _positive_int("4", 3) == 4


@pytest.mark.asyncio
async def test_participant_queries_short_circuit_empty_assignment_scope() -> None:
    session = AsyncMock()
    service = ParticipantWorkspaceService(session)
    profile = SimpleNamespace(id=uuid.uuid4(), company_id=uuid.uuid4())

    assert await service._list_assignments(profile, allowed_assignment_ids=()) == []
    assert await service._get_projects([]) == {}
    assert await service._get_teams([]) == {}
    assert await service._get_people([], profile.company_id) == {}
    assert await service._get_scoring_results([]) == {}
    assert await service._get_active_individual_publications(profile, []) == {}
    session.execute.assert_not_awaited()


def test_workspace_context_handles_no_project_and_multiple_projects() -> None:
    service = ParticipantWorkspaceService(AsyncMock())
    company = SimpleNamespace(name="Synthetic company")
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()
    projects = {
        project_a: SimpleNamespace(id=project_a, name="Project A", due_at=None),
        project_b: SimpleNamespace(id=project_b, name="Project B", due_at=None),
    }

    assert service._workspace_project(company, [], projects) == (None, "Synthetic company")
    assert service._workspace_project(
        company,
        [_assignment(project_id=project_a), _assignment(project_id=project_b)],
        projects,
    ) == (None, "Toate proiectele active")
    assert service._workspace_deadline([], projects) is None


@pytest.mark.asyncio
async def test_multi_profile_workspace_requires_explicit_context() -> None:
    service = ParticipantWorkspaceService(AsyncMock())
    profile_a = SimpleNamespace(id=uuid.uuid4())
    profile_b = SimpleNamespace(id=uuid.uuid4())
    company_a = SimpleNamespace(id=uuid.uuid4())
    company_b = SimpleNamespace(id=uuid.uuid4())
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()
    cycle_b = uuid.uuid4()
    contexts = [
        ParticipantWorkspaceContext(
            participant_profile_id=profile_a.id,
            participant_full_name="Participant A",
            participant_email="same@example.com",
            company_id=company_a.id,
            company_name="Company A",
            projects=[
                ParticipantWorkspaceProject(
                    id=project_a,
                    name="Program A",
                    deadline_label="finalul evaluării",
                )
            ],
        ),
        ParticipantWorkspaceContext(
            participant_profile_id=profile_b.id,
            participant_full_name="Participant B",
            participant_email="same@example.com",
            company_id=company_b.id,
            company_name="Company B",
            projects=[
                ParticipantWorkspaceProject(
                    id=project_b,
                    name="Program B",
                    deadline_label="finalul evaluării",
                    cycles=[
                        ParticipantWorkspaceCycle(
                            id=cycle_b,
                            project_id=project_b,
                            sequence=2,
                            name="Reevaluare 1",
                            status="active",
                        )
                    ],
                )
            ],
        ),
    ]
    rows = [(profile_a, company_a), (profile_b, company_b)]

    unresolved = await service._resolve_workspace_context(
        rows,
        contexts,
        participant_profile_id=None,
        project_id=None,
        cycle_id=None,
        allowed_assignment_ids=None,
        scoped_project_id=None,
    )
    selected_by_project = await service._resolve_workspace_context(
        rows,
        contexts,
        participant_profile_id=None,
        project_id=project_b,
        cycle_id=None,
        allowed_assignment_ids=None,
        scoped_project_id=None,
    )
    selected_by_cycle = await service._resolve_workspace_context(
        rows,
        contexts,
        participant_profile_id=profile_b.id,
        project_id=project_b,
        cycle_id=cycle_b,
        allowed_assignment_ids=None,
        scoped_project_id=None,
    )

    assert unresolved == (None, None, None, None)
    assert selected_by_project == (profile_b, company_b, project_b, cycle_b)
    assert selected_by_cycle == (profile_b, company_b, project_b, cycle_b)


@pytest.mark.asyncio
async def test_single_profile_with_multiple_projects_requires_program_selection() -> None:
    service = ParticipantWorkspaceService(AsyncMock())
    profile = SimpleNamespace(id=uuid.uuid4())
    company = SimpleNamespace(id=uuid.uuid4())
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()
    context = ParticipantWorkspaceContext(
        participant_profile_id=profile.id,
        participant_full_name="Participant",
        company_id=company.id,
        company_name="Company",
        projects=[
            ParticipantWorkspaceProject(
                id=project_a,
                name="Program A",
                deadline_label="finalul evaluării",
            ),
            ParticipantWorkspaceProject(
                id=project_b,
                name="Program B",
                deadline_label="finalul evaluării",
            ),
        ],
    )

    selected = await service._resolve_workspace_context(
        [(profile, company)],
        [context],
        participant_profile_id=None,
        project_id=None,
        cycle_id=None,
        allowed_assignment_ids=None,
        scoped_project_id=None,
    )

    assert selected == (None, None, None, None)
    assert {project.id for project in context.projects} == {project_a, project_b}


@pytest.mark.asyncio
async def test_multi_project_selection_response_preserves_program_contexts() -> None:
    session = AsyncMock()
    service = ParticipantWorkspaceService(session)
    profile = SimpleNamespace(id=uuid.uuid4())
    company = SimpleNamespace(id=uuid.uuid4())
    projects = [
        ParticipantWorkspaceProject(
            id=uuid.uuid4(),
            name="Program A",
            deadline_label="finalul evaluării",
        ),
        ParticipantWorkspaceProject(
            id=uuid.uuid4(),
            name="Program B",
            deadline_label="finalul evaluării",
        ),
    ]
    context = ParticipantWorkspaceContext(
        participant_profile_id=profile.id,
        participant_full_name="Participant",
        company_id=company.id,
        company_name="Company",
        projects=projects,
    )
    service._list_profiles_and_companies = AsyncMock(  # type: ignore[method-assign]
        return_value=[(profile, company)]
    )
    service._get_authorized_contexts = AsyncMock(  # type: ignore[method-assign]
        return_value=[context]
    )

    summary = await service.get_workspace_summary(uuid.uuid4())

    assert summary.context_selection_required is True
    assert summary.tasks == []
    assert summary.contexts == [context]
    assert [project.name for project in summary.contexts[0].projects] == [
        "Program A",
        "Program B",
    ]
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_single_project_defaults_to_its_active_cycle() -> None:
    service = ParticipantWorkspaceService(AsyncMock())
    profile = SimpleNamespace(id=uuid.uuid4())
    company = SimpleNamespace(id=uuid.uuid4())
    project_id = uuid.uuid4()
    closed_cycle_id = uuid.uuid4()
    active_cycle_id = uuid.uuid4()
    context = ParticipantWorkspaceContext(
        participant_profile_id=profile.id,
        participant_full_name="Participant",
        company_id=company.id,
        company_name="Company",
        projects=[
            ParticipantWorkspaceProject(
                id=project_id,
                name="Program",
                deadline_label="finalul evaluării",
                cycles=[
                    ParticipantWorkspaceCycle(
                        id=closed_cycle_id,
                        project_id=project_id,
                        sequence=1,
                        name="Evaluare inițială",
                        status="closed",
                    ),
                    ParticipantWorkspaceCycle(
                        id=active_cycle_id,
                        project_id=project_id,
                        sequence=2,
                        name="Reevaluare 1",
                        status="active",
                    ),
                ],
            )
        ],
    )

    selected = await service._resolve_workspace_context(
        [(profile, company)],
        [context],
        participant_profile_id=None,
        project_id=None,
        cycle_id=None,
        allowed_assignment_ids=None,
        scoped_project_id=None,
    )

    assert selected == (profile, company, project_id, active_cycle_id)


@pytest.mark.asyncio
async def test_workspace_rejects_cross_profile_cycle_selection() -> None:
    service = ParticipantWorkspaceService(AsyncMock())
    profile_a = SimpleNamespace(id=uuid.uuid4())
    profile_b = SimpleNamespace(id=uuid.uuid4())
    company = SimpleNamespace(id=uuid.uuid4())
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()
    cycle_b = uuid.uuid4()
    contexts = [
        ParticipantWorkspaceContext(
            participant_profile_id=profile_a.id,
            participant_full_name="Participant A",
            company_id=company.id,
            company_name="Company",
            projects=[
                ParticipantWorkspaceProject(
                    id=project_a,
                    name="Program A",
                    deadline_label="finalul evaluării",
                )
            ],
        ),
        ParticipantWorkspaceContext(
            participant_profile_id=profile_b.id,
            participant_full_name="Participant B",
            company_id=company.id,
            company_name="Company",
            projects=[
                ParticipantWorkspaceProject(
                    id=project_b,
                    name="Program B",
                    deadline_label="finalul evaluării",
                    cycles=[
                        ParticipantWorkspaceCycle(
                            id=cycle_b,
                            project_id=project_b,
                            sequence=2,
                            name="Reevaluare 1",
                            status="active",
                        )
                    ],
                )
            ],
        ),
    ]

    with pytest.raises(DomainError) as exc_info:
        await service._resolve_workspace_context(
            [(profile_a, company), (profile_b, company)],
            contexts,
            participant_profile_id=profile_a.id,
            project_id=project_a,
            cycle_id=cycle_b,
            allowed_assignment_ids=None,
            scoped_project_id=None,
        )

    assert exc_info.value.code == "participant_cycle_forbidden"


def test_assignment_tasks_use_neutral_labels_when_targets_are_missing() -> None:
    service = ParticipantWorkspaceService(AsyncMock())
    team_assignment = _assignment(
        target_type=AssignmentTargetType.team,
        target_team_id=uuid.uuid4(),
    )
    person_assignment = _assignment(
        target_type=AssignmentTargetType.person,
        target_person_id=uuid.uuid4(),
    )

    team_task = service._assignment_to_task(
        assignment=team_assignment,
        teams={},
        people={},
        projects={},
    )
    person_task = service._assignment_to_task(
        assignment=person_assignment,
        teams={},
        people={},
        projects={},
    )

    assert team_task.targetLabel == "Echipă"
    assert person_task.targetLabel == "Persoană evaluată"
    assert team_task.projectName is None


def test_participant_results_require_valid_policy_and_expose_only_allowed_scores() -> None:
    service = ParticipantWorkspaceService(AsyncMock())
    assignment = _assignment(
        target_type=AssignmentTargetType.person,
        status=AssignmentStatus.scored,
        target_person_id=uuid.uuid4(),
    )
    result = SimpleNamespace(
        scores={
            "clarity": {"score": 4.5, "interpretation": "  Clar și predictibil.  "},
            "private": {"score": 1.0},
            "invalid": {"score": "not-a-number"},
        },
        primary_result="clarity",
    )
    definition = SimpleNamespace(
        id=assignment.questionnaire_definition_id,
        content_checksum="definition-checksum",
        schema={"sections": []},
        private_config=None,
    )
    publication = SimpleNamespace(
        source_count=1,
        source_assignment_id=assignment.id,
        questionnaire_definition_id=assignment.questionnaire_definition_id,
        definition_checksum="definition-checksum",
        questionnaire_key=assignment.questionnaire_key,
        assignment_round_id=assignment.assignment_round_id,
        policy_snapshot={"publication": "none"},
    )

    assert (
        service._assignment_to_result(
            assignment=assignment,
            result=result,
            definition=definition,
            publication=None,
            teams={},
            people={},
            projects={},
        )
        is None
    )
    assert (
        service._assignment_to_result(
            assignment=assignment,
            result=result,
            definition=definition,
            publication=publication,
            teams={},
            people={},
            projects={},
        )
        is None
    )

    publication.policy_snapshot = {
        "publication": "scores_and_interpretation",
        "dimension_ids": ["clarity", "private", "invalid", None, ""],
        "target_types": ["person"],
        "include_primary_result": True,
    }
    visible = service._assignment_to_result(
        assignment=assignment,
        result=result,
        definition=definition,
        publication=publication,
        teams={},
        people={},
        projects={},
    )

    assert visible is not None
    assert visible.primary_result == "clarity"
    assert visible.scores == {
        "clarity": {
            "score": 4.5,
            "label": "Clarity",
            "interpretation": "Clar și predictibil.",
        },
        "private": {"score": 1.0, "label": "Private"},
    }


@pytest.mark.asyncio
async def test_participant_lookup_and_publication_definition_fail_closed() -> None:
    session = AsyncMock()
    service = ParticipantWorkspaceService(session)
    missing_profile_result = MagicMock()
    missing_profile_result.first.return_value = None
    session.execute = AsyncMock(return_value=missing_profile_result)

    with pytest.raises(DomainError, match="Participant profile not found") as profile_error:
        await service._get_profile_and_company(uuid.uuid4())
    assert profile_error.value.code == "participant_profile_not_found"

    publication = SimpleNamespace(
        questionnaire_definition_id=None,
        definition_checksum=None,
    )
    assert await service._definition_for_publication(publication) is None

    publication.questionnaire_definition_id = uuid.uuid4()
    publication.definition_checksum = "expected-checksum"
    missing_definition_result = MagicMock()
    missing_definition_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=missing_definition_result)
    assert await service._definition_for_publication(publication) is None
