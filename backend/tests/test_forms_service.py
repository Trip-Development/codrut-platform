from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications import task_links
from codrut.modules.forms.models import QuestionnaireDefinition, QuestionnaireKey
from codrut.modules.forms.service import (
    FormsService,
    _allowed_answer_values,
    _required_answer_keys,
    _validate_assignment_response_window,
)


class CatalogRepository:
    def __init__(
        self,
        definitions: list[QuestionnaireDefinition] | None = None,
        *,
        assignment: QuestionnaireAssignment | None = None,
    ) -> None:
        self.definitions = definitions or []
        self.assignment = assignment
        self.submitted_versions: set[tuple[str, int]] = set()
        self.deactivated: list[tuple[str, int | None]] = []

    async def list_definitions(
        self,
        *,
        active_only: bool = True,
    ) -> list[QuestionnaireDefinition]:
        if active_only:
            return [definition for definition in self.definitions if definition.active]
        return list(self.definitions)

    async def get_definition(
        self,
        key: str,
        *,
        version: int | None = None,
    ) -> QuestionnaireDefinition | None:
        matches = [definition for definition in self.definitions if definition.key == key]
        if version is not None:
            return next(
                (definition for definition in matches if definition.version == version),
                None,
            )
        active = [definition for definition in matches if definition.active]
        return max(active, key=lambda definition: definition.version, default=None)

    async def get_definition_by_id(
        self,
        definition_id: UUID,
    ) -> QuestionnaireDefinition | None:
        return next(
            (definition for definition in self.definitions if definition.id == definition_id),
            None,
        )

    async def add_definition(
        self,
        definition: QuestionnaireDefinition,
    ) -> QuestionnaireDefinition:
        definition.id = uuid4()
        self.definitions.append(definition)
        return definition

    async def has_submitted_responses(self, key: str, version: int) -> bool:
        return (key, version) in self.submitted_versions

    async def has_assignments_for_definition(self, definition_id: UUID) -> bool:
        return False

    async def get_latest_version(self, key: str) -> int:
        return max(
            (definition.version for definition in self.definitions if definition.key == key),
            default=0,
        )

    async def deactivate_definitions_for_key(
        self,
        key: str,
        *,
        except_version: int | None = None,
    ) -> None:
        self.deactivated.append((key, except_version))
        for definition in self.definitions:
            if definition.key == key and definition.version != except_version:
                definition.active = False

    async def get_assignment_for_user_by_key(
        self,
        _user_id: UUID,
        questionnaire_key: str,
        *,
        version: int | None = None,
        allowed_assignment_ids: tuple[UUID, ...] | None = None,
    ) -> QuestionnaireAssignment | None:
        assignment = self.assignment
        if assignment is None or assignment.questionnaire_key != questionnaire_key:
            return None
        if allowed_assignment_ids is not None and assignment.id not in allowed_assignment_ids:
            return None
        definition = await self.get_definition_by_id(assignment.questionnaire_definition_id)
        if version is not None and (definition is None or definition.version != version):
            return None
        return assignment

    async def get_project_for_assignment(
        self,
        _assignment: QuestionnaireAssignment,
    ) -> None:
        return None


class ScalarResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class InviteSession:
    def __init__(self, invite: object | None) -> None:
        self.invite = invite
        self.execute_calls = 0

    async def execute(self, _statement: object) -> ScalarResult:
        self.execute_calls += 1
        return ScalarResult(self.invite)


class SecureLinkRepository:
    def __init__(
        self,
        *,
        invite: object | None,
        assignment: QuestionnaireAssignment | None,
    ) -> None:
        self.session = InviteSession(invite)
        self.assignment = assignment

    async def get_assignment_by_id(
        self,
        assignment_id: UUID,
    ) -> QuestionnaireAssignment | None:
        if self.assignment is not None and self.assignment.id == assignment_id:
            return self.assignment
        return None


def _service_with_repository(repository: object) -> FormsService:
    service = FormsService()
    service.repository = cast(Any, repository)
    return service


def _assignment(
    *,
    assignment_id: UUID,
    company_id: UUID,
    profile_id: UUID,
    project_id: UUID | None = None,
) -> QuestionnaireAssignment:
    return QuestionnaireAssignment(
        id=assignment_id,
        company_id=company_id,
        project_id=project_id,
        respondent_profile_id=profile_id,
        questionnaire_key=QuestionnaireKey.lencioni,
        target_type=AssignmentTargetType.team,
        target_team_id=uuid4(),
        status=AssignmentStatus.assigned,
    )


