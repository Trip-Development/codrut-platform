from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.config import get_settings
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
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

    async def list_persisted_definitions(
        self,
        *,
        active_only: bool = True,
        include_private: bool = False,
    ) -> list[QuestionnaireDefinitionResponse]:
        repository = self._require_repository()
        definitions = await repository.list_definitions(active_only=active_only)
        return [
            _to_response(definition, include_private=include_private) for definition in definitions
        ]

    async def get_persisted_definition(
        self,
        key: str,
        *,
        version: int | None = None,
        include_private: bool = False,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        definition = await repository.get_definition(key, version=version)
        if definition is None:
            raise DomainError("Questionnaire definition not found.", code="definition_not_found")
        return _to_response(definition, include_private=include_private)

    async def create_definition(
        self,
        payload: QuestionnaireDefinitionCreateRequest,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        _validate_definition_schema(payload.definition_schema, require_questions=payload.active)
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
        active = payload.active if payload.active is not None else definition.active
        _validate_definition_schema(updated_schema, require_questions=active)
        has_submissions = await repository.has_submitted_responses(key, definition.version)
        has_assignments = await repository.has_assignments_for_definition(definition.id)
        if has_submissions or has_assignments or definition.system_managed:
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
                    system_managed=False,
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
        _validate_definition_schema(definition.schema, require_questions=True)
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
        if definition.system_managed:
            raise DomainError(
                "Imported system definitions are immutable. Clone a version before retiring it.",
                code="definition_system_managed",
            )
        definition.active = False
        return _to_response(definition)

    async def get_assignment_response(
        self,
        user_id: UUID,
        assignment_id: UUID,
        *,
        allowed_assignment_ids: tuple[UUID, ...] | None = None,
    ) -> QuestionnaireResponseResponse:
        repository = self._require_repository()
        assignment = await repository.get_assignment_for_user(
            assignment_id,
            user_id,
            allowed_assignment_ids=allowed_assignment_ids,
        )
        if assignment is None:
            raise DomainError("Assignment not found.", code="assignment_not_found")
        return await self._get_response_for_assignment(assignment)

    async def get_secure_assignment_response(
        self,
        token: str,
        assignment_id: UUID,
    ) -> QuestionnaireResponseResponse:
        assignment = await self._assignment_for_secure_link(token, assignment_id)
        return await self._get_response_for_assignment(assignment)

    async def get_secure_assignment_definition(
        self,
        token: str,
        assignment_id: UUID,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        assignment = await self._assignment_for_secure_link(token, assignment_id)
        await _validate_assignment_response_window(repository, assignment)
        definition = await _resolve_definition(repository, assignment)
        return _to_response(definition, include_private=False)

    async def get_assignment_definition(
        self,
        user_id: UUID,
        assignment_id: UUID,
        *,
        allowed_assignment_ids: tuple[UUID, ...] | None = None,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        assignment = await repository.get_assignment_for_user(
            assignment_id,
            user_id,
            allowed_assignment_ids=allowed_assignment_ids,
        )
        if assignment is None:
            raise DomainError("Assignment not found.", code="assignment_not_found")
        await _validate_assignment_response_window(repository, assignment)
        definition = await _resolve_definition(repository, assignment)
        return _to_response(definition, include_private=False)

    async def get_participant_definition_by_key(
        self,
        user_id: UUID,
        key: str,
        *,
        version: int | None = None,
        allowed_assignment_ids: tuple[UUID, ...] | None = None,
    ) -> QuestionnaireDefinitionResponse:
        repository = self._require_repository()
        assignment = await repository.get_assignment_for_user_by_key(
            user_id,
            key,
            version=version,
            allowed_assignment_ids=allowed_assignment_ids,
        )
        if assignment is None:
            raise DomainError("Questionnaire definition not found.", code="definition_not_found")
        await _validate_assignment_response_window(repository, assignment)
        definition = await _resolve_definition(repository, assignment)
        return _to_response(definition, include_private=False)

    async def _get_response_for_assignment(
        self,
        assignment: QuestionnaireAssignment,
    ) -> QuestionnaireResponseResponse:
        repository = self._require_repository()
        await _validate_assignment_response_window(repository, assignment)
        response = await repository.get_response_by_assignment(assignment.id)
        if response is None:
            definition = await _resolve_definition(repository, assignment)
            return QuestionnaireResponseResponse(
                id=assignment.id,
                assignment_id=assignment.id,
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
        allowed_assignment_ids: tuple[UUID, ...] | None = None,
    ) -> QuestionnaireResponseResponse:
        repository = self._require_repository()
        assignment = await repository.get_assignment_for_user(
            assignment_id,
            user_id,
            allowed_assignment_ids=allowed_assignment_ids,
        )
        if assignment is None:
            raise DomainError("Assignment not found.", code="assignment_not_found")
        return await self._save_response_for_assignment(assignment, payload, submit=submit)

    async def save_secure_assignment_response(
        self,
        token: str,
        assignment_id: UUID,
        payload: QuestionnaireResponseSaveRequest,
        *,
        submit: bool = False,
    ) -> QuestionnaireResponseResponse:
        assignment = await self._assignment_for_secure_link(token, assignment_id)
        return await self._save_response_for_assignment(assignment, payload, submit=submit)

    async def _save_response_for_assignment(
        self,
        assignment: QuestionnaireAssignment,
        payload: QuestionnaireResponseSaveRequest,
        *,
        submit: bool = False,
    ) -> QuestionnaireResponseResponse:
        repository = self._require_repository()
        assignment_id = assignment.id
        response = await repository.get_response_by_assignment(assignment_id)
        if response is not None and response.status == QuestionnaireResponseStatus.submitted:
            if submit and response.answers == payload.answers:
                return _response_to_schema(response)
            raise DomainError(
                "Submitted responses are locked. Ask the trainer to reopen this assignment.",
                code="response_locked",
            )
        await _validate_assignment_response_window(repository, assignment)
        definition = await _resolve_definition(repository, assignment)
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
                from codrut.modules.scoring.publication import ResultPublicationService
                from codrut.modules.scoring.service import ScoringService

                scoring_service = ScoringService(session)
                scoring_schema = definition.schema
                if definition.private_config:
                    scoring_schema = definition.private_config.get("schema", scoring_schema)
                try:
                    await scoring_service.compute_and_save_score(
                        assignment_id=assignment.id,
                        questionnaire_key=definition.key,
                        questionnaire_version=definition.version,
                        answers=payload.answers,
                        definition_schema=scoring_schema,
                    )
                    assignment.status = AssignmentStatus.scored
                    assignment.submitted_at = assignment.submitted_at or response.submitted_at
                    assignment.scored_at = response.submitted_at
                    await ResultPublicationService(session).reconcile_assignment(assignment.id)
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

    async def _assignment_for_secure_link(
        self,
        token: str,
        assignment_id: UUID,
    ) -> QuestionnaireAssignment:
        from sqlalchemy import select

        from codrut.modules.communications.task_links import parse_task_token
        from codrut.modules.identity.models import AssignmentInvite

        repository = self._require_repository()
        claims = parse_task_token(token, get_settings())
        if assignment_id not in claims.assignment_ids:
            raise DomainError(
                "Task link assignment scope is invalid.",
                code="task_link_scope_mismatch",
            )

        invite_result = await repository.session.execute(
            select(AssignmentInvite).where(AssignmentInvite.token == token)
        )
        invite = invite_result.scalar_one_or_none()
        if invite is None or invite.status != "active":
            raise DomainError("Task link is no longer active.", code="task_link_revoked")
        if invite.expires_at <= datetime.now(UTC):
            raise DomainError("Task link has expired.", code="task_link_expired")
        if (
            invite.company_id != claims.company_id
            or invite.respondent_profile_id != claims.respondent_profile_id
            or (invite.project_id is not None and invite.project_id != claims.project_id)
        ):
            raise DomainError(
                "Task link assignment scope is invalid.",
                code="task_link_scope_mismatch",
            )

        assignment = await repository.get_assignment_by_id(assignment_id)
        if (
            assignment is None
            or assignment.company_id != claims.company_id
            or assignment.respondent_profile_id != claims.respondent_profile_id
            or (claims.project_id is not None and assignment.project_id != claims.project_id)
            or (invite.project_id is not None and assignment.project_id != invite.project_id)
        ):
            raise DomainError(
                "Task link assignment scope is invalid.",
                code="task_link_scope_mismatch",
            )
        return assignment

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
        profile = await repository.get_participant_by_profile_id(assignment.respondent_profile_id)
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
        profile = await repository.get_participant_by_profile_id(participant_profile_id)
        if profile is None:
            raise DomainError("Participant profile not found.", code="profile_not_found")

        assignment = await repository.get_pcm_assignment(
            company_id=profile.company_id,
            participant_profile_id=profile.id,
            questionnaire_key=questionnaire_key,
        )
        if assignment is not None:
            return assignment

        definition = await _resolve_definition_by_key(repository, questionnaire_key)

        assignment = QuestionnaireAssignment(
            company_id=profile.company_id,
            respondent_profile_id=profile.id,
            questionnaire_key=questionnaire_key,
            questionnaire_definition_id=getattr(definition, "id", None),
            target_type=AssignmentTargetType.self_assessment,
            access_mode=AssignmentAccessMode.account_link,
            status=AssignmentStatus.assigned,
        )
        repository.session.add(assignment)
        await repository.session.flush()
        return assignment


def _to_response(
    definition: Any,
    *,
    include_private: bool = True,
) -> QuestionnaireDefinitionResponse:
    schema = definition.schema
    if include_private and getattr(definition, "private_config", None):
        schema = definition.private_config.get("schema", schema)
    elif not include_private:
        schema = _participant_schema(schema)
    return QuestionnaireDefinitionResponse(
        key=definition.key,
        version=definition.version,
        title=definition.title,
        description=definition.description or "",
        active=getattr(definition, "active", True),
        definition_schema=schema,
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
    required_keys = _required_answer_keys(schema)
    missing = [key for key in required_keys if key not in answers or answers[key] is None]
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


def _required_answer_keys(schema: dict) -> set[str]:
    keys: set[str] = set()
    for section in schema.get("sections", []):
        for question in section.get("questions", []):
            if question.get("required", True) is False:
                continue
            question_id = question["id"]
            if question.get("type") == "statement_score_set":
                keys.update(
                    f"{question_id}:{statement['id']}"
                    for statement in question.get("statements", [])
                )
            else:
                keys.add(question_id)
    return keys


async def _resolve_definition(
    repository: FormsRepository,
    assignment: QuestionnaireAssignment,
) -> Any:
    definition_id = getattr(assignment, "questionnaire_definition_id", None)
    if definition_id is not None and hasattr(repository, "get_definition_by_id"):
        definition = await repository.get_definition_by_id(definition_id)
        if definition is None or definition.key != assignment.questionnaire_key:
            raise DomainError(
                "Pinned questionnaire definition was not found.",
                code="assignment_definition_not_found",
            )
        return definition

    definition = await _resolve_definition_by_key(repository, assignment.questionnaire_key)
    if getattr(definition, "id", None) is not None:
        assignment.questionnaire_definition_id = definition.id
    return definition


async def _resolve_definition_by_key(
    repository: FormsRepository,
    key: str,
) -> Any:
    if hasattr(repository, "get_definition"):
        definition = await repository.get_definition(key)
        if definition is not None:
            return definition
    raise DomainError(
        "Questionnaire definition not found.",
        code="definition_not_found",
    )


def _participant_schema(schema: dict[str, Any]) -> dict[str, Any]:
    private_keys = {
        "scoring",
        "source",
        "interpretation",
        "interpretations",
        "private_feedback",
        "trainer_feedback",
    }

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: clean(child) for key, child in value.items() if key not in private_keys}
        if isinstance(value, list):
            return [clean(child) for child in value]
        return deepcopy(value)

    return clean(schema)


async def _validate_assignment_response_window(
    repository: FormsRepository,
    assignment: QuestionnaireAssignment,
) -> None:
    now = datetime.now(UTC)
    if assignment.due_at is not None and assignment.due_at <= now:
        raise DomainError(
            "Assignment response window has closed.",
            code="assignment_closed",
        )
    project = await repository.get_project_for_assignment(assignment)
    if project is None:
        return
    if project.form_opens_at is not None and project.form_opens_at > now:
        raise DomainError(
            "Project questionnaires are not open yet.",
            code="project_not_open",
        )
    close_candidates = [
        value for value in (project.form_closes_at, project.due_at) if value is not None
    ]
    if close_candidates and min(close_candidates) <= now:
        raise DomainError(
            "Project questionnaire window has closed.",
            code="project_closed",
        )


def _validate_definition_schema(
    schema: dict[str, Any],
    *,
    require_questions: bool,
) -> None:
    sections = schema.get("sections")
    if not isinstance(sections, list) or not sections:
        raise DomainError(
            "Questionnaire definition must include at least one section.",
            code="definition_invalid",
        )
    for section in sections:
        questions = section.get("questions") if isinstance(section, dict) else None
        if not isinstance(questions, list) or (require_questions and not questions):
            raise DomainError(
                "Questionnaire definition sections must include at least one item.",
                code="definition_invalid",
            )
