import uuid
from typing import Any, cast

import pytest

from codrut.core.errors import DomainError
from codrut.modules.forms.models import QuestionnaireDefinition, QuestionnaireKey
from codrut.modules.forms.schemas import (
    QuestionnaireDefinitionCreateRequest,
    QuestionnaireDefinitionUpdateRequest,
)
from codrut.modules.forms.service import FormsService


class FakeDefinitionRepository:
    def __init__(self, definitions: list[QuestionnaireDefinition] | None = None) -> None:
        self.definitions = definitions or []
        self.submitted_versions: set[tuple[QuestionnaireKey, int]] = set()
        self.assigned_definition_ids: set[uuid.UUID] = set()
        self.lookup_keys: list[str] = []
        self.list_calls = 0

    async def list_definitions(
        self,
        *,
        active_only: bool = True,
    ) -> list[QuestionnaireDefinition]:
        self.list_calls += 1
        definitions = self.definitions
        if active_only:
            definitions = [definition for definition in definitions if definition.active]
        return sorted(definitions, key=lambda definition: (definition.key, -definition.version))

    async def get_definition(
        self,
        key: str,
        *,
        version: int | None = None,
    ) -> QuestionnaireDefinition | None:
        self.lookup_keys.append(key)
        definitions = [definition for definition in self.definitions if definition.key == key]
        if version is None:
            definitions = [definition for definition in definitions if definition.active]
            return max(definitions, key=lambda definition: definition.version, default=None)
        return next(
            (definition for definition in definitions if definition.version == version),
            None,
        )

    async def get_latest_version(self, key: str) -> int:
        versions = [definition.version for definition in self.definitions if definition.key == key]
        return max(versions, default=0)

    async def add_definition(
        self,
        definition: QuestionnaireDefinition,
    ) -> QuestionnaireDefinition:
        definition.id = uuid.uuid4()
        self.definitions.append(definition)
        return definition

    async def has_submitted_responses(self, key: str, version: int) -> bool:
        return (key, version) in self.submitted_versions

    async def has_assignments_for_definition(self, definition_id: uuid.UUID) -> bool:
        return definition_id in self.assigned_definition_ids

    async def deactivate_definitions_for_key(
        self,
        key: str,
        *,
        except_version: int | None = None,
    ) -> None:
        for definition in self.definitions:
            if definition.key == key and definition.version != except_version:
                definition.active = False


def make_service(repository: FakeDefinitionRepository) -> FormsService:
    service = FormsService()
    service.repository = cast(Any, repository)
    return service


def minimal_schema(label: str = "Item 1") -> dict[str, Any]:
    return {
        "schema_version": "questionnaire.v1",
        "audience": "leadership",
        "sections": [
            {
                "id": "main",
                "title": "Main",
                "questions": [
                    {
                        "id": "q1",
                        "code": "Q1",
                        "type": "likert",
                        "label": label,
                        "required": True,
                        "scale": [
                            {"value": 1, "label": "Rar"},
                            {"value": 2, "label": "Uneori"},
                            {"value": 3, "label": "Frecvent"},
                            {"value": 4, "label": "Intotdeauna"},
                        ],
                    }
                ],
            }
        ],
        "scoring": {"method": "sum_by_group", "groups": []},
    }


def persisted_definition(
    *,
    key: QuestionnaireKey = QuestionnaireKey.icare,
    version: int = 1,
    active: bool = True,
    label: str = "Item 1",
) -> QuestionnaireDefinition:
    return QuestionnaireDefinition(
        id=uuid.uuid4(),
        key=key,
        version=version,
        title="ICARE",
        description="Imported ICARE structure",
        schema=minimal_schema(label),
        active=active,
    )


@pytest.mark.asyncio
async def test_create_definition_persists_versioned_structure() -> None:
    repository = FakeDefinitionRepository()
    service = make_service(repository)

    result = await service.create_definition(
        QuestionnaireDefinitionCreateRequest(
            key=QuestionnaireKey.icare,
            title="ICARE",
            description="Imported ICARE structure",
            schema=minimal_schema(),
        )
    )

    assert result.key == QuestionnaireKey.icare
    assert result.version == 1
    assert result.active is True
    assert result.definition_schema["audience"] == "leadership"
    assert result.definition_schema["sections"][0]["questions"][0]["scale"][-1]["value"] == 4


@pytest.mark.asyncio
async def test_create_definition_accepts_custom_category_slug() -> None:
    repository = FakeDefinitionRepository()
    service = make_service(repository)

    result = await service.create_definition(
        QuestionnaireDefinitionCreateRequest(
            key="team_health_custom",
            title="Team health",
            description="Custom trainer-defined questionnaire",
            schema=minimal_schema(),
        )
    )

    assert result.key == "team_health_custom"
    assert repository.definitions[0].key == "team_health_custom"


@pytest.mark.asyncio
async def test_create_inactive_definition_accepts_empty_draft_section() -> None:
    repository = FakeDefinitionRepository()
    service = make_service(repository)

    result = await service.create_definition(
        QuestionnaireDefinitionCreateRequest(
            key="draft_custom",
            title="Draft custom",
            schema={
                "schema_version": "questionnaire.v1",
                "audience": "team",
                "sections": [{"id": "sectiunea_1", "title": "Secțiunea 1", "questions": []}],
            },
            active=False,
        )
    )

    assert result.active is False
    assert result.definition_schema["sections"][0]["questions"] == []


