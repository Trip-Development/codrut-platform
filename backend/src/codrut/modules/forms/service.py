from codrut.modules.forms.definitions import (
    APPROVED_QUESTIONNAIRE_DEFINITIONS,
    get_approved_questionnaire_definition,
)
from codrut.modules.forms.models import QuestionnaireKey
from codrut.modules.forms.schemas import QuestionnaireDefinitionResponse


class FormsService:
    def list_definitions(self) -> list[QuestionnaireDefinitionResponse]:
        return [
            _to_response(definition)
            for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS
        ]

    def get_definition(self, key: QuestionnaireKey) -> QuestionnaireDefinitionResponse:
        return _to_response(get_approved_questionnaire_definition(key))


def _to_response(definition) -> QuestionnaireDefinitionResponse:
    return QuestionnaireDefinitionResponse(
        key=definition.key,
        version=definition.version,
        title=definition.title,
        description=definition.description,
        definition_schema=definition.schema,
    )
