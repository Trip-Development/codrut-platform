from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.forms.definitions import get_approved_questionnaire_definition
from codrut.modules.forms.models import QuestionnaireKey
from codrut.modules.scoring.models import ScoringResult
from codrut.modules.scoring.repository import ScoringRepository


class ScoringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ScoringRepository(session)

    async def get_result_by_assignment(self, assignment_id: UUID) -> ScoringResult | None:
        return await self.repository.get_by_assignment(assignment_id)

    async def compute_and_save_score(
        self,
        assignment_id: UUID,
        questionnaire_key: QuestionnaireKey,
        answers: dict[str, Any],
    ) -> ScoringResult:
        try:
            definition = get_approved_questionnaire_definition(questionnaire_key)
        except KeyError as e:
            raise DomainError(
                f"No scoring definition for key: {questionnaire_key.value}",
                code="scoring_not_supported",
            ) from e

        schema = definition.schema
        scoring_meta = schema.get("scoring")
        if not scoring_meta:
            raise DomainError(
                f"Questionnaire {questionnaire_key.value} has no scoring metadata.",
                code="scoring_metadata_missing",
            )

        method = scoring_meta.get("method")
        scores: dict[str, Any] = {}
        primary_result: str | None = None

        if method == "sum_by_group":
            groups = scoring_meta.get("groups", [])
            interpretations = scoring_meta.get("interpretation", [])
            for group in groups:
                group_id = group["id"]
                q_ids = group.get("question_ids", [])
                group_score = sum(int(answers.get(q_id, 0)) for q_id in q_ids)

                interpretation_label = ""
                for rule in interpretations:
                    r_min = rule.get("min")
                    r_max = rule.get("max")
                    if r_min is not None and r_max is not None and r_min <= group_score <= r_max:
                        interpretation_label = rule.get("label", "")
                        break

                scores[group_id] = {
                    "score": group_score,
                    "interpretation": interpretation_label,
                }

            if scores:
                lowest_group = min(scores.keys(), key=lambda k: scores[k]["score"])
                primary_result = lowest_group

        elif method == "sum_statement_scores_by_driver":
            drivers = scoring_meta.get("drivers", [])
            for driver in drivers:
                scores[driver["id"]] = 0

            for section in schema.get("sections", []):
                for question in section.get("questions", []):
                    if question.get("type") == "statement_score_set":
                        q_id = question["id"]
                        for statement in question.get("statements", []):
                            s_id = statement["id"]
                            driver_id = statement.get("scoring", {}).get("driver")
                            if driver_id:
                                answer_key = f"{q_id}:{s_id}"
                                score_val = int(answers.get(answer_key, 0))
                                scores[driver_id] = scores.get(driver_id, 0) + score_val

            if scores:
                highest_driver = max(scores.keys(), key=lambda k: scores[k])
                primary_result = highest_driver

        else:
            raise DomainError(
                f"Unsupported scoring method: {method}",
                code="unsupported_scoring_method",
            )

        existing = await self.repository.get_by_assignment(assignment_id)
        if existing:
            existing.scores = scores
            existing.primary_result = primary_result
            result = existing
        else:
            result = ScoringResult(
                assignment_id=assignment_id,
                scores=scores,
                primary_result=primary_result,
            )
            await self.repository.add_scoring_result(result)

        return result
