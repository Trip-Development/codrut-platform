import uuid

import pytest
from pydantic import EmailStr, TypeAdapter

from codrut.core.config import Settings
from codrut.core.database import SessionLocal, engine
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.tools.local_preview import (
    PREVIEW_DEFINITION_VERSION,
    PREVIEW_PARTICIPANT_EMAIL_DOMAIN,
    assert_local_preview_allowed,
    build_preview_email_templates,
    build_preview_questionnaire_definitions,
    build_sample_answers,
)
from codrut.tools.seed_local_preview import _preview_uuid, _replace_preview_definitions


def test_preview_participant_domain_satisfies_api_email_validation() -> None:
    email = TypeAdapter(EmailStr).validate_python(f"participant@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}")

    assert str(email) == f"participant@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}"


def test_local_preview_is_blocked_in_production() -> None:
    settings = Settings.model_construct(env="production", local_auth_bypass=False)
    with pytest.raises(RuntimeError, match="cannot be seeded in production"):
        assert_local_preview_allowed(settings)


def test_local_preview_is_allowed_in_test() -> None:
    assert_local_preview_allowed(Settings(env="test"))


def test_preview_record_ids_are_stable_and_semantically_distinct() -> None:
    project_id = _preview_uuid("project", "Atelier Meridian", "Leadership operațional Q3")

    assert project_id == _preview_uuid(
        "project",
        "Atelier Meridian",
        "Leadership operațional Q3",
    )
    assert project_id != _preview_uuid(
        "project",
        "Atelier Meridian",
        "Coaching managerial aplicat",
    )


def test_local_preview_is_blocked_outside_development_and_test() -> None:
    with pytest.raises(RuntimeError, match="only be seeded in development or test"):
        assert_local_preview_allowed(Settings(env="staging"))


def test_preview_definitions_use_short_synthetic_samples() -> None:
    definitions = {
        definition.key: definition for definition in build_preview_questionnaire_definitions()
    }

    assert PREVIEW_DEFINITION_VERSION > 1
    assert set(definitions) == {"pcm_base", "lencioni", "distress_drivers", "boss_360"}
    assert len(definitions["pcm_base"].schema["sections"][0]["questions"]) == 2
    assert len(definitions["lencioni"].schema["sections"][0]["questions"]) == 15
    work_style_questions = definitions["distress_drivers"].schema["sections"][0]["questions"]
    assert len(work_style_questions) == 1
    assert len(work_style_questions[0]["statements"]) == 10
    assert definitions["distress_drivers"].schema["scoring"]["normalize_to"] == 100
    assert all(
        driver["feedback_above_50"]
        for driver in definitions["distress_drivers"].schema["scoring"]["drivers"]
    )
    assert definitions["boss_360"].schema["scoring"]["score_min"] == 0
    assert definitions["distress_drivers"].feedback_policy["participant_results"] == {
        "publication": "scores",
        "target_types": ["self"],
        "dimension_ids": [
            "autonomie",
            "rigoare",
            "efort",
            "ritm",
            "cooperare",
        ],
        "include_primary_result": True,
    }
    assert definitions["lencioni"].feedback_policy["participant_results"]["target_types"] == [
        "team"
    ]
    assert len(definitions["boss_360"].schema["sections"]) == 4
    assert all(
        len(section["questions"]) == 1 and len(section["questions"][0]["statements"]) == 2
        for section in definitions["boss_360"].schema["sections"]
    )
    feedback_statements = [
        statement
        for section in definitions["boss_360"].schema["sections"]
        for question in section["questions"]
        for statement in question["statements"]
    ]
    assert all(len(statement["scale"]) == 4 for statement in feedback_statements)
    assert all(
        option["label"] not in {"1", "2", "3", "4"}
        for statement in feedback_statements
        for option in statement["scale"]
    )
    assert all(definition.schema["local_preview"]["sample"] for definition in definitions.values())
    assert all("source" not in definition.schema for definition in definitions.values())


def test_preview_email_templates_are_synthetic_and_renderable() -> None:
    templates = build_preview_email_templates()

    assert set(templates) == {
        "preview_evaluation_invite",
        "preview_evaluation_reminder",
        "preview_campaign_reactivation",
        "preview_campaign_report",
    }
    assert all(template.key.startswith("preview_") for template in templates.values())
    assert all(template.version == PREVIEW_DEFINITION_VERSION for template in templates.values())
    assert all(
        template.required_context == frozenset({"first_name", "action_url"})
        for template in templates.values()
    )
    assert all("${first_name}" in template.html_body for template in templates.values())
    assert all("${action_url}" in template.html_body for template in templates.values())
    assert all("${first_name}" in template.text_body for template in templates.values())
    assert all("${action_url}" in template.text_body for template in templates.values())


def test_sample_answers_cover_every_visible_sample_item() -> None:
    definitions = build_preview_questionnaire_definitions()

    for definition in definitions:
        answers = build_sample_answers(definition.schema)
        assert answers

        expected = 0
        for section in definition.schema["sections"]:
            for question in section["questions"]:
                expected += (
                    len(question.get("statements", []))
                    if question.get("type") == "statement_score_set"
                    else 1
                )
        assert len(answers) == expected


def test_sample_answers_can_build_a_partial_draft() -> None:
    definition = next(
        definition
        for definition in build_preview_questionnaire_definitions()
        if definition.key == "lencioni"
    )

    assert len(build_sample_answers(definition.schema, limit=3)) == 3


async def test_preview_replacement_does_not_deactivate_system_definitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await engine.dispose()
    preview_version = 1_000_000_000 + uuid.uuid4().int % 400_000_000
    version = 1_500_000_000 + uuid.uuid4().int % 500_000_000
    monkeypatch.setattr(
        "codrut.tools.seed_local_preview.PREVIEW_DEFINITION_VERSION",
        preview_version,
    )
    definition = QuestionnaireDefinition(
        id=uuid.uuid4(),
        key="lencioni",
        version=version,
        title="Protected synthetic boundary",
        description="Synthetic protected-content boundary fixture.",
        schema={"key": "lencioni", "version": version, "sections": []},
        active=True,
        system_managed=True,
        package_id=f"synthetic-package-{uuid.uuid4().hex}",
        content_checksum=uuid.uuid4().hex * 2,
    )
    try:
        async with SessionLocal() as session:
            session.add(definition)
            await session.flush()

            preview_definitions = await _replace_preview_definitions(session)
            await session.refresh(definition)

            assert definition.active is True
            assert preview_definitions["lencioni"].active is False
            await session.rollback()
    finally:
        await engine.dispose()
