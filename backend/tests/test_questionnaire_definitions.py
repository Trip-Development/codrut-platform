import pytest

from codrut.modules.forms.definitions import (
    APPROVED_QUESTIONNAIRE_DEFINITIONS,
    LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS,
    get_approved_questionnaire_definition,
)
from codrut.modules.forms.models import QuestionnaireKey
from codrut.tools.local_preview import (
    PREVIEW_DEFINITION_VERSION,
    build_preview_questionnaire_definitions,
)


def test_implementation_repository_does_not_embed_official_questionnaires() -> None:
    assert APPROVED_QUESTIONNAIRE_DEFINITIONS == ()
    assert LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS == {}

    with pytest.raises(KeyError):
        get_approved_questionnaire_definition(QuestionnaireKey.lencioni)


def test_local_preview_uses_versioned_synthetic_contracts() -> None:
    definitions = {
        definition.key: definition for definition in build_preview_questionnaire_definitions()
    }

    assert PREVIEW_DEFINITION_VERSION > 1
    assert set(definitions) == {"pcm_base", "lencioni", "distress_drivers", "boss_360"}
    assert all(
        definition.schema.get("local_preview", {}).get("sample") is True
        for definition in definitions.values()
    )
    assert all("source" not in definition.schema for definition in definitions.values())


def test_synthetic_scoring_fixtures_cover_supported_methods() -> None:
    methods = {
        definition.schema.get("scoring", {}).get("method")
        for definition in build_preview_questionnaire_definitions()
        if definition.schema.get("scoring")
    }

    assert methods == {
        "sum_by_group",
        "sum_statement_scores_by_driver",
        "average_statement_scores_by_section",
    }