@pytest.mark.asyncio
async def test_update_definition_mutates_unused_version() -> None:
    definition = persisted_definition()
    repository = FakeDefinitionRepository([definition])
    service = make_service(repository)

    result = await service.update_definition(
        QuestionnaireKey.icare,
        QuestionnaireDefinitionUpdateRequest(
            title="ICARE updated",
            schema=minimal_schema("Updated item"),
        ),
    )

    assert result.version == 1
    assert result.title == "ICARE updated"
    assert (
        repository.definitions[0].schema["sections"][0]["questions"][0]["label"] == "Updated item"
    )


@pytest.mark.asyncio
async def test_update_definition_versions_submitted_definition() -> None:
    definition = persisted_definition(label="Original item")
    repository = FakeDefinitionRepository([definition])
    repository.submitted_versions.add((QuestionnaireKey.icare, 1))
    service = make_service(repository)

    result = await service.update_definition(
        QuestionnaireKey.icare,
        QuestionnaireDefinitionUpdateRequest(schema=minimal_schema("New item")),
    )

    assert result.version == 2
    assert result.active is True
    assert definition.active is False
    assert definition.schema["sections"][0]["questions"][0]["label"] == "Original item"
    assert repository.definitions[1].schema["sections"][0]["questions"][0]["label"] == "New item"


@pytest.mark.asyncio
async def test_activate_definition_deactivates_sibling_versions() -> None:
    version_1 = persisted_definition(version=1, active=False)
    version_2 = persisted_definition(version=2, active=True)
    repository = FakeDefinitionRepository([version_1, version_2])
    service = make_service(repository)

    result = await service.activate_definition(QuestionnaireKey.icare, 1)

    assert result.version == 1
    assert version_1.active is True
    assert version_2.active is False


@pytest.mark.asyncio
async def test_activate_definition_rejects_incomplete_draft() -> None:
    definition = QuestionnaireDefinition(
        id=uuid.uuid4(),
        key="draft_custom",
        version=1,
        title="Draft custom",
        description="",
        schema={
            "schema_version": "questionnaire.v1",
            "audience": "team",
            "sections": [{"id": "sectiunea_1", "title": "Secțiunea 1", "questions": []}],
        },
        active=False,
    )
    repository = FakeDefinitionRepository([definition])
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.activate_definition("draft_custom", 1)

    assert exc_info.value.code == "definition_invalid"
    assert definition.active is False


@pytest.mark.asyncio
async def test_retire_definition_marks_active_false_without_deleting() -> None:
    definition = persisted_definition()
    repository = FakeDefinitionRepository([definition])
    service = make_service(repository)

    result = await service.retire_definition(QuestionnaireKey.icare)

    assert result.active is False
    assert repository.definitions == [definition]


@pytest.mark.asyncio
async def test_active_definition_schema_requires_items() -> None:
    service = make_service(FakeDefinitionRepository())

    with pytest.raises(DomainError) as exc_info:
        await service.create_definition(
            QuestionnaireDefinitionCreateRequest(
                key=QuestionnaireKey.icare,
                title="Broken",
                schema={"schema_version": "questionnaire.v1", "sections": []},
            )
        )

    assert exc_info.value.code == "definition_invalid"


@pytest.mark.asyncio
async def test_update_definition_versions_system_managed_definition() -> None:
    definition = persisted_definition(label="Protected item")
    definition.system_managed = True
    repository = FakeDefinitionRepository([definition])
    service = make_service(repository)

    result = await service.update_definition(
        QuestionnaireKey.icare,
        QuestionnaireDefinitionUpdateRequest(schema=minimal_schema("Trainer clone")),
    )

    assert result.version == 2
    assert definition.active is False
    assert definition.system_managed is True
    assert repository.definitions[1].system_managed is False
    assert repository.definitions[1].schema["sections"][0]["questions"][0]["label"] == (
        "Trainer clone"
    )


@pytest.mark.asyncio
async def test_retire_definition_rejects_system_managed_definition() -> None:
    definition = persisted_definition()
    definition.system_managed = True
    service = make_service(FakeDefinitionRepository([definition]))

    with pytest.raises(DomainError) as exc_info:
        await service.retire_definition(QuestionnaireKey.icare)

    assert exc_info.value.code == "definition_system_managed"
    assert definition.active is True


@pytest.mark.asyncio
async def test_get_persisted_definition_does_not_seed_when_definition_exists() -> None:
    definition = persisted_definition(key="lencioni", version=1, active=True)
    repository = FakeDefinitionRepository([definition])
    service = make_service(repository)

    first = await service.get_persisted_definition("lencioni")
    second = await service.get_persisted_definition("lencioni")

    assert first.key == "lencioni"
    assert second.key == "lencioni"
    assert repository.lookup_keys == ["lencioni", "lencioni"]
    assert repository.list_calls == 0