def _patch_task_claims(
    monkeypatch: pytest.MonkeyPatch,
    *,
    assignment_ids: list[UUID],
    company_id: UUID,
    profile_id: UUID,
    project_id: UUID | None = None,
) -> None:
    claims = SimpleNamespace(
        assignment_ids=assignment_ids,
        company_id=company_id,
        respondent_profile_id=profile_id,
        project_id=project_id,
    )
    monkeypatch.setattr(task_links, "parse_task_token", lambda _token, _settings: claims)


def _active_invite(
    *,
    company_id: UUID,
    profile_id: UUID,
    project_id: UUID | None = None,
    expired: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        status="active",
        expires_at=datetime.now(UTC) + (timedelta(seconds=-1) if expired else timedelta(minutes=5)),
        company_id=company_id,
        respondent_profile_id=profile_id,
        project_id=project_id,
    )


def test_forms_service_requires_repository_for_persisted_operations() -> None:
    with pytest.raises(RuntimeError, match="requires a database session"):
        FormsService()._require_repository()


def test_answer_schema_helpers_distinguish_optional_questions_and_statement_sets() -> None:
    schema = {
        "sections": [
            {
                "questions": [
                    {
                        "id": "optional",
                        "type": "likert",
                        "required": False,
                        "scale": [{"value": 1}, {"value": 2}],
                    },
                    {
                        "id": "signals",
                        "type": "statement_score_set",
                        "scale": [{"value": "low"}, {"value": "high"}],
                        "statements": [{"id": "clarity"}, {"id": "support"}],
                    },
                ]
            }
        ]
    }

    assert _allowed_answer_values(schema) == {
        "optional": {1, 2},
        "signals:clarity": {"low", "high"},
        "signals:support": {"low", "high"},
    }
    assert _required_answer_keys(schema) == {"signals:clarity", "signals:support"}


async def test_assignment_response_window_rejects_due_and_project_boundaries() -> None:
    now = datetime.now(UTC)

    with pytest.raises(DomainError) as assignment_closed:
        await _validate_assignment_response_window(
            cast(Any, SimpleNamespace(get_project_for_assignment=None)),
            SimpleNamespace(due_at=now - timedelta(seconds=1)),
        )
    assert assignment_closed.value.code == "assignment_closed"

    class WindowRepository:
        def __init__(self, project: object | None) -> None:
            self.project = project

        async def get_project_for_assignment(self, _assignment: object) -> object | None:
            return self.project

    open_assignment = SimpleNamespace(due_at=None)
    await _validate_assignment_response_window(
        cast(Any, WindowRepository(None)),
        open_assignment,
    )

    with pytest.raises(DomainError) as not_open:
        await _validate_assignment_response_window(
            cast(
                Any,
                WindowRepository(
                    SimpleNamespace(
                        form_opens_at=now + timedelta(minutes=1),
                        form_closes_at=None,
                        due_at=None,
                    )
                ),
            ),
            open_assignment,
        )
    assert not_open.value.code == "project_not_open"

    with pytest.raises(DomainError) as project_closed:
        await _validate_assignment_response_window(
            cast(
                Any,
                WindowRepository(
                    SimpleNamespace(
                        form_opens_at=now - timedelta(minutes=2),
                        form_closes_at=None,
                        due_at=now - timedelta(minutes=1),
                    )
                ),
            ),
            open_assignment,
        )
    assert project_closed.value.code == "project_closed"

    await _validate_assignment_response_window(
        cast(
            Any,
            WindowRepository(
                SimpleNamespace(
                    form_opens_at=now - timedelta(minutes=1),
                    form_closes_at=now + timedelta(minutes=1),
                    due_at=None,
                )
            ),
        ),
        open_assignment,
    )


async def test_list_persisted_definitions_does_not_seed_content_from_code() -> None:
    repository = CatalogRepository()

    definitions = await _service_with_repository(repository).list_persisted_definitions()

    assert definitions == []
    assert repository.definitions == []


async def test_get_persisted_definition_rejects_unknown_key_without_seeding() -> None:
    repository = CatalogRepository()

    with pytest.raises(DomainError) as exc_info:
        await _service_with_repository(repository).get_persisted_definition("unknown_form")

    assert exc_info.value.code == "definition_not_found"
    assert repository.definitions == []


