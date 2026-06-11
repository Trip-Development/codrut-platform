from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.assignments.models import QuestionnaireAssignment
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

    async def list_company_assignment_results(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
    ) -> list[tuple[QuestionnaireAssignment, ScoringResult | None]]:
        stmt = (
            select(QuestionnaireAssignment, ScoringResult)
            .outerjoin(ScoringResult, ScoringResult.assignment_id == QuestionnaireAssignment.id)
            .where(QuestionnaireAssignment.company_id == company_id)
        )
        if project_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.project_id == project_id)
        result = await self.session.execute(stmt.order_by(QuestionnaireAssignment.created_at))
        return [(assignment, scoring_result) for assignment, scoring_result in result.all()]

    async def delete_by_assignment(self, assignment_id: UUID) -> None:
        stmt = delete(ScoringResult).where(ScoringResult.assignment_id == assignment_id)
        await self.session.execute(stmt)
