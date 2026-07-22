import json
import uuid

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.modules.communications.models import EmailTemplate
from codrut.modules.forms.models import ProtectedContentImport, QuestionnaireDefinition
from codrut.modules.protected_content.package import (
    canonical_checksum,
    load_protected_content_package,
    reversion_protected_content_package,
)
from codrut.modules.protected_content.service import ProtectedContentService


def package_payload(*, package_id: str | None = None, title: str = "Synthetic package") -> dict:
    suffix = uuid.uuid4().hex
    payload = {
        "package_version": "protected-content.v1",
        "package_id": package_id or f"test-package-{suffix}",
        "questionnaires": [
            {
                "key": f"protected_sample_{suffix}",
                "version": 1,
                "title": title,
                "description": "Synthetic contract fixture.",
                "participant_schema": {
                    "schema_version": "questionnaire.v1",
                    "sections": [
                        {
                            "id": "public",
                            "title": "Public",
                            "questions": [
                                {
                                    "id": "q1",
                                    "code": "Q1",
                                    "type": "likert",
                                    "label": "Synthetic prompt",
                                    "required": True,
                                    "scale": [
                                        {"value": 1, "label": "1"},
                                        {"value": 2, "label": "2"},
                                    ],
                                }
                            ],
                        }
                    ],
                },
                "private_config": {
                    "schema": {
                        "schema_version": "questionnaire.v1",
                        "sections": [],
                        "scoring": {"method": "private_fixture"},
                    }
                },
                "feedback_policy": {"publication": "none"},
                "trainer_visibility_policy": {"raw_responses": "hidden"},
                "activate": True,
            }
        ],
        "email_templates": [
            {
                "key": f"protected_email_{suffix}",
                "version": 1,
                "subject": "Salut, ${first_name}",
                "html_body": "<p>Salut, ${first_name}.</p>",
                "text_body": "Salut, ${first_name}.",
                "variables": ["first_name"],
                "audience": "test:synthetic",
                "activate": True,
            }
        ],
    }
    payload["checksum"] = canonical_checksum(payload)
    return payload


def load_package(payload: dict):
    return load_protected_content_package(json.dumps(payload, ensure_ascii=False))


def resign(payload: dict) -> None:
    payload["checksum"] = canonical_checksum(
        {key: value for key, value in payload.items() if key != "checksum"}
    )


def test_package_rejects_invalid_or_empty_payloads() -> None:
    with pytest.raises(DomainError) as malformed:
        load_protected_content_package("{")
    assert malformed.value.code == "protected_content_invalid"

    payload = package_payload()
    payload["questionnaires"] = []
    payload["email_templates"] = []
    resign(payload)
    with pytest.raises(DomainError) as empty:
        load_package(payload)
    assert empty.value.code == "protected_content_empty"


def test_package_rejects_checksum_mismatch() -> None:
    payload = package_payload()
    payload["questionnaires"][0]["title"] = "Tampered"

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_checksum_mismatch"


def test_package_rejects_duplicate_questionnaire_version() -> None:
    payload = package_payload()
    payload["questionnaires"].append(dict(payload["questionnaires"][0]))
    payload["checksum"] = canonical_checksum({k: v for k, v in payload.items() if k != "checksum"})

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_duplicate_questionnaire"


def test_package_rejects_duplicate_template_version() -> None:
    payload = package_payload()
    payload["email_templates"].append(dict(payload["email_templates"][0]))
    resign(payload)

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_duplicate_template"


def test_package_rejects_private_scoring_in_participant_schema() -> None:
    payload = package_payload()
    payload["questionnaires"][0]["participant_schema"]["scoring"] = {"method": "leak"}
    payload["checksum"] = canonical_checksum({k: v for k, v in payload.items() if k != "checksum"})

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_participant_schema_private"


@pytest.mark.parametrize(
    ("container_path", "private_key"),
    [
        (("participant_schema",), "weights"),
        (("participant_schema", "sections", 0), "internal_notes"),
        (("participant_schema", "sections", 0, "questions", 0), "formula"),
        (
            ("participant_schema", "sections", 0, "questions", 0, "scale", 0),
            "score_ranges",
        ),
    ],
)
def test_package_rejects_alternate_private_metadata_at_every_public_level(
    container_path: tuple[str | int, ...],
    private_key: str,
) -> None:
    payload = package_payload()
    container = payload["questionnaires"][0]
    for segment in container_path:
        container = container[segment]
    container[private_key] = {"private": True}
    payload["checksum"] = canonical_checksum(
        {key: value for key, value in payload.items() if key != "checksum"}
    )

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_participant_schema_private"


