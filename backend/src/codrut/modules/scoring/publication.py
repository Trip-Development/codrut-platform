import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import case, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.scoring.models import (
    ResultPublication,
    ResultPublicationKind,
    ScoringResult,
)

COMPLETED_ASSIGNMENT_STATUSES = {
    AssignmentStatus.submitted,
    AssignmentStatus.validated,
    AssignmentStatus.scored,
}

LENCIONI_QUESTIONNAIRE_KEYS = {"lencioni", "lencioni_en"}
DISTRESS_DRIVER_QUESTIONNAIRE_KEYS = {"distress_drivers", "distress_drivers_en"}
ICARE_QUESTIONNAIRE_KEYS = {"boss_360", "boss_360_en", "icare"}


def required_feedback_count(
    *,
    eligible_count: int,
    minimum_completed: int = 2,
    target_completed: int = 3,
) -> int:
    # `target_completed` remains useful for invitation/progress planning, but it
    # must not silently raise the participant-facing privacy threshold. Results
    # become publishable at the explicit minimum and are then split into cohorts,
    # each of which independently enforces that same minimum.
    _ = eligible_count, target_completed
    return max(1, minimum_completed)


class ResultPublicationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reconcile_assignment(self, assignment_id: UUID) -> None:
        row = (
            await self.session.execute(
                select(QuestionnaireAssignment, QuestionnaireDefinition, ScoringResult)
                .outerjoin(
                    QuestionnaireDefinition,
                    QuestionnaireDefinition.id
                    == QuestionnaireAssignment.questionnaire_definition_id,
                )
                .outerjoin(
                    ScoringResult,
                    ScoringResult.assignment_id == QuestionnaireAssignment.id,
                )
                .where(QuestionnaireAssignment.id == assignment_id)
            )
        ).first()
        if row is None:
            return
        assignment, definition, scoring_result = row
        await self._reconcile_individual(assignment, definition, scoring_result)
        if (
            assignment.target_type == AssignmentTargetType.person
            and assignment.target_person_id is not None
            and assignment.target_person_id != assignment.respondent_profile_id
        ):
            await self._reconcile_aggregate(assignment, definition)

    async def reconcile_all(self) -> int:
        assignment_ids = list(
            (
                await self.session.execute(
                    select(QuestionnaireAssignment.id)
                    .join(ScoringResult, ScoringResult.assignment_id == QuestionnaireAssignment.id)
                    .order_by(QuestionnaireAssignment.created_at, QuestionnaireAssignment.id)
                )
            ).scalars()
        )
        for assignment_id in assignment_ids:
            await self.reconcile_assignment(assignment_id)
        return len(assignment_ids)

    async def _reconcile_individual(
        self,
        assignment: QuestionnaireAssignment,
        definition: QuestionnaireDefinition | None,
        scoring_result: ScoringResult | None,
    ) -> None:
        publication_key = f"individual:{assignment.id}"
        policy = _participant_result_policy(definition)
        allowed_target_types = policy.get("target_types", ["self", "team"])
        allowed_dimensions = _dimension_ids(policy)
        should_publish = bool(
            definition is not None
            and scoring_result is not None
            and policy.get("publication", "none") != "none"
            and assignment.target_type.value in allowed_target_types
            and (
                not policy.get("require_self_target", False)
                or assignment.target_person_id == assignment.respondent_profile_id
            )
            and any(dimension in scoring_result.scores for dimension in allowed_dimensions)
        )
        if not should_publish:
            await self._revoke(publication_key)
            return
        assert definition is not None
        await self._publish(
            publication_key=publication_key,
            participant_profile_id=assignment.respondent_profile_id,
            assignment=assignment,
            definition=definition,
            source_assignment_id=assignment.id,
            kind=ResultPublicationKind.individual,
            source_count=1,
            policy_snapshot=_safe_individual_policy_snapshot(policy),
        )

    async def _reconcile_aggregate(
        self,
        assignment: QuestionnaireAssignment,
        definition: QuestionnaireDefinition | None,
    ) -> None:
        assert assignment.target_person_id is not None
        await self._lock_aggregate_scope(assignment)
        feedback_policy = _effective_feedback_policy(definition)
        publication_key = _aggregate_publication_key(assignment)
        if definition is None or feedback_policy.get("publication", "none") != "aggregate":
            await self._revoke(publication_key)
            return

        statement = (
            select(QuestionnaireAssignment, ScoringResult)
            .outerjoin(ScoringResult, ScoringResult.assignment_id == QuestionnaireAssignment.id)
            .where(QuestionnaireAssignment.company_id == assignment.company_id)
            .where(QuestionnaireAssignment.questionnaire_key == assignment.questionnaire_key)
            .where(QuestionnaireAssignment.target_type == AssignmentTargetType.person)
            .where(QuestionnaireAssignment.target_person_id == assignment.target_person_id)
            .where(QuestionnaireAssignment.respondent_profile_id != assignment.target_person_id)
        )
        statement = (
            statement.where(QuestionnaireAssignment.project_id.is_(None))
            if assignment.project_id is None
            else statement.where(QuestionnaireAssignment.project_id == assignment.project_id)
        )
        statement = (
            statement.where(QuestionnaireAssignment.assessment_cycle_id.is_(None))
            if assignment.assessment_cycle_id is None
            else statement.where(
                QuestionnaireAssignment.assessment_cycle_id
                == assignment.assessment_cycle_id
            )
        )
        statement = (
            statement.where(QuestionnaireAssignment.questionnaire_definition_id.is_(None))
            if assignment.questionnaire_definition_id is None
            else statement.where(
                QuestionnaireAssignment.questionnaire_definition_id
                == assignment.questionnaire_definition_id
            )
        )
        candidate_rows = [
            (candidate, result)
            for candidate, result in (await self.session.execute(statement)).all()
            if candidate.status != AssignmentStatus.cancelled
        ]
        rows, publication_round_id, merged_round_ids = _aggregate_cycle_rows(
            candidate_rows,
            assignment.assignment_round_id,
        )
        publication_key = _aggregate_publication_key(
            assignment,
            assignment_round_id=publication_round_id,
        )
        for merged_round_id in merged_round_ids:
            if merged_round_id != publication_round_id:
                await self._revoke(
                    _aggregate_publication_key(
                        assignment,
                        assignment_round_id=merged_round_id,
                    )
                )
        completed_rows = [
            (candidate, result)
            for candidate, result in rows
            if candidate.status in COMPLETED_ASSIGNMENT_STATUSES and result is not None
        ]
        minimum_completed = _positive_int(feedback_policy.get("minimum_completed"), 2)
        target_completed = _positive_int(feedback_policy.get("target_completed"), 3)
        required = required_feedback_count(
            eligible_count=len(rows),
            minimum_completed=minimum_completed,
            target_completed=target_completed,
        )
        dimension_ids = _dimension_ids(feedback_policy)
        visible_dimensions = {
            dimension
            for dimension in dimension_ids
            if sum(dimension in result.scores for _candidate, result in completed_rows) >= required
        }
        if len(completed_rows) < required or not visible_dimensions:
            await self._revoke(publication_key)
            return

        await self._publish(
            publication_key=publication_key,
            participant_profile_id=assignment.target_person_id,
            assignment=assignment,
            definition=definition,
            source_assignment_id=None,
            kind=ResultPublicationKind.aggregate_360,
            source_count=len(completed_rows),
            policy_snapshot={
                "publication": "aggregate",
                "minimum_completed": minimum_completed,
                "target_completed": target_completed,
                "required_completed": required,
                "dimension_ids": sorted(visible_dimensions),
                "source_assignment_ids": sorted(
                    str(candidate.id) for candidate, _result in completed_rows
                ),
            },
            assignment_round_id=publication_round_id,
        )

    async def _lock_aggregate_scope(
        self,
        assignment: QuestionnaireAssignment,
    ) -> None:
        """Serialize publication decisions that read the same response cohort."""
        lock_scope = ":".join(
            (
                "result-publication",
                str(assignment.company_id),
                str(assignment.project_id or "none"),
                str(assignment.assessment_cycle_id or "none"),
                str(assignment.target_person_id),
                str(
                    assignment.questionnaire_definition_id
                    or assignment.questionnaire_key
                ),
            )
        )
        await self.session.execute(
            text(
                "select pg_advisory_xact_lock("
                "hashtextextended(:lock_scope, 0)"
                ")"
            ),
            {"lock_scope": lock_scope},
        )

    async def _publish(
        self,
        *,
        publication_key: str,
        participant_profile_id: UUID,
        assignment: QuestionnaireAssignment,
        definition: QuestionnaireDefinition,
        source_assignment_id: UUID | None,
        kind: ResultPublicationKind,
        source_count: int,
        policy_snapshot: dict[str, Any],
        assignment_round_id: UUID | None = None,
    ) -> None:
        now = datetime.now(UTC)
        values = {
            "publication_key": publication_key,
            "participant_profile_id": participant_profile_id,
            "company_id": assignment.company_id,
            "project_id": assignment.project_id,
            "assignment_round_id": assignment_round_id or assignment.assignment_round_id,
            "assessment_cycle_id": assignment.assessment_cycle_id,
            "questionnaire_definition_id": assignment.questionnaire_definition_id,
            "questionnaire_key": assignment.questionnaire_key,
            "source_assignment_id": source_assignment_id,
            "kind": kind,
            "source_count": source_count,
            "definition_checksum": definition_publication_checksum(definition),
            "policy_snapshot": policy_snapshot,
            "published_at": now,
            "revoked_at": None,
        }
        statement = insert(ResultPublication).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[ResultPublication.publication_key],
            set_={
                **{
                    key: value
                    for key, value in values.items()
                    if key not in {"publication_key", "published_at"}
                },
                "published_at": case(
                    (ResultPublication.revoked_at.is_not(None), now),
                    else_=ResultPublication.published_at,
                ),
                "updated_at": now,
            },
        )
        await self.session.execute(statement)

    async def _revoke(self, publication_key: str) -> None:
        now = datetime.now(UTC)
        await self.session.execute(
            update(ResultPublication)
            .where(ResultPublication.publication_key == publication_key)
            .where(ResultPublication.revoked_at.is_(None))
            .values(revoked_at=now, updated_at=now)
        )


