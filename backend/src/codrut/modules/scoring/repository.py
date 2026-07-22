from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from codrut.modules.assignments.models import QuestionnaireAssignment
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)
from codrut.modules.scoring.models import ScoringResult


class ScoringRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_assignment(self, assignment_id: UUID) -> ScoringResult | None:
        stmt = select(ScoringResult).where(ScoringResult.assignment_id == assignment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_scoring_result(self, result: ScoringResult) -> ScoringResult:
        self.session.add(result)
        await self.session.flush()
        return result

    async def get_questionnaire_definition_schema(
        self,
        key: str,
        version: int,
    ) -> dict | None:
        result = await self.session.execute(
            select(QuestionnaireDefinition.schema)
            .where(QuestionnaireDefinition.key == key)
            .where(QuestionnaireDefinition.version == version)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_company_assignment_results(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
    ) -> list[tuple[QuestionnaireAssignment, ScoringResult | None]]:
        stmt = (
            select(QuestionnaireAssignment, ScoringResult)
            .outerjoin(ScoringResult, ScoringResult.assignment_id == QuestionnaireAssignment.id)
            .where(QuestionnaireAssignment.company_id == company_id)
        )
        if project_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.project_id == project_id)
        if assessment_cycle_id is not None:
            stmt = stmt.where(
                QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id
            )
        result = await self.session.execute(stmt.order_by(QuestionnaireAssignment.created_at))
        return [(assignment, scoring_result) for assignment, scoring_result in result.all()]

    async def list_company_assignment_results_with_definitions(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
    ) -> list[
        tuple[
            QuestionnaireAssignment,
            ScoringResult | None,
            QuestionnaireDefinition | None,
        ]
    ]:
        stmt = (
            select(QuestionnaireAssignment, ScoringResult, QuestionnaireDefinition)
            .outerjoin(ScoringResult, ScoringResult.assignment_id == QuestionnaireAssignment.id)
            .outerjoin(
                QuestionnaireDefinition,
                QuestionnaireDefinition.id == QuestionnaireAssignment.questionnaire_definition_id,
            )
            .where(QuestionnaireAssignment.company_id == company_id)
        )
        if project_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.project_id == project_id)
        if assessment_cycle_id is not None:
            stmt = stmt.where(
                QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id
            )
        result = await self.session.execute(stmt.order_by(QuestionnaireAssignment.created_at))
        return [
            (assignment, scoring_result, definition)
            for assignment, scoring_result, definition in result.all()
        ]

    async def list_company_icare_answer_responses(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
    ) -> list[
        tuple[
            QuestionnaireAssignment,
            QuestionnaireResponse,
            ParticipantProfile,
            ParticipantProfile | None,
            QuestionnaireDefinition,
        ]
    ]:
        respondent = aliased(ParticipantProfile)
        target = aliased(ParticipantProfile)
        stmt = (
            select(
                QuestionnaireAssignment,
                QuestionnaireResponse,
                respondent,
                target,
                QuestionnaireDefinition,
            )
            .join(
                QuestionnaireResponse,
                QuestionnaireResponse.assignment_id == QuestionnaireAssignment.id,
            )
            .join(
                QuestionnaireDefinition,
                QuestionnaireDefinition.id == QuestionnaireAssignment.questionnaire_definition_id,
            )
            .join(respondent, respondent.id == QuestionnaireAssignment.respondent_profile_id)
            .outerjoin(target, target.id == QuestionnaireAssignment.target_person_id)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(
                QuestionnaireAssignment.questionnaire_key.in_(("boss_360", "boss_360_en", "icare"))
            )
            .where(QuestionnaireResponse.status == QuestionnaireResponseStatus.submitted)
            .where(QuestionnaireResponse.questionnaire_version == QuestionnaireDefinition.version)
            .where(
                QuestionnaireDefinition.trainer_visibility_policy["raw_responses"].astext
                == "visible"
            )
        )
        if project_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.project_id == project_id)
        if assessment_cycle_id is not None:
            stmt = stmt.where(
                QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id
            )

        result = await self.session.execute(
            stmt.order_by(
                QuestionnaireResponse.submitted_at,
                QuestionnaireAssignment.created_at,
                respondent.full_name,
            )
        )
        return [
            (assignment, response, respondent_profile, target_profile, definition)
            for assignment, response, respondent_profile, target_profile, definition in result.all()
        ]

    async def list_company_pcm_responses(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
    ) -> list[tuple[QuestionnaireAssignment, QuestionnaireResponse]]:
        stmt = (
            select(QuestionnaireAssignment, QuestionnaireResponse)
            .join(
                QuestionnaireResponse,
                QuestionnaireResponse.assignment_id == QuestionnaireAssignment.id,
            )
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.questionnaire_key.in_(("pcm_base", "phase")))
            .where(QuestionnaireResponse.status == QuestionnaireResponseStatus.submitted)
        )
        if project_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.project_id == project_id)
        if assessment_cycle_id is not None:
            stmt = stmt.where(
                QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id
            )
        result = await self.session.execute(
            stmt.order_by(
                QuestionnaireResponse.submitted_at,
                QuestionnaireAssignment.created_at,
            )
        )
        return list(result.all())

    async def delete_by_assignment(self, assignment_id: UUID) -> None:
        stmt = delete(ScoringResult).where(ScoringResult.assignment_id == assignment_id)
        await self.session.execute(stmt)
