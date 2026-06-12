from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
)
from codrut.modules.companies.anonymous import new_anonymous_name
from codrut.modules.companies.models import Company, CompanyProject, ParticipantProfile
from codrut.modules.identity.schemas import InviteTask
from codrut.modules.identity.service import _invite_task_copy
from codrut.modules.participants.schemas import (
    ParticipantWorkspaceCard,
    ParticipantWorkspaceSummary,
)


class ParticipantWorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_workspace_summary(self, user_id: UUID) -> ParticipantWorkspaceSummary:
        profile, company = await self._get_profile_and_company(user_id)
        if not profile.anonymous_name:
            profile.anonymous_name = new_anonymous_name()
            await self.session.flush()
        assignments = await self._list_assignments(profile)
        projects = await self._get_projects(assignments)
        teams = await self._get_teams(assignments)
        people = await self._get_people(assignments, profile.company_id)

        tasks = [
            self._assignment_to_task(
                assignment=assignment,
                teams=teams,
                people=people,
            )
            for assignment in assignments
        ]
        project_id, project_name = self._workspace_project(company, assignments, projects)
        deadline_at = self._workspace_deadline(assignments, projects)
        completed = sum(1 for task in tasks if task.status == "completed")
        pending = len(tasks) - completed

        return ParticipantWorkspaceSummary(
            participant_profile_id=profile.id,
            participant_full_name=profile.full_name,
            participant_email=profile.email,
            anonymous_name=profile.anonymous_name,
            company_id=company.id,
            company_name=company.name,
            project_id=project_id,
            project_name=project_name,
            deadline_label=_format_deadline(deadline_at),
            deadline_at=deadline_at,
            pcm_base=profile.pcm_base,
            pcm_phase=profile.pcm_phase,
            tasks=tasks,
            cards=[
                ParticipantWorkspaceCard(
                    title="De completat",
                    description=f"{pending} sarcini active",
                    meta="Acum",
                ),
                ParticipantWorkspaceCard(
                    title="Finalizate",
                    description=f"{completed}/{len(tasks)} sarcini salvate",
                    meta="Progres",
                ),
                ParticipantWorkspaceCard(
                    title="Companie",
                    description=company.name,
                    meta="Context",
                ),
            ],
            empty_state=ParticipantWorkspaceCard(
                title="Nu ai sarcini active",
                description=(
                    "Când trainerul salvează alocări pentru tine, chestionarele apar aici "
                    "automat."
                ),
            ),
        )

    async def _get_profile_and_company(self, user_id: UUID) -> tuple[ParticipantProfile, Company]:
        result = await self.session.execute(
            select(ParticipantProfile, Company)
            .join(Company, Company.id == ParticipantProfile.company_id)
            .where(ParticipantProfile.user_id == user_id)
        )
        row = result.first()
        if row is None:
            raise DomainError(
                "Participant profile not found for this account.",
                code="participant_profile_not_found",
            )
        return row[0], row[1]

    async def _list_assignments(
        self,
        profile: ParticipantProfile,
    ) -> list[QuestionnaireAssignment]:
        result = await self.session.execute(
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.company_id == profile.company_id)
            .where(QuestionnaireAssignment.respondent_profile_id == profile.id)
            .order_by(
                QuestionnaireAssignment.due_at.asc().nulls_last(),
                QuestionnaireAssignment.created_at.asc(),
            )
        )
        return list(result.scalars().all())

    async def _get_projects(
        self,
        assignments: list[QuestionnaireAssignment],
    ) -> dict[UUID, CompanyProject]:
        project_ids = {assignment.project_id for assignment in assignments if assignment.project_id}
        if not project_ids:
            return {}
        result = await self.session.execute(
            select(CompanyProject).where(CompanyProject.id.in_(project_ids))
        )
        return {project.id: project for project in result.scalars().all()}

    async def _get_teams(self, assignments: list[QuestionnaireAssignment]) -> dict[UUID, Team]:
        team_ids = {
            assignment.target_team_id
            for assignment in assignments
            if assignment.target_type == AssignmentTargetType.team and assignment.target_team_id
        }
        if not team_ids:
            return {}
        result = await self.session.execute(select(Team).where(Team.id.in_(team_ids)))
        return {team.id: team for team in result.scalars().all()}

    async def _get_people(
        self,
        assignments: list[QuestionnaireAssignment],
        company_id: UUID,
    ) -> dict[UUID, ParticipantProfile]:
        person_ids = {
            assignment.target_person_id
            for assignment in assignments
            if assignment.target_type == AssignmentTargetType.person and assignment.target_person_id
        }
        if not person_ids:
            return {}
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .where(ParticipantProfile.id.in_(person_ids))
        )
        return {profile.id: profile for profile in result.scalars().all()}

    def _assignment_to_task(
        self,
        *,
        assignment: QuestionnaireAssignment,
        teams: dict[UUID, Team],
        people: dict[UUID, ParticipantProfile],
    ) -> InviteTask:
        title, detail, estimated_minutes = _invite_task_copy(assignment.questionnaire_key)
        target_label = "Autoevaluare"
        if assignment.target_type == AssignmentTargetType.team and assignment.target_team_id:
            team = teams.get(assignment.target_team_id)
            target_label = team.name if team is not None else "Echipă"
        elif assignment.target_type == AssignmentTargetType.person and assignment.target_person_id:
            person = people.get(assignment.target_person_id)
            target_label = person.full_name if person is not None else "Persoană evaluată"

        return InviteTask(
            id=str(assignment.id),
            title=title,
            status=_task_status(assignment.status),
            detail=detail,
            href=(
                f"/participant/questionnaires/{assignment.questionnaire_key}"
                f"?assignmentId={assignment.id}"
            ),
            assignmentId=str(assignment.id),
            targetLabel=target_label,
            estimatedMinutes=estimated_minutes,
            questionnaireKey=assignment.questionnaire_key,
        )

    def _workspace_project(
        self,
        company: Company,
        assignments: list[QuestionnaireAssignment],
        projects: dict[UUID, CompanyProject],
    ) -> tuple[UUID | None, str]:
        project_ids = [
            assignment.project_id
            for assignment in assignments
            if assignment.project_id is not None and assignment.project_id in projects
        ]
        unique_project_ids = list(dict.fromkeys(project_ids))
        if len(unique_project_ids) == 1:
            project_id = unique_project_ids[0]
            return project_id, projects[project_id].name
        if len(unique_project_ids) > 1:
            return None, "Toate proiectele active"
        return None, company.name

    def _workspace_deadline(
        self,
        assignments: list[QuestionnaireAssignment],
        projects: dict[UUID, CompanyProject],
    ) -> datetime | None:
        candidates = [
            assignment.due_at
            for assignment in assignments
            if assignment.due_at is not None
        ]
        candidates.extend(
            project.due_at for project in projects.values() if project.due_at is not None
        )
        if not candidates:
            return None
        return min(candidates)


def _task_status(status: AssignmentStatus) -> str:
    if status in {AssignmentStatus.submitted, AssignmentStatus.validated, AssignmentStatus.scored}:
        return "completed"
    if status == AssignmentStatus.started:
        return "in_progress"
    return "not_started"


def _format_deadline(value: datetime | None) -> str:
    if value is None:
        return "finalul evaluării"
    return value.strftime("%d.%m.%Y")