async def test_participant_definition_omits_private_scoring_metadata() -> None:
    definition = QuestionnaireDefinition(
        id=uuid4(),
        key="protected_sample",
        version=2,
        title="Protected sample",
        description="",
        schema={
            "schema_version": "questionnaire.v1",
            "source": {"provider": "private"},
            "sections": [
                {
                    "id": "main",
                    "title": "Main",
                    "questions": [
                        {
                            "id": "q1",
                            "type": "likert",
                            "label": "Public prompt",
                            "scale": [{"value": 1, "label": "1"}],
                            "scoring": {"weight": 4},
                        }
                    ],
                }
            ],
            "scoring": {"method": "private"},
        },
        private_config={
            "schema": {
                "schema_version": "questionnaire.v1",
                "sections": [],
                "scoring": {"method": "private"},
            }
        },
        active=True,
        system_managed=True,
    )
    service = _service_with_repository(CatalogRepository([definition]))

    participant = await service.get_persisted_definition("protected_sample")
    trainer = await service.get_persisted_definition(
        "protected_sample",
        include_private=True,
    )

    assert participant.definition_schema["sections"][0]["questions"][0]["label"] == (
        "Public prompt"
    )
    assert "source" not in participant.definition_schema
    assert "scoring" not in participant.definition_schema
    assert "scoring" not in participant.definition_schema["sections"][0]["questions"][0]
    assert trainer.definition_schema["scoring"] == {"method": "private"}


async def test_participant_can_read_only_an_assigned_definition_by_key() -> None:
    definition = QuestionnaireDefinition(
        id=uuid4(),
        key="protected_sample",
        version=2,
        title="Protected sample",
        description="",
        schema={
            "schema_version": "questionnaire.v1",
            "sections": [
                {
                    "id": "main",
                    "title": "Main",
                    "questions": [
                        {
                            "id": "q1",
                            "type": "likert",
                            "label": "Public prompt",
                            "scale": [{"value": 1, "label": "1"}],
                        }
                    ],
                }
            ],
            "scoring": {"method": "private"},
        },
        private_config={"scoring": {"weights": [1]}},
        active=True,
        system_managed=True,
    )
    assignment = QuestionnaireAssignment(
        id=uuid4(),
        company_id=uuid4(),
        respondent_profile_id=uuid4(),
        questionnaire_key="protected_sample",
        questionnaire_definition_id=definition.id,
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.assigned,
    )
    repository = CatalogRepository([definition], assignment=assignment)
    service = _service_with_repository(repository)

    participant = await service.get_participant_definition_by_key(
        uuid4(),
        "protected_sample",
        allowed_assignment_ids=(assignment.id,),
    )

    assert participant.key == "protected_sample"
    assert participant.version == 2
    assert participant.definition_schema["sections"][0]["questions"][0]["label"] == (
        "Public prompt"
    )
    assert "scoring" not in participant.definition_schema


async def test_participant_definition_by_key_rejects_unassigned_catalog_entry() -> None:
    definition = QuestionnaireDefinition(
        id=uuid4(),
        key="protected_sample",
        version=2,
        title="Protected sample",
        description="",
        schema={"schema_version": "questionnaire.v1", "sections": []},
        active=True,
    )
    service = _service_with_repository(CatalogRepository([definition]))

    with pytest.raises(DomainError) as exc_info:
        await service.get_participant_definition_by_key(uuid4(), "protected_sample")

    assert exc_info.value.code == "definition_not_found"


async def test_secure_link_rejects_assignment_outside_token_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assignment_id = uuid4()
    company_id = uuid4()
    profile_id = uuid4()
    repository = SecureLinkRepository(invite=None, assignment=None)
    _patch_task_claims(
        monkeypatch,
        assignment_ids=[],
        company_id=company_id,
        profile_id=profile_id,
    )

    with pytest.raises(DomainError) as exc_info:
        await _service_with_repository(repository)._assignment_for_secure_link(
            "task-token", assignment_id
        )

    assert exc_info.value.code == "task_link_scope_mismatch"
    assert repository.session.execute_calls == 0


async def test_secure_link_rejects_revoked_invite(monkeypatch: pytest.MonkeyPatch) -> None:
    assignment_id = uuid4()
    company_id = uuid4()
    profile_id = uuid4()
    repository = SecureLinkRepository(invite=None, assignment=None)
    _patch_task_claims(
        monkeypatch,
        assignment_ids=[assignment_id],
        company_id=company_id,
        profile_id=profile_id,
    )

    with pytest.raises(DomainError) as exc_info:
        await _service_with_repository(repository)._assignment_for_secure_link(
            "task-token", assignment_id
        )

    assert exc_info.value.code == "task_link_revoked"
    assert repository.session.execute_calls == 1