def _participant_result_policy(
    definition: QuestionnaireDefinition | None,
) -> dict[str, Any]:
    policy = _effective_feedback_policy(definition).get("participant_results")
    return policy if isinstance(policy, dict) else {}


def _effective_feedback_policy(
    definition: QuestionnaireDefinition | None,
) -> dict[str, Any]:
    if definition is None:
        return {}
    if isinstance(definition.feedback_policy, dict) and definition.feedback_policy:
        return definition.feedback_policy

    schema = _definition_scoring_schema(definition)
    if schema is None:
        return {}

    if definition.key in LENCIONI_QUESTIONNAIRE_KEYS:
        dimension_ids = _scoring_collection_ids(schema, "groups")
        if not dimension_ids:
            return {}
        return {
            "participant_results": {
                "publication": "scores_and_interpretation",
                "dimension_ids": dimension_ids,
                "target_types": ["team"],
                "include_primary_result": True,
            }
        }

    if definition.key in DISTRESS_DRIVER_QUESTIONNAIRE_KEYS:
        dimension_ids = _scoring_collection_ids(schema, "drivers")
        if not dimension_ids:
            return {}
        return {
            "participant_results": {
                "publication": "scores",
                "dimension_ids": dimension_ids,
                "target_types": ["self"],
                "include_primary_result": True,
            }
        }

    if definition.key in ICARE_QUESTIONNAIRE_KEYS:
        dimension_ids = _statement_score_set_ids(schema)
        if not dimension_ids:
            return {}
        return {
            "publication": "aggregate",
            "minimum_completed": 2,
            "target_completed": 3,
            "dimension_ids": dimension_ids,
            "participant_results": {
                "publication": "scores",
                "dimension_ids": dimension_ids,
                "target_types": ["person"],
                "require_self_target": True,
                "include_primary_result": True,
            },
        }

    return {}


