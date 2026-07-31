from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleQuestionnaire,
    AssessmentCycleStatus,
    AssessmentCycleTeamMembership,
    AssignmentStatus,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
    TeamType,
)


class AssignmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_team(self, team: Team) -> Team:
        self.session.add(team)
        await self.session.flush()
        return team

    async def add_assessment_cycle(self, cycle: AssessmentCycle) -> AssessmentCycle:
        self.session.add(cycle)
        await self.session.flush()
        return cycle

    async def add_assessment_cycle_questionnaires(
        self,
        questionnaires: list[AssessmentCycleQuestionnaire],
    ) -> list[AssessmentCycleQuestionnaire]:
        self.session.add_all(questionnaires)
        await self.session.flush()
        return questionnaires

    async def list_assessment_cycles(
        self,
        company_id: UUID,
        project_id: UUID,
    ) -> list[AssessmentCycle]:
        result = await self.session.execute(
            select(AssessmentCycle)
            .where(AssessmentCycle.company_id == company_id)
            .where(AssessmentCycle.project_id == project_id)
            .order_by(AssessmentCycle.sequence.desc())
        )
        return list(result.scalars().all())

    async def get_assessment_cycle(
        self,
        company_id: UUID,
        project_id: UUID,
        assessment_cycle_id: UUID,
        *,
        for_update: bool = False,
    ) -> AssessmentCycle | None:
        statement = (
            select(AssessmentCycle)
            .where(AssessmentCycle.company_id == company_id)
            .where(AssessmentCycle.project_id == project_id)
            .where(AssessmentCycle.id == assessment_cycle_id)
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_open_assessment_cycle(
        self,
        company_id: UUID,
        project_id: UUID,
    ) -> AssessmentCycle | None:
        result = await self.session.execute(
            select(AssessmentCycle)
            .where(AssessmentCycle.company_id == company_id)
            .where(AssessmentCycle.project_id == project_id)
            .where(
                AssessmentCycle.status.in_(
                    (AssessmentCycleStatus.draft, AssessmentCycleStatus.active)
                )
            )
            .order_by(AssessmentCycle.sequence.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_assessment_cycle(
        self,
        company_id: UUID,
        project_id: UUID,
    ) -> AssessmentCycle | None:
        result = await self.session.execute(
            select(AssessmentCycle)
            .where(AssessmentCycle.company_id == company_id)
            .where(AssessmentCycle.project_id == project_id)
            .order_by(AssessmentCycle.sequence.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def next_assessment_cycle_sequence(
        self,
        company_id: UUID,
        project_id: UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.max(AssessmentCycle.sequence))
            .where(AssessmentCycle.company_id == company_id)
            .where(AssessmentCycle.project_id == project_id)
        )
        return int(result.scalar_one_or_none() or 0) + 1

    async def list_assessment_cycle_questionnaires(
        self,
        assessment_cycle_id: UUID,
    ) -> list[AssessmentCycleQuestionnaire]:
        result = await self.session.execute(
            select(AssessmentCycleQuestionnaire)
            .where(AssessmentCycleQuestionnaire.assessment_cycle_id == assessment_cycle_id)
            .order_by(
                AssessmentCycleQuestionnaire.display_order,
                AssessmentCycleQuestionnaire.questionnaire_key,
            )
        )
        return list(result.scalars().all())

    async def delete_assessment_cycle(self, cycle: AssessmentCycle) -> None:
        await self.session.execute(
            delete(QuestionnaireAssignment).where(
                QuestionnaireAssignment.assessment_cycle_id == cycle.id
            )
        )
        await self.session.delete(cycle)
        await self.session.flush()

    async def count_unfinished_cycle_assignments(self, assessment_cycle_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(QuestionnaireAssignment.id))
            .where(QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id)
            .where(
                QuestionnaireAssignment.status.not_in(
                    (
                        AssignmentStatus.submitted,
                        AssignmentStatus.validated,
                        AssignmentStatus.scored,
                        AssignmentStatus.cancelled,
                    )
                )
            )
        )
        return int(result.scalar_one())

    async def cancel_unfinished_cycle_assignments(
        self, assessment_cycle_id: UUID
    ) -> list[QuestionnaireAssignment]:
        result = await self.session.execute(
            select(QuestionnaireAssignment).where(
                QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id
            )
        )
        assignments = list(result.scalars().all())
        cancelled: list[QuestionnaireAssignment] = []
        for assignment in assignments:
            if assignment.status in {
                AssignmentStatus.submitted,
                AssignmentStatus.validated,
                AssignmentStatus.scored,
                AssignmentStatus.cancelled,
            }:
                continue
            assignment.status = AssignmentStatus.cancelled
            cancelled.append(assignment)
        await self.session.flush()
        return cancelled

    async def synchronize_cycle_assignment_deadlines(
        self,
        assessment_cycle_id: UUID,
        due_at: datetime | None,
    ) -> None:
        await self.session.execute(
            update(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id)
            .values(due_at=due_at)
        )

    async def list_cycle_team_memberships(
        self,
        assessment_cycle_id: UUID,
        team_id: UUID,
    ) -> list[AssessmentCycleTeamMembership]:
        result = await self.session.execute(
            select(AssessmentCycleTeamMembership)
            .where(AssessmentCycleTeamMembership.assessment_cycle_id == assessment_cycle_id)
            .where(AssessmentCycleTeamMembership.team_id == team_id)
            .order_by(AssessmentCycleTeamMembership.created_at)
        )
        return list(result.scalars().all())

    async def list_cycle_leadership_participant_ids(
        self,
        assessment_cycle_id: UUID,
    ) -> set[UUID]:
        result = await self.session.execute(
            select(AssessmentCycleTeamMembership.participant_profile_id)
            .join(Team, Team.id == AssessmentCycleTeamMembership.team_id)
            .where(
                AssessmentCycleTeamMembership.assessment_cycle_id
                == assessment_cycle_id,
                Team.type == TeamType.leadership,
            )
        )
        return set(result.scalars().all())

    async def add_cycle_team_memberships(
        self,
        memberships: list[AssessmentCycleTeamMembership],
    ) -> list[AssessmentCycleTeamMembership]:
        self.session.add_all(memberships)
        await self.session.flush()
        return memberships

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

    async def get_team_membership_by_id(
        self,
        team_id: UUID,
        membership_id: UUID,
    ) -> TeamMembership | None:
        result = await self.session.execute(
            select(TeamMembership)
            .where(TeamMembership.team_id == team_id)
            .where(TeamMembership.id == membership_id)
        )
        return result.scalar_one_or_none()

    async def delete_team_membership(self, membership: TeamMembership) -> None:
        await self.session.delete(membership)
        await self.session.flush()

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
        *,
        for_update: bool = False,
    ) -> QuestionnaireAssignment | None:
        statement = (
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.id == assignment_id)
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
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
        assessment_cycle_id: UUID | None = None,
    ) -> QuestionnaireAssignment | None:
        statement = (
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.project_id == project_id)
            .where(QuestionnaireAssignment.respondent_profile_id == respondent_profile_id)
            .where(QuestionnaireAssignment.questionnaire_key == questionnaire_key)
            .where(QuestionnaireAssignment.target_type == target_type)
            .where(QuestionnaireAssignment.target_person_id == target_person_id)
            .where(QuestionnaireAssignment.target_team_id == target_team_id)
        )
        if assessment_cycle_id is not None:
            statement = statement.where(
                QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id
            )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_assignments(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
    ) -> list[QuestionnaireAssignment]:
        stmt = select(QuestionnaireAssignment).where(
            QuestionnaireAssignment.company_id == company_id
        )
        if project_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.project_id == project_id)
        if assessment_cycle_id is not None:
            stmt = stmt.where(QuestionnaireAssignment.assessment_cycle_id == assessment_cycle_id)
        result = await self.session.execute(stmt.order_by(QuestionnaireAssignment.created_at))
        return list(result.scalars().all())
