from fastapi import APIRouter

from codrut.modules.forms.models import QuestionnaireKey
from codrut.modules.forms.schemas import QuestionnaireDefinitionResponse
from codrut.modules.forms.service import FormsService

router = APIRouter()


@router.get("/definitions", response_model=list[QuestionnaireDefinitionResponse])
async def list_questionnaire_definitions() -> list[QuestionnaireDefinitionResponse]:
    return FormsService().list_definitions()


@router.get("/definitions/{key}", response_model=QuestionnaireDefinitionResponse)
async def get_questionnaire_definition(
    key: QuestionnaireKey,
) -> QuestionnaireDefinitionResponse:
    return FormsService().get_definition(key)
