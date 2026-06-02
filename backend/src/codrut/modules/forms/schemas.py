from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from codrut.modules.forms.models import QuestionnaireKey, QuestionnaireResponseStatus


class QuestionnaireDefinitionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: QuestionnaireKey
    version: int
    title: str
    description: str
    definition_schema: dict[str, Any] = Field(alias="schema")


class QuestionnaireResponseSaveRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class QuestionnaireResponseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    questionnaire_key: QuestionnaireKey
    questionnaire_version: int
    status: QuestionnaireResponseStatus
    answers: dict[str, Any]
