from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.assignments.models import AssignmentTargetType, QuestionnaireAssignment
from codrut.modules.companies.models import CompanyProject, ParticipantProfile
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)
from codrut.modules.identity.models import SHADOW_ACCOUNT_PASSWORD_HASH, User


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

    async def get_participant_for_user(self, user_id: UUID) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile).where(ParticipantProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_permanent_participant_for_user(self, user_id: UUID) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile)
            .join(User, User.id == ParticipantProfile.user_id)
            .where(ParticipantProfile.user_id == user_id)
            .where(User.password_hash != SHADOW_ACCOUNT_PASSWORD_HASH)
        )
        return result.scalar_one_or_none()

    async def get_participant_by_profile_id(
        self,
        participant_profile_id: UUID,
    ) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile).where(ParticipantProfile.id == participant_profile_id)
        )
        return result.scalar_one_or_none()

    async def get_pcm_assignment(
        self,
        *,
        company_id: UUID,
        participant_profile_id: UUID,
        questionnaire_key: str,
    ) -> QuestionnaireAssignment | None:
        result = await self.session.execute(
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.respondent_profile_id == participant_profile_id)
            .where(QuestionnaireAssignment.questionnaire_key == questionnaire_key)
            .where(QuestionnaireAssignment.target_type == AssignmentTargetType.self_assessment)
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

    async def get_project_for_assignment(
        self,
        assignment: QuestionnaireAssignment,
    ) -> CompanyProject | None:
        if assignment.project_id is None:
            return None
        result = await self.session.execute(
            select(CompanyProject)
            .where(CompanyProject.id == assignment.project_id)
            .where(CompanyProject.company_id == assignment.company_id)
        )
        return result.scalar_one_or_none()

    async def add_response(self, response: QuestionnaireResponse) -> QuestionnaireResponse:
        self.session.add(response)
        await self.session.flush()
        return response

    async def list_definitions(
        self,
        *,
        active_only: bool = True,
    ) -> list[QuestionnaireDefinition]:
        stmt = select(QuestionnaireDefinition).order_by(
            QuestionnaireDefinition.key,
            QuestionnaireDefinition.version.desc(),
        )
        if active_only:
            stmt = stmt.where(QuestionnaireDefinition.active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_definition(
        self,
        key: str,
        *,
        version: int | None = None,
    ) -> QuestionnaireDefinition | None:
        stmt = select(QuestionnaireDefinition).where(QuestionnaireDefinition.key == key)
        if version is None:
            stmt = stmt.where(QuestionnaireDefinition.active.is_(True)).order_by(
                QuestionnaireDefinition.version.desc()
            )
        else:
            stmt = stmt.where(QuestionnaireDefinition.version == version)
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def get_latest_version(self, key: str) -> int:
        result = await self.session.execute(
            select(func.max(QuestionnaireDefinition.version)).where(
                QuestionnaireDefinition.key == key,
            )
        )
        return result.scalar_one_or_none() or 0

    async def add_definition(
        self,
        definition: QuestionnaireDefinition,
    ) -> QuestionnaireDefinition:
        self.session.add(definition)
        await self.session.flush()
        return definition

    async def has_submitted_responses(
        self,
        key: str,
        version: int,
    ) -> bool:
        result = await self.session.execute(
            select(QuestionnaireResponse.id)
            .where(QuestionnaireResponse.questionnaire_key == key)
            .where(QuestionnaireResponse.questionnaire_version == version)
            .where(QuestionnaireResponse.status == QuestionnaireResponseStatus.submitted)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def deactivate_definitions_for_key(
        self,
        key: str,
        *,
        except_version: int | None = None,
    ) -> None:
        stmt = select(QuestionnaireDefinition).where(QuestionnaireDefinition.key == key)
        result = await self.session.execute(stmt)
        definitions = result.scalars().all()
        for definition in definitions:
            if definition.version != except_version:
                definition.active = False
