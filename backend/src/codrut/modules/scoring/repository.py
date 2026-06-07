from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def delete_by_assignment(self, assignment_id: UUID) -> None:
        stmt = delete(ScoringResult).where(ScoringResult.assignment_id == assignment_id)
        await self.session.execute(stmt)
