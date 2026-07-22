from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, select, update
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


def required_feedback_count(
    *,
    eligible_count: int,
    minimum_completed: int = 2,
    target_completed: int = 3,
) -> int:
    minimum = max(1, minimum_completed)
    target = max(minimum, target_completed)
    return max(minimum, min(target, eligible_count))


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
        publication_key = _aggregate_publication_key(assignment)
        feedback_policy = definition.feedback_policy if definition is not None else {}
        if definition is None or feedback_policy.get("publication", "none") != "aggregate":
            await self._revoke(publication_key)
            return

        statement = (
            select(QuestionnaireAssignment, ScoringResult)
            .outerjoin(ScoringResult, ScoringResult.assignment_id == QuestionnaireAssignment.id)
            .where(QuestionnaireAssignment.company_id == assignment.company_id)
            .where(QuestionnaireAssignment.assignment_round_id == assignment.assignment_round_id)
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
            statement.where(QuestionnaireAssignment.questionnaire_definition_id.is_(None))
            if assignment.questionnaire_definition_id is None
            else statement.where(
                QuestionnaireAssignment.questionnaire_definition_id
                == assignment.questionnaire_definition_id
            )
        )
        rows = list((await self.session.execute(statement)).all())
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
            },
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
    ) -> None:
        now = datetime.now(UTC)
        values = {
            "publication_key": publication_key,
            "participant_profile_id": participant_profile_id,
            "company_id": assignment.company_id,
            "project_id": assignment.project_id,
            "assignment_round_id": assignment.assignment_round_id,
            "questionnaire_definition_id": assignment.questionnaire_definition_id,
            "questionnaire_key": assignment.questionnaire_key,
            "source_assignment_id": source_assignment_id,
            "kind": kind,
            "source_count": source_count,
            "definition_checksum": definition.content_checksum,
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
    if definition is None or not isinstance(definition.feedback_policy, dict):
        return {}
    policy = definition.feedback_policy.get("participant_results")
    return policy if isinstance(policy, dict) else {}


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


def _aggregate_publication_key(assignment: QuestionnaireAssignment) -> str:
    return ":".join(
        (
            "aggregate-360",
            str(assignment.target_person_id),
            str(assignment.project_id or "none"),
            str(assignment.assignment_round_id),
            str(assignment.questionnaire_definition_id or assignment.questionnaire_key),
        )
    )
