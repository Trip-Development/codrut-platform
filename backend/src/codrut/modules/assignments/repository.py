from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.assignments.models import QuestionnaireAssignment, Team, TeamMembership


class AssignmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_team(self, team: Team) -> Team:
        self.session.add(team)
        await self.session.flush()
        return team

    async def get_team(self, company_id: UUID, team_id: UUID) -> Team | None:
        result = await self.session.execute(
            select(Team).where(Team.company_id == company_id).where(Team.id == team_id)
        )
        return result.scalar_one_or_none()

    async def get_team_by_name(self, company_id: UUID, name: str) -> Team | None:
        result = await self.session.execute(
            select(Team).where(Team.company_id == company_id).where(Team.name == name)
        )
        return result.scalar_one_or_none()

    async def list_teams(self, company_id: UUID) -> list[Team]:
        result = await self.session.execute(
            select(Team).where(Team.company_id == company_id).order_by(Team.name)
        )
        return list(result.scalars().all())

    async def add_team_membership(self, membership: TeamMembership) -> TeamMembership:
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def get_team_membership(
        self,
        team_id: UUID,
        participant_profile_id: UUID,
    ) -> TeamMembership | None:
        result = await self.session.execute(
            select(TeamMembership)
            .where(TeamMembership.team_id == team_id)
            .where(TeamMembership.participant_profile_id == participant_profile_id)
        )
        return result.scalar_one_or_none()

    async def list_team_memberships(self, team_id: UUID) -> list[TeamMembership]:
        result = await self.session.execute(
            select(TeamMembership)
            .where(TeamMembership.team_id == team_id)
            .order_by(TeamMembership.created_at)
        )
        return list(result.scalars().all())

    async def add_assignment(self, assignment: QuestionnaireAssignment) -> QuestionnaireAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def get_assignment(
        self,
        company_id: UUID,
        assignment_id: UUID,
    ) -> QuestionnaireAssignment | None:
        result = await self.session.execute(
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.id == assignment_id)
        )
        return result.scalar_one_or_none()

    async def get_matching_assignment(
        self,
        *,
        company_id: UUID,
        project_id: UUID | None,
        respondent_profile_id: UUID,
        questionnaire_key: str,
        target_type: str,
        target_person_id: UUID | None,
        target_team_id: UUID | None,
    ) -> QuestionnaireAssignment | None:
        result = await self.session.execute(
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.project_id == project_id)
            .where(QuestionnaireAssignment.respondent_profile_id == respondent_profile_id)
            .where(QuestionnaireAssignment.questionnaire_key == questionnaire_key)
            .where(QuestionnaireAssignment.target_type == target_type)
            .where(QuestionnaireAssignment.target_person_id == target_person_id)
            .where(QuestionnaireAssignment.target_team_id == target_team_id)
        )
        return result.scalar_one_or_none()

    async def list_assignments(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
    ) -> list[QuestionnaireAssignment]:
        stmt = select(QuestionnaireAssignment).where(
            QuestionnaireAssignment.company_id == company_id
        )
        if project_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.project_id == project_id)
        result = await self.session.execute(
            stmt.order_by(QuestionnaireAssignment.created_at)
        )
        return list(result.scalars().all())
