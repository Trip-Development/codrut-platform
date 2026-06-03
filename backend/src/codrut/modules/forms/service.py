from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus
from codrut.modules.forms.definitions import (
    APPROVED_QUESTIONNAIRE_DEFINITIONS,
    get_approved_questionnaire_definition,
)
from codrut.modules.forms.models import (
    QuestionnaireKey,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)
from codrut.modules.forms.repository import FormsRepository
from codrut.modules.forms.schemas import (
    QuestionnaireDefinitionResponse,
    QuestionnaireResponseResponse,
    QuestionnaireResponseSaveRequest,
)


class FormsService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.repository = FormsRepository(session) if session is not None else None

    def list_definitions(self) -> list[QuestionnaireDefinitionResponse]:
        return [
            _to_response(definition)
            for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS
        ]

    def get_definition(self, key: QuestionnaireKey) -> QuestionnaireDefinitionResponse:
        return _to_response(get_approved_questionnaire_definition(key))

    async def get_assignment_response(
        self,
        user_id: UUID,
        assignment_id: UUID,
    ) -> QuestionnaireResponseResponse:
        repository = self._require_repository()
        assignment = await repository.get_assignment_for_user(assignment_id, user_id)
        if assignment is None:
            raise DomainError("Assignment not found.", code="assignment_not_found")
        response = await repository.get_response_by_assignment(assignment_id)
        if response is None:
            raise DomainError("Response not found.", code="response_not_found")
        return _response_to_schema(response)

    async def save_assignment_response(
        self,
        user_id: UUID,
        assignment_id: UUID,
        payload: QuestionnaireResponseSaveRequest,
        *,
        submit: bool = False,
    ) -> QuestionnaireResponseResponse:
        repository = self._require_repository()
        assignment = await repository.get_assignment_for_user(assignment_id, user_id)
        if assignment is None:
            raise DomainError("Assignment not found.", code="assignment_not_found")
        definition = get_approved_questionnaire_definition(
            QuestionnaireKey(assignment.questionnaire_key)
        )
        response = await repository.get_response_by_assignment(assignment_id)
        if submit:
            _validate_submit_answers(definition.schema, payload.answers)
        if response is None:
            response = await repository.add_response(
                QuestionnaireResponse(
                    assignment_id=assignment.id,
                    questionnaire_key=definition.key,
                    questionnaire_version=definition.version,
                    status=QuestionnaireResponseStatus.draft,
                    answers=payload.answers,
                )
            )
        else:
            response.answers = payload.answers
        if submit:
            response.status = QuestionnaireResponseStatus.submitted
            response.submitted_at = response.submitted_at or datetime.now(UTC)
            assignment.status = AssignmentStatus.submitted
            assignment.submitted_at = assignment.submitted_at or response.submitted_at
        elif assignment.status == AssignmentStatus.assigned:
            assignment.status = AssignmentStatus.started
            assignment.started_at = assignment.started_at or datetime.now(UTC)
        return _response_to_schema(response)

    def _require_repository(self) -> FormsRepository:
        if self.repository is None:
            raise RuntimeError("FormsService requires a database session for response operations")
        return self.repository


def _to_response(definition) -> QuestionnaireDefinitionResponse:
    return QuestionnaireDefinitionResponse(
        key=definition.key,
        version=definition.version,
        title=definition.title,
        description=definition.description,
        definition_schema=definition.schema,
    )


def _response_to_schema(response: QuestionnaireResponse) -> QuestionnaireResponseResponse:
    return QuestionnaireResponseResponse.model_validate(response)


def _validate_submit_answers(schema: dict, answers: dict) -> None:
    allowed_values = _allowed_answer_values(schema)
    missing = [
        key
        for key in allowed_values
        if key not in answers or answers[key] is None
    ]
    if missing:
        raise DomainError(
            "Submitted response is missing required answers.",
            code="response_incomplete",
        )
    invalid = [
        key
        for key, value in answers.items()
        if key in allowed_values and value not in allowed_values[key]
    ]
    if invalid:
        raise DomainError(
            "Submitted response has answers outside the allowed scale.",
            code="response_invalid_answer",
        )


def _allowed_answer_values(schema: dict) -> dict[str, set[int]]:
    values: dict[str, set[int]] = {}
    for section in schema.get("sections", []):
        for question in section.get("questions", []):
            question_id = question["id"]
            scale_values = {
                option["value"]
                for option in question.get("scale", [])
            }
            if question.get("type") == "statement_score_set":
                values.update(
                    {
                        f"{question_id}:{statement['id']}": scale_values
                        for statement in question.get("statements", [])
                    }
                )
            else:
                values[question_id] = scale_values
    return values