def test_package_rejects_malformed_participant_schema() -> None:
    payload = package_payload()
    del payload["questionnaires"][0]["participant_schema"]["sections"][0]["questions"][0][
        "code"
    ]
    payload["checksum"] = canonical_checksum(
        {key: value for key, value in payload.items() if key != "checksum"}
    )

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_participant_schema_invalid"


def test_package_requires_public_statements_for_statement_score_questions() -> None:
    payload = package_payload()
    question = payload["questionnaires"][0]["participant_schema"]["sections"][0][
        "questions"
    ][0]
    question["type"] = "statement_score_set"
    resign(payload)

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_participant_schema_invalid"


def test_package_rejects_unsafe_aggregate_feedback_policy() -> None:
    payload = package_payload()
    payload["questionnaires"][0]["feedback_policy"] = {
        "publication": "aggregate",
        "minimum_completed": 1,
        "target_completed": 1,
        "dimension_ids": [],
    }
    payload["checksum"] = canonical_checksum({k: v for k, v in payload.items() if k != "checksum"})

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_feedback_policy_invalid"


@pytest.mark.parametrize(
    "policy",
    [
        {"publication": "private"},
        {"publication": "none", "minimum_completed": True},
        {"publication": "none", "minimum_completed": 3, "target_completed": 2},
        {
            "publication": "aggregate",
            "minimum_completed": 2,
            "target_completed": 3,
            "dimension_ids": [],
        },
        {"publication": "none", "participant_results": []},
        {
            "publication": "none",
            "participant_results": {"publication": "private"},
        },
        {
            "publication": "none",
            "participant_results": {"publication": "scores", "dimension_ids": []},
        },
        {
            "publication": "none",
            "participant_results": {
                "publication": "none",
                "dimension_ids": [],
                "target_types": "self",
            },
        },
        {
            "publication": "none",
            "participant_results": {
                "publication": "none",
                "dimension_ids": [],
                "target_types": ["organization"],
            },
        },
        {
            "publication": "none",
            "participant_results": {
                "publication": "none",
                "dimension_ids": [],
                "include_primary_result": "yes",
            },
        },
        {
            "publication": "none",
            "participant_results": {
                "publication": "none",
                "dimension_ids": [],
                "require_self_target": 1,
            },
        },
        {
            "publication": "none",
            "participant_results": {"publication": "none", "dimension_ids": "signal"},
        },
        {
            "publication": "none",
            "participant_results": {"publication": "none", "dimension_ids": [""]},
        },
        {
            "publication": "none",
            "participant_results": {
                "publication": "none",
                "dimension_ids": ["signal", "signal"],
            },
        },
    ],
)
def test_package_rejects_unsafe_feedback_policy_shapes(policy: dict) -> None:
    payload = package_payload()
    payload["questionnaires"][0]["feedback_policy"] = policy
    resign(payload)

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_feedback_policy_invalid"


def test_package_accepts_explicit_safe_feedback_and_visibility_policy() -> None:
    payload = package_payload()
    questionnaire = payload["questionnaires"][0]
    questionnaire["feedback_policy"] = {
        "publication": "aggregate",
        "minimum_completed": 2,
        "target_completed": 3,
        "dimension_ids": ["signal"],
        "participant_results": {
            "publication": "scores_and_interpretation",
            "dimension_ids": ["signal"],
            "target_types": ["self", "person", "team"],
            "include_primary_result": False,
            "require_self_target": True,
        },
    }
    questionnaire["trainer_visibility_policy"] = {"raw_responses": "visible"}
    resign(payload)

    package = load_package(payload)

    assert package.questionnaires[0].feedback_policy["minimum_completed"] == 2


