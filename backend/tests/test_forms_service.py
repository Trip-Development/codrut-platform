from codrut.modules.forms.models import QuestionnaireKey
from codrut.modules.forms.service import FormsService


def test_forms_service_lists_approved_definitions() -> None:
    definitions = FormsService().list_definitions()

    assert {definition.key for definition in definitions} == {
        QuestionnaireKey.pcm_base,
        QuestionnaireKey.phase,
        QuestionnaireKey.lencioni,
        QuestionnaireKey.lencioni_en,
        QuestionnaireKey.distress_drivers,
        QuestionnaireKey.distress_drivers_en,
        QuestionnaireKey.boss_360,
        QuestionnaireKey.boss_360_en,
    }


def test_forms_service_returns_definition_schema() -> None:
    definition = FormsService().get_definition(QuestionnaireKey.lencioni)

    assert definition.version == 1
    assert definition.definition_schema["schema_version"] == "questionnaire.v1"
    assert definition.definition_schema["sections"][0]["questions"][0]["type"] == "likert"