def definition_publication_checksum(definition: QuestionnaireDefinition) -> str:
    if definition.content_checksum:
        return definition.content_checksum
    payload = {
        "key": definition.key,
        "version": definition.version,
        "title": definition.title,
        "description": definition.description,
        "schema": definition.schema,
        "private_config": definition.private_config,
        "feedback_policy": definition.feedback_policy,
        "trainer_visibility_policy": definition.trainer_visibility_policy,
    }
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _definition_scoring_schema(definition: QuestionnaireDefinition) -> dict[str, Any] | None:
    private_schema = (definition.private_config or {}).get("schema")
    for candidate in (private_schema, definition.schema):
        if isinstance(candidate, dict) and isinstance(candidate.get("scoring"), dict):
            return candidate
    return None


def _scoring_collection_ids(schema: dict[str, Any], collection: str) -> list[str]:
    scoring = schema.get("scoring")
    if not isinstance(scoring, dict):
        return []
    return [
        dimension_id.strip()
        for item in scoring.get(collection, [])
        if isinstance(item, dict)
        and isinstance((dimension_id := item.get("id")), str)
        and dimension_id.strip()
    ]


def _statement_score_set_ids(schema: dict[str, Any]) -> list[str]:
    dimension_ids: list[str] = []
    for section in schema.get("sections", []):
        if not isinstance(section, dict):
            continue
        for question in section.get("questions", []):
            if not isinstance(question, dict) or question.get("type") != "statement_score_set":
                continue
            dimension_id = question.get("id")
            if isinstance(dimension_id, str) and dimension_id.strip():
                dimension_ids.append(dimension_id.strip())
    return dimension_ids


