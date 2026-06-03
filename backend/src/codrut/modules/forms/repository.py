from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.assignments.models import QuestionnaireAssignment
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.forms.models import QuestionnaireResponse


class FormsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_assignment_for_user(
        self,
        assignment_id: UUID,
        user_id: UUID,
    ) -> QuestionnaireAssignment | None:
        result = await self.session.execute(
            select(QuestionnaireAssignment)
            .join(
                ParticipantProfile,
                ParticipantProfile.id == QuestionnaireAssignment.respondent_profile_id,
            )
            .where(QuestionnaireAssignment.id == assignment_id)
            .where(ParticipantProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_response_by_assignment(
        self,
        assignment_id: UUID,
    ) -> QuestionnaireResponse | None:
        result = await self.session.execute(
            select(QuestionnaireResponse).where(
                QuestionnaireResponse.assignment_id == assignment_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_response(self, response: QuestionnaireResponse) -> QuestionnaireResponse:
        self.session.add(response)
        await self.session.flush()
        return response