def test_package_rejects_invalid_trainer_visibility_policy() -> None:
    payload = package_payload()
    payload["questionnaires"][0]["trainer_visibility_policy"] = {
        "raw_responses": "everyone"
    }
    resign(payload)

    with pytest.raises(DomainError) as exc_info:
        load_package(payload)

    assert exc_info.value.code == "protected_content_trainer_visibility_invalid"


def test_reversion_removes_private_response_metadata_from_participant_schema() -> None:
    payload = package_payload()
    source_package_id = payload["package_id"]
    payload["questionnaires"][0]["participant_schema"]["response"] = {
        "scoring": "private"
    }
    payload["questionnaires"][0]["private_config"]["schema"]["response"] = {
        "scoring": "private"
    }
    payload["checksum"] = canonical_checksum(
        {key: value for key, value in payload.items() if key != "checksum"}
    )

    package = reversion_protected_content_package(
        json.dumps(payload, ensure_ascii=False),
        package_id=f"{source_package_id}-v2",
    )

    questionnaire = package.questionnaires[0]
    template = package.email_templates[0]
    assert questionnaire.version == 2
    assert "response" not in questionnaire.participant_schema
    assert questionnaire.private_config["schema"]["response"] == {"scoring": "private"}
    assert template.version == 2
    assert load_protected_content_package(
        json.dumps(package.model_dump(mode="json"), ensure_ascii=False)
    ).checksum == package.checksum


def test_reversion_requires_a_new_package_id() -> None:
    payload = package_payload()

    with pytest.raises(DomainError) as exc_info:
        reversion_protected_content_package(
            json.dumps(payload, ensure_ascii=False),
            package_id=payload["package_id"],
        )

    assert exc_info.value.code == "protected_content_package_id_unchanged"


def test_reversion_rejects_invalid_source_and_checksum() -> None:
    with pytest.raises(DomainError) as invalid:
        reversion_protected_content_package("not-json", package_id="new-package")
    assert invalid.value.code == "protected_content_invalid"

    payload = package_payload()
    payload["questionnaires"][0]["title"] = "Changed without resigning"
    with pytest.raises(DomainError) as mismatch:
        reversion_protected_content_package(
            json.dumps(payload, ensure_ascii=False),
            package_id="new-package",
        )
    assert mismatch.value.code == "protected_content_checksum_mismatch"


async def test_import_and_activation_are_transactional_and_idempotent() -> None:
    await engine.dispose()
    payload = package_payload()
    package = load_package(payload)
    questionnaire = package.questionnaires[0]
    template = package.email_templates[0]
    try:
        async with SessionLocal() as session:
            service = ProtectedContentService(session)

            imported = await service.import_package(package)
            repeated = await service.import_package(package)
            activated = await service.activate_package(package)

            definition = await session.scalar(
                select(QuestionnaireDefinition).where(
                    QuestionnaireDefinition.key == questionnaire.key,
                    QuestionnaireDefinition.version == questionnaire.version,
                )
            )
            email_template = await session.scalar(
                select(EmailTemplate).where(
                    EmailTemplate.key == template.key,
                    EmailTemplate.version == template.version,
                    EmailTemplate.owner_id.is_(None),
                )
            )
            audit = await session.scalar(
                select(ProtectedContentImport).where(
                    ProtectedContentImport.package_id == package.package_id
                )
            )

            assert imported.status == "imported"
            assert repeated.status == "already_imported"
            assert activated.status == "activated"
            assert definition is not None
            assert definition.active is True
            assert definition.system_managed is True
            assert definition.schema == questionnaire.participant_schema
            assert definition.private_config == questionnaire.private_config
            assert definition.package_id == package.package_id
            assert email_template is not None
            assert email_template.active is True
            assert email_template.system_managed is True
            assert email_template.package_id == package.package_id
            assert audit is not None
            assert audit.checksum == package.checksum
            await session.rollback()
    finally:
        await engine.dispose()


async def test_activation_requires_the_exact_imported_package() -> None:
    await engine.dispose()
    package = load_package(package_payload())
    try:
        async with SessionLocal() as session:
            with pytest.raises(DomainError) as exc_info:
                await ProtectedContentService(session).activate_package(package)

            assert exc_info.value.code == "protected_content_not_imported"
            await session.rollback()
    finally:
        await engine.dispose()