def _dimension_ids(policy: dict[str, Any]) -> set[str]:
    return {
        value.strip()
        for value in policy.get("dimension_ids", [])
        if isinstance(value, str) and value.strip()
    }


def _safe_individual_policy_snapshot(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "publication": policy.get("publication", "none"),
        "dimension_ids": sorted(_dimension_ids(policy)),
        "target_types": [
            value
            for value in policy.get("target_types", ["self", "team"])
            if isinstance(value, str)
        ],
        "require_self_target": bool(policy.get("require_self_target", False)),
        "include_primary_result": bool(policy.get("include_primary_result", True)),
    }


def _positive_int(value: object, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return fallback
    return value


def _aggregate_publication_key(
    assignment: QuestionnaireAssignment,
    *,
    assignment_round_id: UUID | None = None,
) -> str:
    return ":".join(
        (
            "aggregate-360",
            str(assignment.target_person_id),
            str(assignment.project_id or "none"),
            str(assignment.assessment_cycle_id or "legacy"),
            str(assignment_round_id or assignment.assignment_round_id),
            str(assignment.questionnaire_definition_id or assignment.questionnaire_key),
        )
    )


def _aggregate_cycle_rows(
    rows: list[tuple[QuestionnaireAssignment, ScoringResult | None]],
    current_round_id: UUID,
) -> tuple[
    list[tuple[QuestionnaireAssignment, ScoringResult | None]],
    UUID,
    set[UUID],
]:
    rounds_by_reviewer: dict[UUID, set[UUID]] = {}
    all_round_ids: set[UUID] = set()
    for candidate, _result in rows:
        all_round_ids.add(candidate.assignment_round_id)
        rounds_by_reviewer.setdefault(candidate.respondent_profile_id, set()).add(
            candidate.assignment_round_id
        )

    created_at_values = [candidate.created_at for candidate, _result in rows]
    created_in_one_save_window = bool(created_at_values) and (
        max(created_at_values) - min(created_at_values) <= timedelta(minutes=10)
    )
    split_batch = (
        len(all_round_ids) > 1
        and created_in_one_save_window
        and all(len(round_ids) == 1 for round_ids in rounds_by_reviewer.values())
    )
    selected_rows = (
        rows
        if split_batch
        else [
            row
            for row in rows
            if row[0].assignment_round_id == current_round_id
        ]
    )
    publication_round_id = (
        min(all_round_ids, key=str) if split_batch and all_round_ids else current_round_id
    )

    by_reviewer: dict[UUID, tuple[QuestionnaireAssignment, ScoringResult | None]] = {}
    for row in selected_rows:
        candidate, result = row
        current = by_reviewer.get(candidate.respondent_profile_id)
        if current is None or _aggregate_row_priority(candidate, result) > _aggregate_row_priority(
            *current
        ):
            by_reviewer[candidate.respondent_profile_id] = row
    return list(by_reviewer.values()), publication_round_id, all_round_ids if split_batch else set()


def _aggregate_row_priority(
    assignment: QuestionnaireAssignment,
    result: ScoringResult | None,
) -> tuple[bool, datetime, str]:
    completed = assignment.status in COMPLETED_ASSIGNMENT_STATUSES and result is not None
    return completed, assignment.updated_at or datetime.min.replace(tzinfo=UTC), str(assignment.id)
