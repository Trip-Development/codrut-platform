from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codrut.modules.forms.models import QuestionnaireKey


class QuestionnaireDefinitionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: QuestionnaireKey
    version: int
    title: str
    description: str
    definition_schema: dict[str, Any] = Field(alias="schema")