async def test_activation_skips_questionnaires_and_templates_opted_out_by_package() -> None:
    await engine.dispose()
    payload = package_payload()
    payload["questionnaires"][0]["activate"] = False
    payload["email_templates"][0]["activate"] = False
    resign(payload)
    package = load_package(payload)
    questionnaire = package.questionnaires[0]
    template = package.email_templates[0]
    try:
        async with SessionLocal() as session:
            service = ProtectedContentService(session)
            await service.import_package(package)

            result = await service.activate_package(package)
            definition = await session.scalar(
                select(QuestionnaireDefinition).where(
                    QuestionnaireDefinition.key == questionnaire.key,
                    QuestionnaireDefinition.version == questionnaire.version,
                )
            )
            email_template = await session.scalar(
                select(EmailTemplate).where(
                    EmailTemplate.key == template.key,
                    EmailTemplate.version == template.version,
                    EmailTemplate.owner_id.is_(None),
                )
            )

            assert result.status == "activated"
            assert definition is not None and definition.active is False
            assert email_template is not None and email_template.active is False
            await session.rollback()
    finally:
        await engine.dispose()


async def test_import_rejects_reused_package_id_with_different_content() -> None:
    await engine.dispose()
    package_id = f"conflict-package-{uuid.uuid4().hex}"
    first = load_package(package_payload(package_id=package_id))
    second = load_package(package_payload(package_id=package_id, title="Changed fixture"))
    try:
        async with SessionLocal() as session:
            service = ProtectedContentService(session)
            await service.import_package(first)

            with pytest.raises(DomainError) as exc_info:
                await service.import_package(second)

            assert exc_info.value.code == "protected_content_package_conflict"
            await session.rollback()
    finally:
        await engine.dispose()


async def test_import_rejects_private_policy_change_for_existing_definition_version() -> None:
    await engine.dispose()
    first_payload = package_payload()
    first = load_package(first_payload)
    second_payload = json.loads(json.dumps(first_payload))
    second_payload["package_id"] = f"replacement-package-{uuid.uuid4().hex}"
    second_payload["questionnaires"][0]["private_config"] = {
        "schema": {"schema_version": "questionnaire.v1", "sections": []},
        "formula": "changed",
    }
    second_payload["checksum"] = canonical_checksum(
        {key: value for key, value in second_payload.items() if key != "checksum"}
    )
    second = load_package(second_payload)
    try:
        async with SessionLocal() as session:
            service = ProtectedContentService(session)
            await service.import_package(first)

            with pytest.raises(DomainError) as exc_info:
                await service.import_package(second)

            assert exc_info.value.code == "protected_content_questionnaire_conflict"
            definition = await session.scalar(
                select(QuestionnaireDefinition).where(
                    QuestionnaireDefinition.key == first.questionnaires[0].key,
                    QuestionnaireDefinition.version == first.questionnaires[0].version,
                )
            )
            assert definition is not None
            assert definition.private_config == first.questionnaires[0].private_config
            await session.rollback()
    finally:
        await engine.dispose()


async def test_import_rejects_stale_checksum_on_mutated_system_definition() -> None:
    await engine.dispose()
    first_payload = package_payload()
    first = load_package(first_payload)
    repeated_payload = json.loads(json.dumps(first_payload))
    repeated_payload["package_id"] = f"repeated-package-{uuid.uuid4().hex}"
    repeated_payload["checksum"] = canonical_checksum(
        {key: value for key, value in repeated_payload.items() if key != "checksum"}
    )
    repeated = load_package(repeated_payload)
    try:
        async with SessionLocal() as session:
            service = ProtectedContentService(session)
            await service.import_package(first)
            definition = await session.scalar(
                select(QuestionnaireDefinition).where(
                    QuestionnaireDefinition.key == first.questionnaires[0].key,
                    QuestionnaireDefinition.version == first.questionnaires[0].version,
                )
            )
            assert definition is not None
            original_checksum = definition.content_checksum
            definition.trainer_visibility_policy = {"raw_responses": "visible"}
            await session.flush()

            with pytest.raises(DomainError) as exc_info:
                await service.import_package(repeated)

            assert exc_info.value.code == "protected_content_questionnaire_conflict"
            assert definition.content_checksum == original_checksum
            await session.rollback()
    finally:
        await engine.dispose()
