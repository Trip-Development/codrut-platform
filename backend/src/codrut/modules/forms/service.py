from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.forms.definitions import (
    APPROVED_QUESTIONNAIRE_DEFINITIONS,
    LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS,
    get_approved_questionnaire_definition,
)
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireKey,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)
from codrut.modules.forms.repository import FormsRepository
from codrut.modules.forms.schemas import (
    ParticipantOnboardingResponse,
    QuestionnaireDefinitionCreateRequest,
    QuestionnaireDefinitionResponse,
    QuestionnaireDefinitionUpdateRequest,
    QuestionnaireResponseResponse,
    QuestionnaireResponseSaveRequest,
)


class FormsService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.repository = FormsRepository(session) if session is not None else None

    def list_definitions(self) -> list[QuestionnaireDefinitionResponse]:
        return [_to_response(definition) for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS]

    def get_definition(self, key: str) -> QuestionnaireDefinitionResponse:
        return _to_response(get_approved_questionnaire_definition(key))

    async def list_persisted_definitions(
        self,
        *,
        active_only: bool = True,
    ) -> list[QuestionnaireDefinitionResponse]:
        repository = self._require_repository()
        await self._seed_catalog_definitions(repository)
        definitions = await repository.list_definitions(active_only=active_only)
        return [_to_response(definition) for definition in definitions]

    async def get_persisted_definition(
        self,
        key: str,
        *,
        version: int | None = None,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        await self._seed_catalog_definitions(repository)
        definition = await repository.get_definition(key, version=version)
        if definition is None and version is None and key in LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS:
            return _to_response(LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS[key])
        if definition is None:
            raise DomainError("Questionnaire definition not found.", code="definition_not_found")
        return _to_response(definition)

    async def create_definition(
        self,
        payload: QuestionnaireDefinitionCreateRequest,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        _validate_definition_schema(payload.definition_schema)
        version = await repository.get_latest_version(payload.key) + 1
        if payload.active:
            await repository.deactivate_definitions_for_key(payload.key)
        definition = await repository.add_definition(
            QuestionnaireDefinition(
                key=payload.key,
                version=version,
                title=payload.title.strip(),
                description=payload.description or "",
                schema=payload.definition_schema,
                active=payload.active,
            )
        )
        return _to_response(definition)

    async def update_definition(
        self,
        key: str,
        payload: QuestionnaireDefinitionUpdateRequest,
        *,
        version: int | None = None,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        definition = await repository.get_definition(key, version=version)
        if definition is None:
            raise DomainError("Questionnaire definition not found.", code="definition_not_found")
        updated_schema = definition.schema
        if payload.definition_schema is not None:
            updated_schema = payload.definition_schema
        _validate_definition_schema(updated_schema)
        has_submissions = await repository.has_submitted_responses(key, definition.version)
        if has_submissions:
            next_version = await repository.get_latest_version(key) + 1
            await repository.deactivate_definitions_for_key(key)
            definition = await repository.add_definition(
                QuestionnaireDefinition(
                    key=key,
                    version=next_version,
                    title=(payload.title or definition.title).strip(),
                    description=(
                        payload.description
                        if payload.description is not None
                        else definition.description
                    ),
                    schema=updated_schema,
                    active=payload.active if payload.active is not None else True,
                )
            )
        else:
            definition.title = (payload.title or definition.title).strip()
            definition.description = (
                payload.description if payload.description is not None else definition.description
            )
            definition.schema = updated_schema
            if payload.active is not None:
                definition.active = payload.active
        if definition.active:
            await repository.deactivate_definitions_for_key(key, except_version=definition.version)
        return _to_response(definition)

    async def activate_definition(
        self,
        key: str,
        version: int,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        definition = await repository.get_definition(key, version=version)
        if definition is None:
            raise DomainError("Questionnaire definition not found.", code="definition_not_found")
        await repository.deactivate_definitions_for_key(key, except_version=definition.version)
        definition.active = True
        return _to_response(definition)

    async def retire_definition(
        self,
        key: str,
        *,
        version: int | None = None,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        definition = await repository.get_definition(key, version=version)
        if definition is None:
            raise DomainError("Questionnaire definition not found.", code="definition_not_found")
        definition.active = False
        return _to_response(definition)

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
            definition = await _resolve_definition(
                repository,
                assignment.questionnaire_key,
            )
            return QuestionnaireResponseResponse(
                id=assignment_id,
                assignment_id=assignment_id,
                questionnaire_key=definition.key,
                questionnaire_version=definition.version,
                status=QuestionnaireResponseStatus.draft,
                answers={},
            )
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
        definition = await _resolve_definition(
            repository,
            assignment.questionnaire_key,
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
            await self._apply_profile_answer_side_effects(
                assignment,
                definition.key,
                payload.answers,
            )

            session = getattr(repository, "session", None)
            if session is not None:
                from codrut.modules.scoring.service import ScoringService

                scoring_service = ScoringService(session)
                try:
                    await scoring_service.compute_and_save_score(
                        assignment_id=assignment.id,
                        questionnaire_key=definition.key,
                        questionnaire_version=definition.version,
                        answers=payload.answers,
                        definition_schema=definition.schema,
                    )
                    assignment.status = AssignmentStatus.scored
                    assignment.submitted_at = assignment.submitted_at or response.submitted_at
                    assignment.scored_at = response.submitted_at
                except DomainError as e:
                    if e.code not in {"scoring_not_supported", "scoring_metadata_missing"}:
                        raise
                    assignment.status = AssignmentStatus.submitted
                    assignment.submitted_at = assignment.submitted_at or response.submitted_at
            else:
                assignment.status = AssignmentStatus.submitted
                assignment.submitted_at = assignment.submitted_at or response.submitted_at
        elif assignment.status == AssignmentStatus.assigned:
            assignment.status = AssignmentStatus.started
            assignment.started_at = assignment.started_at or datetime.now(UTC)
        return _response_to_schema(response)

    async def get_participant_onboarding(self, user_id: UUID) -> ParticipantOnboardingResponse:
        repository = self._require_repository()
        profile = await repository.get_permanent_participant_for_user(user_id)
        if profile is None:
            return ParticipantOnboardingResponse(required=False)

        if not profile.pcm_base or not profile.pcm_phase:
            assignment = await self._ensure_pcm_assignment(profile.id, "pcm_base")
            return _onboarding_response(assignment)

        return ParticipantOnboardingResponse(required=False)

    def _require_repository(self) -> FormsRepository:
        if self.repository is None:
            raise RuntimeError("FormsService requires a database session for response operations")
        return self.repository

    async def _apply_profile_answer_side_effects(
        self,
        assignment: QuestionnaireAssignment,
        questionnaire_key: str,
        answers: dict[str, Any],
    ) -> None:
        if questionnaire_key not in {QuestionnaireKey.pcm_base.value, QuestionnaireKey.phase.value}:
            return

        repository = self._require_repository()
        profile = await repository.get_participant_by_profile_id(
            assignment.respondent_profile_id
        )
        if profile is None:
            return

        if questionnaire_key == QuestionnaireKey.pcm_base.value:
            profile.pcm_base = _clean_pcm_answer(answers.get("pcm_base"))
            profile.pcm_profile = profile.pcm_base
            profile.pcm_phase = _clean_pcm_answer(answers.get("pcm_phase"))
        elif questionnaire_key == QuestionnaireKey.phase.value:
            profile.pcm_phase = _clean_pcm_answer(answers.get("pcm_phase"))

    async def _ensure_pcm_assignment(
        self,
        participant_profile_id: UUID,
        questionnaire_key: str,
    ) -> QuestionnaireAssignment:
        repository = self._require_repository()
        profile = await repository.get_participant_by_profile_id(
            participant_profile_id
        )
        if profile is None:
            raise DomainError("Participant profile not found.", code="profile_not_found")

        assignment = await repository.get_pcm_assignment(
            company_id=profile.company_id,
            participant_profile_id=profile.id,
            questionnaire_key=questionnaire_key,
        )
        if assignment is not None:
            return assignment

        assignment = QuestionnaireAssignment(
            company_id=profile.company_id,
            respondent_profile_id=profile.id,
            questionnaire_key=questionnaire_key,
            target_type=AssignmentTargetType.self_assessment,
            access_mode=AssignmentAccessMode.account_link,
            status=AssignmentStatus.assigned,
        )
        repository.session.add(assignment)
        await repository.session.flush()
        return assignment

    async def _seed_catalog_definitions(self, repository: FormsRepository) -> None:
        for catalog_definition in APPROVED_QUESTIONNAIRE_DEFINITIONS:
            existing = await repository.get_definition(
                catalog_definition.key,
                version=catalog_definition.version,
            )
            if existing is None:
                await repository.add_definition(
                    QuestionnaireDefinition(
                        key=catalog_definition.key,
                        version=catalog_definition.version,
                        title=catalog_definition.title,
                        description=catalog_definition.description,
                        schema=deepcopy(catalog_definition.schema),
                        active=True,
                    )
                )
                continue

            if (
                existing.title == catalog_definition.title
                and (existing.description or "") == catalog_definition.description
                and existing.schema == catalog_definition.schema
                and existing.active
            ):
                continue

            has_submissions = await repository.has_submitted_responses(
                existing.key,
                existing.version,
            )
            if not has_submissions:
                existing.title = catalog_definition.title
                existing.description = catalog_definition.description
                existing.schema = deepcopy(catalog_definition.schema)
                existing.active = True
                await repository.deactivate_definitions_for_key(
                    existing.key,
                    except_version=existing.version,
                )
                continue

            next_version = await repository.get_latest_version(catalog_definition.key) + 1
            await repository.deactivate_definitions_for_key(catalog_definition.key)
            await repository.add_definition(
                QuestionnaireDefinition(
                    key=catalog_definition.key,
                    version=next_version,
                    title=catalog_definition.title,
                    description=catalog_definition.description,
                    schema=deepcopy(catalog_definition.schema),
                    active=True,
                )
            )
        for alias_key in LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS:
            await repository.deactivate_definitions_for_key(alias_key)


def _to_response(definition: Any) -> QuestionnaireDefinitionResponse:
    return QuestionnaireDefinitionResponse(
        key=definition.key,
        version=definition.version,
        title=definition.title,
        description=definition.description or "",
        active=getattr(definition, "active", True),
        definition_schema=definition.schema,
    )


def _response_to_schema(response: QuestionnaireResponse) -> QuestionnaireResponseResponse:
    return QuestionnaireResponseResponse.model_validate(response)


def _onboarding_response(assignment: QuestionnaireAssignment) -> ParticipantOnboardingResponse:
    return ParticipantOnboardingResponse(
        required=True,
        questionnaire_key=assignment.questionnaire_key,
        assignment_id=assignment.id,
        href=f"/participant/questionnaires/{assignment.questionnaire_key}?assignmentId={assignment.id}",
    )


def _clean_pcm_answer(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _validate_submit_answers(schema: dict, answers: dict) -> None:
    allowed_values = _allowed_answer_values(schema)
    missing = [key for key in allowed_values if key not in answers or answers[key] is None]
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


def _allowed_answer_values(schema: dict) -> dict[str, set[Any]]:
    values: dict[str, set[Any]] = {}
    for section in schema.get("sections", []):
        for question in section.get("questions", []):
            question_id = question["id"]
            scale_values = {option["value"] for option in question.get("scale", [])}
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


async def _resolve_definition(
    repository: FormsRepository,
    key: str,
) -> Any:
    if hasattr(repository, "get_definition"):
        definition = await repository.get_definition(key)
        if definition is not None:
            return definition
    try:
        return get_approved_questionnaire_definition(key)
    except KeyError as exc:
        raise DomainError(
            "Questionnaire definition not found.",
            code="definition_not_found",
        ) from exc


def _validate_definition_schema(schema: dict[str, Any]) -> None:
    sections = schema.get("sections")
    if not isinstance(sections, list) or not sections:
        raise DomainError(
            "Questionnaire definition must include at least one section.",
            code="definition_invalid",
        )
    for section in sections:
        questions = section.get("questions") if isinstance(section, dict) else None
        if not isinstance(questions, list) or not questions:
            raise DomainError(
                "Questionnaire definition sections must include at least one item.",
                code="definition_invalid",
            )
