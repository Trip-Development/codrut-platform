"""Compatibility surface for database-backed questionnaire definitions.

Official questionnaire content is imported from a protected content package and is
never embedded in the implementation repository. Local preview definitions live in
``codrut.tools.local_preview`` and contain synthetic sample questions only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codrut.modules.forms.models import QuestionnaireKey

DefinitionSchema = dict[str, Any]


@dataclass(frozen=True)
class ApprovedQuestionnaireDefinition:
    key: QuestionnaireKey
    version: int
    title: str
    description: str
    schema: DefinitionSchema


APPROVED_QUESTIONNAIRE_DEFINITIONS: tuple[ApprovedQuestionnaireDefinition, ...] = ()
LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS: dict[str, ApprovedQuestionnaireDefinition] = {}


def get_approved_questionnaire_definition(
    key: QuestionnaireKey | str,
) -> ApprovedQuestionnaireDefinition:
    raise KeyError(str(key))
