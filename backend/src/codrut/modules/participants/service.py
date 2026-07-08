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
from codrut.modules.forms.definitions.catalog import BOSS_360_DEFINITION
from codrut.modules.identity.schemas import InviteTask
from codrut.modules.identity.service import _invite_task_copy
from codrut.modules.participants.schemas import (
    ParticipantReceivedFeedbackDimension,
    ParticipantReceivedFeedbackSummary,
    ParticipantWorkspaceCard,
    ParticipantWorkspaceResult,
    ParticipantWorkspaceSummary,
)
from codrut.modules.scoring.models import ScoringResult

COMPLETED_ASSIGNMENT_STATUSES = {
    AssignmentStatus.submitted,
    AssignmentStatus.validated,
    AssignmentStatus.scored,
}
RECEIVED_360_QUESTIONNAIRE_KEYS = {"boss_360", "boss_360_en", "icare"}
RECEIVED_360_MINIMUM_COMPLETED = 2
ICARE_DIMENSION_IDS = [
    question["id"]
    for section in BOSS_360_DEFINITION.schema["sections"]
    for question in section.get("questions", [])
]
ICARE_DIMENSION_ID_SET = set(ICARE_DIMENSION_IDS)


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
        scoring_results = await self._get_scoring_results(assignments)
        received_feedback = await self._get_received_feedback_summary(profile)

        tasks = [
            self._assignment_to_task(
                assignment=assignment,
                teams=teams,
                people=people,
            )
            for assignment in assignments
        ]
        results = [
            self._assignment_to_result(
                assignment=assignment,
                result=scoring_results[assignment.id],
                teams=teams,
                people=people,
            )
            for assignment in assignments
            if assignment.status in COMPLETED_ASSIGNMENT_STATUSES
            and assignment.id in scoring_results
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
            pcm_base=profile.pcm_base,
            pcm_phase=profile.pcm_phase,
            company_id=company.id,
            company_name=company.name,
            project_id=project_id,
            project_name=project_name,
            deadline_label=_format_deadline(deadline_at),
            deadline_at=deadline_at,
            tasks=tasks,
            results=results,
            received_feedback=received_feedback,
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

    async def _get_received_feedback_summary(
        self,
        profile: ParticipantProfile,
    ) -> ParticipantReceivedFeedbackSummary | None:
        result = await self.session.execute(
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.company_id == profile.company_id)
            .where(QuestionnaireAssignment.target_type == AssignmentTargetType.person)
            .where(QuestionnaireAssignment.target_person_id == profile.id)
            .where(QuestionnaireAssignment.respondent_profile_id != profile.id)
            .where(QuestionnaireAssignment.questionnaire_key.in_(RECEIVED_360_QUESTIONNAIRE_KEYS))
        )
        received_assignments = list(result.scalars().all())
        if not received_assignments:
            return None

        completed_assignments = [
            assignment
            for assignment in received_assignments
            if assignment.status in COMPLETED_ASSIGNMENT_STATUSES
        ]
        completed_count = len(completed_assignments)
        if completed_count < RECEIVED_360_MINIMUM_COMPLETED:
            return ParticipantReceivedFeedbackSummary(
                completed_count=completed_count,
                minimum_completed=RECEIVED_360_MINIMUM_COMPLETED,
                visible=False,
            )

        completed_assignment_ids = {assignment.id for assignment in completed_assignments}
        scoring_result = await self.session.execute(
            select(ScoringResult).where(ScoringResult.assignment_id.in_(completed_assignment_ids))
        )
        scoring_results = list(scoring_result.scalars().all())
        if len(scoring_results) < RECEIVED_360_MINIMUM_COMPLETED:
            return ParticipantReceivedFeedbackSummary(
                completed_count=completed_count,
                minimum_completed=RECEIVED_360_MINIMUM_COMPLETED,
                visible=False,
            )

        dimension_values: dict[str, list[float]] = {
            dimension_id: [] for dimension_id in ICARE_DIMENSION_IDS
        }
        for scoring in scoring_results:
            for dimension_id, value in scoring.scores.items():
                if dimension_id not in ICARE_DIMENSION_ID_SET:
                    continue
                score = _extract_numeric_score(value)
                if score is None:
                    continue
                dimension_values[dimension_id].append(score)

        visible_dimension_values = {
            dimension_id: values
            for dimension_id, values in dimension_values.items()
            if len(values) >= RECEIVED_360_MINIMUM_COMPLETED
        }
        visible_scores = [
            score
            for values in visible_dimension_values.values()
            for score in values
        ]
        dimensions = [
            ParticipantReceivedFeedbackDimension(
                id=dimension_id,
                average_score=round(sum(values) / len(values), 1),
                completed_count=len(values),
            )
            for dimension_id, values in visible_dimension_values.items()
        ]
        return ParticipantReceivedFeedbackSummary(
            completed_count=completed_count,
            minimum_completed=RECEIVED_360_MINIMUM_COMPLETED,
            visible=bool(dimensions),
            overall_average=(
                round(sum(visible_scores) / len(visible_scores), 1)
                if visible_scores
                else None
            ),
            dimensions=dimensions,
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

    async def _get_scoring_results(
        self,
        assignments: list[QuestionnaireAssignment],
    ) -> dict[UUID, ScoringResult]:
        assignment_ids = {
            assignment.id
            for assignment in assignments
            if assignment.status in COMPLETED_ASSIGNMENT_STATUSES
        }
        if not assignment_ids:
            return {}
        result = await self.session.execute(
            select(ScoringResult).where(ScoringResult.assignment_id.in_(assignment_ids))
        )
        return {
            scoring_result.assignment_id: scoring_result
            for scoring_result in result.scalars().all()
        }

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

    def _assignment_to_result(
        self,
        *,
        assignment: QuestionnaireAssignment,
        result: ScoringResult,
        teams: dict[UUID, Team],
        people: dict[UUID, ParticipantProfile],
    ) -> ParticipantWorkspaceResult:
        task = self._assignment_to_task(assignment=assignment, teams=teams, people=people)
        return ParticipantWorkspaceResult(
            assignment_id=assignment.id,
            questionnaire_key=assignment.questionnaire_key,
            title=task.title,
            target_label=task.targetLabel,
            scores=result.scores,
            primary_result=result.primary_result,
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


def _extract_numeric_score(value: object) -> float | None:
    raw = value.get("score") if isinstance(value, dict) else value
    if isinstance(raw, (int, float)):
        return float(raw)
    return None