async def test_secure_link_rejects_expired_invite(monkeypatch: pytest.MonkeyPatch) -> None:
    assignment_id = uuid4()
    company_id = uuid4()
    profile_id = uuid4()
    invite = _active_invite(
        company_id=company_id,
        profile_id=profile_id,
        expired=True,
    )
    repository = SecureLinkRepository(invite=invite, assignment=None)
    _patch_task_claims(
        monkeypatch,
        assignment_ids=[assignment_id],
        company_id=company_id,
        profile_id=profile_id,
    )

    with pytest.raises(DomainError) as exc_info:
        await _service_with_repository(repository)._assignment_for_secure_link(
            "task-token", assignment_id
        )

    assert exc_info.value.code == "task_link_expired"


async def test_secure_link_rejects_assignment_owned_by_another_company(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assignment_id = uuid4()
    company_id = uuid4()
    profile_id = uuid4()
    invite = _active_invite(
        company_id=company_id,
        profile_id=profile_id,
    )
    assignment = _assignment(
        assignment_id=assignment_id,
        company_id=uuid4(),
        profile_id=profile_id,
    )
    repository = SecureLinkRepository(invite=invite, assignment=assignment)
    _patch_task_claims(
        monkeypatch,
        assignment_ids=[assignment_id],
        company_id=company_id,
        profile_id=profile_id,
    )

    with pytest.raises(DomainError) as exc_info:
        await _service_with_repository(repository)._assignment_for_secure_link(
            "task-token", assignment_id
        )

    assert exc_info.value.code == "task_link_scope_mismatch"


async def test_secure_link_returns_assignment_when_all_ownership_checks_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assignment_id = uuid4()
    company_id = uuid4()
    profile_id = uuid4()
    invite = _active_invite(
        company_id=company_id,
        profile_id=profile_id,
    )
    assignment = _assignment(
        assignment_id=assignment_id,
        company_id=company_id,
        profile_id=profile_id,
    )
    repository = SecureLinkRepository(invite=invite, assignment=assignment)
    _patch_task_claims(
        monkeypatch,
        assignment_ids=[assignment_id],
        company_id=company_id,
        profile_id=profile_id,
    )

    result = await _service_with_repository(repository)._assignment_for_secure_link(
        "task-token", assignment_id
    )

    assert result is assignment


async def test_secure_link_rejects_invite_from_another_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assignment_id = uuid4()
    company_id = uuid4()
    profile_id = uuid4()
    project_id = uuid4()
    assignment = _assignment(
        assignment_id=assignment_id,
        company_id=company_id,
        profile_id=profile_id,
        project_id=project_id,
    )
    repository = SecureLinkRepository(
        invite=_active_invite(
            company_id=company_id,
            profile_id=profile_id,
            project_id=uuid4(),
        ),
        assignment=assignment,
    )
    _patch_task_claims(
        monkeypatch,
        assignment_ids=[assignment_id],
        company_id=company_id,
        profile_id=profile_id,
        project_id=project_id,
    )

    with pytest.raises(DomainError) as exc_info:
        await _service_with_repository(repository)._assignment_for_secure_link(
            "task-token", assignment_id
        )

    assert exc_info.value.code == "task_link_scope_mismatch"


async def test_secure_link_rejects_assignment_from_another_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assignment_id = uuid4()
    company_id = uuid4()
    profile_id = uuid4()
    project_id = uuid4()
    assignment = _assignment(
        assignment_id=assignment_id,
        company_id=company_id,
        profile_id=profile_id,
        project_id=uuid4(),
    )
    repository = SecureLinkRepository(
        invite=_active_invite(
            company_id=company_id,
            profile_id=profile_id,
            project_id=project_id,
        ),
        assignment=assignment,
    )
    _patch_task_claims(
        monkeypatch,
        assignment_ids=[assignment_id],
        company_id=company_id,
        profile_id=profile_id,
        project_id=project_id,
    )

    with pytest.raises(DomainError) as exc_info:
        await _service_with_repository(repository)._assignment_for_secure_link(
            "task-token", assignment_id
        )

    assert exc_info.value.code == "task_link_scope_mismatch"
