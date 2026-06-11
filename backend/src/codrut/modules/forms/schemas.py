from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from codrut.modules.forms.models import QuestionnaireResponseStatus

QuestionnaireSlug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9_]+$",
    ),
]


class QuestionnaireDefinitionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    version: int
    title: str
    description: str
    active: bool = True
    definition_schema: dict[str, Any] = Field(alias="schema")


class QuestionnaireDefinitionCreateRequest(BaseModel):
    key: QuestionnaireSlug
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    definition_schema: dict[str, Any] = Field(alias="schema")
    active: bool = True


class QuestionnaireDefinitionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    definition_schema: dict[str, Any] | None = Field(default=None, alias="schema")
    active: bool | None = None


class QuestionnaireResponseSaveRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class QuestionnaireResponseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    questionnaire_key: str
    questionnaire_version: int
    status: QuestionnaireResponseStatus
    answers: dict[str, Any]


class ParticipantOnboardingResponse(BaseModel):
    required: bool
    questionnaire_key: str | None = None
    assignment_id: UUID | None = None
    href: str | None = None
