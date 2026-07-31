from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleStatus,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
)
from codrut.modules.assignments.team_snapshot import (
    load_assessment_cycle_team_snapshot,
)
from codrut.modules.companies.anonymous import allocate_anonymous_name
from codrut.modules.companies.hierarchy import (
    HierarchyParticipant,
    build_organization_hierarchy,
)
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)
from codrut.modules.identity.schemas import InviteTask
from codrut.modules.identity.service import _invite_task_copy
from codrut.modules.participants.schemas import (
    ParticipantQuestionnaireProject,
    ParticipantQuestionnaireTask,
    ParticipantReceivedFeedbackDimension,
    ParticipantReceivedFeedbackSummary,
    ParticipantWorkspaceCard,
    ParticipantWorkspaceContext,
    ParticipantWorkspaceCycle,
    ParticipantWorkspaceProject,
    ParticipantWorkspaceResult,
    ParticipantWorkspaceSummary,
)
from codrut.modules.scoring.models import (
    ResultPublication,
    ResultPublicationKind,
    ScoringResult,
)
from codrut.modules.scoring.publication import definition_publication_checksum
from codrut.modules.scoring.scale import derive_definition_score_scale

COMPLETED_ASSIGNMENT_STATUSES = {
    AssignmentStatus.submitted,
    AssignmentStatus.validated,
    AssignmentStatus.scored,
}
RECEIVED_360_QUESTIONNAIRE_KEYS = {"boss_360", "boss_360_en", "icare"}
RECEIVED_360_MINIMUM_COMPLETED = 2


class ParticipantWorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _anonymous_name_exists(self, anonymous_name: str) -> bool:
        result = await self.session.execute(
            select(
                exists().where(
                    ParticipantProfile.anonymous_name == anonymous_name
                )
            )
        )
        return bool(result.scalar())

    async def get_workspace_summary(
        self,
        user_id: UUID,
        *,
        participant_profile_id: UUID | None = None,
        project_id: UUID | None = None,
        cycle_id: UUID | None = None,
        allowed_assignment_ids: tuple[UUID, ...] | None = None,
        scoped_project_id: UUID | None = None,
    ) -> ParticipantWorkspaceSummary:
        profile_rows = await self._list_profiles_and_companies(user_id)
        contexts = await self._get_authorized_contexts(profile_rows)
        questionnaire_projects = await self._get_questionnaire_projects(
            profile_rows,
            contexts,
            allowed_assignment_ids=allowed_assignment_ids,
            scoped_project_id=scoped_project_id,
        )
        profile, company, project_id, cycle_id = await self._resolve_workspace_context(
            profile_rows,
            contexts,
            participant_profile_id=participant_profile_id,
            project_id=project_id,
            cycle_id=cycle_id,
            allowed_assignment_ids=allowed_assignment_ids,
            scoped_project_id=scoped_project_id,
        )
        if profile is None or company is None:
            return ParticipantWorkspaceSummary(
                context_selection_required=True,
                contexts=contexts,
                questionnaire_projects=questionnaire_projects,
            )
        if not profile.anonymous_name:
            profile.anonymous_name = await allocate_anonymous_name(
                self._anonymous_name_exists
            )
            await self.session.flush()
        visible_cycle_ids = {
            cycle.id
            for cycle in self._selected_cycles(contexts, profile.id, project_id)
        }
        selected_project = next(
            (
                project
                for context in contexts
                if context.participant_profile_id == profile.id
                for project in context.projects
                if project.id == project_id
            ),
            None,
        )
        history_only = bool(
            selected_project is not None
            and selected_project.history_bucket == "history"
        )
        assignments = await self._list_assignments(
            profile,
            project_id=project_id,
            cycle_id=cycle_id,
            allowed_assignment_ids=allowed_assignment_ids,
            visible_cycle_ids=visible_cycle_ids,
            history_only=history_only,
        )
        pcm_base, pcm_phase = (
            await self._get_cycle_pcm_values(assignments)
            if cycle_id is not None
            else (profile.pcm_base, profile.pcm_phase)
        )
        projects = await self._get_projects(assignments)
        teams = await self._get_teams(assignments)
        people = await self._get_people(assignments, profile.company_id)
        scoring_results = await self._get_scoring_results(assignments)
        result_definitions = await self._get_result_definitions(assignments)
        individual_publications = await self._get_active_individual_publications(
            profile,
            assignments,
        )
        allowed_project_ids: set[UUID | None] | None = (
            {project_id} if project_id is not None else None
        )
        if allowed_assignment_ids is not None:
            allowed_project_ids = {assignment.project_id for assignment in assignments}
            if scoped_project_id is not None:
                allowed_project_ids = {scoped_project_id}
        received_feedback_groups = await self._get_received_feedback_summaries(
            profile,
            allowed_project_ids=allowed_project_ids,
            cycle_id=cycle_id,
        )
        received_feedback = (
            received_feedback_groups[0] if len(received_feedback_groups) == 1 else None
        )

        tasks = [
            self._assignment_to_task(
                assignment=assignment,
                teams=teams,
                people=people,
                projects=projects,
            )
            for assignment in assignments
        ]
        results: list[ParticipantWorkspaceResult] = []
        for assignment in assignments:
            if (
                assignment.status not in COMPLETED_ASSIGNMENT_STATUSES
                or assignment.id not in scoring_results
            ):
                continue
            workspace_result = self._assignment_to_result(
                assignment=assignment,
                result=scoring_results[assignment.id],
                definition=result_definitions.get(assignment.id),
                publication=individual_publications.get(assignment.id),
                teams=teams,
                people=people,
                projects=projects,
            )
            if workspace_result is not None:
                results.append(workspace_result)
        workspace_project_id, project_name = self._workspace_project(
            company,
            assignments,
            projects,
        )
        if project_id is not None:
            workspace_project_id = project_id
            project = projects.get(project_id)
            if project is not None:
                project_name = project.name
            elif selected_project is not None:
                project_name = selected_project.name
        deadline_at = self._workspace_deadline(assignments, projects)
        completed = sum(1 for task in tasks if task.status == "completed")
        pending = len(tasks) - completed

        return ParticipantWorkspaceSummary(
            participant_profile_id=profile.id,
            participant_full_name=profile.full_name,
            participant_email=profile.email,
            anonymous_name=profile.anonymous_name,
            pcm_base=pcm_base,
            pcm_phase=pcm_phase,
            company_id=company.id,
            company_name=company.name,
            project_id=workspace_project_id,
            project_name=project_name,
            assessment_cycle_id=cycle_id,
            contexts=contexts,
            cycles=self._selected_cycles(contexts, profile.id, workspace_project_id),
            projects=self._workspace_projects(
                assignments,
                projects,
                cycles=self._selected_cycles(contexts, profile.id, None),
            ),
            questionnaire_projects=questionnaire_projects,
            deadline_label=_format_deadline(deadline_at),
            deadline_at=deadline_at,
            tasks=tasks,
            results=results,
            received_feedback=received_feedback,
            received_feedback_groups=received_feedback_groups,
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
                    "Când trainerul salvează alocări pentru tine, chestionarele apar aici automat."
                ),
            ),
        )

    async def _get_questionnaire_projects(
        self,
        profile_rows: list[tuple[ParticipantProfile, Company]],
        contexts: list[ParticipantWorkspaceContext],
        *,
        allowed_assignment_ids: tuple[UUID, ...] | None,
        scoped_project_id: UUID | None,
    ) -> list[ParticipantQuestionnaireProject]:
        profiles_by_id = {
            profile.id: (profile, company)
            for profile, company in profile_rows
        }
        visible_project_ids_by_profile = {
            context.participant_profile_id: {
                project.id for project in context.projects
            }
            for context in contexts
        }
        profile_ids = set(profiles_by_id)
        if not profile_ids:
            return []

        statement = (
            select(QuestionnaireAssignment)
            .outerjoin(
                AssessmentCycle,
                AssessmentCycle.id
                == QuestionnaireAssignment.assessment_cycle_id,
            )
            .where(
                QuestionnaireAssignment.respondent_profile_id.in_(profile_ids)
            )
            .where(
                QuestionnaireAssignment.status != AssignmentStatus.cancelled
            )
            .where(
                or_(
                    QuestionnaireAssignment.assessment_cycle_id.is_(None),
                    AssessmentCycle.status != AssessmentCycleStatus.draft,
                )
            )
            .order_by(
                QuestionnaireAssignment.due_at.asc().nulls_last(),
                QuestionnaireAssignment.created_at.asc(),
            )
        )
        if allowed_assignment_ids is not None:
            if not allowed_assignment_ids:
                return []
            statement = statement.where(
                QuestionnaireAssignment.id.in_(allowed_assignment_ids)
            )
        if scoped_project_id is not None:
            statement = statement.where(
                QuestionnaireAssignment.project_id == scoped_project_id
            )
        assignment_result = await self.session.execute(statement)
        assignments = [
            assignment
            for assignment in assignment_result.scalars().all()
            if assignment.project_id
            in visible_project_ids_by_profile.get(
                assignment.respondent_profile_id,
                set(),
            )
        ]
        if not assignments:
            return []

        projects = await self._get_projects(assignments)
        teams = await self._get_teams(assignments)
        company_ids = {
            company.id for _profile, company in profile_rows
        }
        people: dict[UUID, ParticipantProfile] = {}
        for company_id in company_ids:
            people.update(await self._get_people(assignments, company_id))

        cycle_ids = {
            assignment.assessment_cycle_id
            for assignment in assignments
            if assignment.assessment_cycle_id is not None
        }
        cycles: dict[UUID, AssessmentCycle] = {}
        if cycle_ids:
            cycle_result = await self.session.execute(
                select(AssessmentCycle).where(
                    AssessmentCycle.id.in_(cycle_ids)
                )
            )
            cycles = {
                cycle.id: cycle for cycle in cycle_result.scalars().all()
            }

        catalog: list[ParticipantQuestionnaireProject] = []
        for context in contexts:
            for workspace_project in context.projects:
                project_assignments = [
                    assignment
                    for assignment in assignments
                    if assignment.respondent_profile_id
                    == context.participant_profile_id
                    and assignment.project_id == workspace_project.id
                ]
                if not project_assignments:
                    continue

                questionnaires: list[ParticipantQuestionnaireTask] = []
                for assignment in project_assignments:
                    task = self._assignment_to_task(
                        assignment=assignment,
                        teams=teams,
                        people=people,
                        projects=projects,
                    )
                    cycle = (
                        cycles.get(assignment.assessment_cycle_id)
                        if assignment.assessment_cycle_id is not None
                        else None
                    )
                    deadline_at = assignment.due_at
                    if deadline_at is None:
                        project = projects.get(workspace_project.id)
                        deadline_at = project.due_at if project is not None else None
                    task_payload = task.model_dump()
                    task_payload.update(
                        cycleName=cycle.name if cycle is not None else None,
                        cycleSequence=(
                            cycle.sequence if cycle is not None else None
                        ),
                        deadlineLabel=_format_deadline(deadline_at),
                        dueAt=deadline_at,
                    )
                    questionnaires.append(
                        ParticipantQuestionnaireTask.model_validate(task_payload)
                    )

                completed_count = sum(
                    questionnaire.status == "completed"
                    for questionnaire in questionnaires
                )
                catalog.append(
                    ParticipantQuestionnaireProject(
                        id=workspace_project.id,
                        participant_profile_id=context.participant_profile_id,
                        company_name=context.company_name,
                        name=workspace_project.name,
                        status=workspace_project.status,
                        history_bucket=workspace_project.history_bucket,
                        deadline_label=workspace_project.deadline_label,
                        completed_count=completed_count,
                        total_count=len(questionnaires),
                        questionnaires=questionnaires,
                    )
                )

        return sorted(
            catalog,
            key=lambda project: (
                project.completed_count == project.total_count,
                project.history_bucket == "history",
                project.name.casefold(),
                str(project.id),
            ),
        )

    async def _get_received_feedback_summaries(
        self,
        profile: ParticipantProfile,
        *,
        allowed_project_ids: set[UUID | None] | None,
        cycle_id: UUID | None,
    ) -> list[ParticipantReceivedFeedbackSummary]:
        statement = (
            select(ResultPublication)
            .where(ResultPublication.company_id == profile.company_id)
            .where(ResultPublication.participant_profile_id == profile.id)
            .where(ResultPublication.kind == ResultPublicationKind.aggregate_360)
            .where(ResultPublication.revoked_at.is_(None))
            .where(ResultPublication.questionnaire_key.in_(RECEIVED_360_QUESTIONNAIRE_KEYS))
            .order_by(
                ResultPublication.project_id.asc().nulls_last(),
                ResultPublication.published_at.asc(),
            )
        )
        if allowed_project_ids is not None:
            conditions = []
            concrete_project_ids = {
                project_id for project_id in allowed_project_ids if project_id is not None
            }
            if concrete_project_ids:
                conditions.append(ResultPublication.project_id.in_(concrete_project_ids))
            if None in allowed_project_ids:
                conditions.append(ResultPublication.project_id.is_(None))
            if not conditions:
                return []
            statement = statement.where(or_(*conditions))
        if cycle_id is not None:
            statement = statement.where(ResultPublication.assessment_cycle_id == cycle_id)

        result = await self.session.execute(statement)
        publications = list(result.scalars().all())
        if not publications:
            return []

        project_ids = {
            publication.project_id for publication in publications if publication.project_id
        }
        projects: dict[UUID, CompanyProject] = {}
        if project_ids:
            project_result = await self.session.execute(
                select(CompanyProject).where(CompanyProject.id.in_(project_ids))
            )
            projects = {project.id: project for project in project_result.scalars().all()}

        summaries: list[ParticipantReceivedFeedbackSummary] = []
        for publication in publications:
            definition = await self._definition_for_publication(publication)
            if definition is None:
                continue
            assignments = await self._received_assignments_for_publication(
                profile,
                publication,
            )
            cohort_summaries = await self._build_received_feedback_summaries(
                assignments,
                profile=profile,
                publication=publication,
                definition=definition,
                project_id=publication.project_id,
                project_name=(
                    projects[publication.project_id].name
                    if publication.project_id is not None
                    and publication.project_id in projects
                    else "Fără proiect"
                ),
            )
            summaries.extend(cohort_summaries)
        return summaries

    async def _build_received_feedback_summaries(
        self,
        received_assignments: list[QuestionnaireAssignment],
        *,
        profile: ParticipantProfile,
        publication: ResultPublication,
        definition: QuestionnaireDefinition,
        project_id: UUID | None,
        project_name: str,
    ) -> list[ParticipantReceivedFeedbackSummary]:
        policy = publication.policy_snapshot
        if not isinstance(policy, dict) or policy.get("publication") != "aggregate":
            return []
        minimum_completed = RECEIVED_360_MINIMUM_COMPLETED
        allowed_dimensions = {
            str(dimension_id)
            for dimension_id in policy.get("dimension_ids", [])
            if isinstance(dimension_id, str) and dimension_id.strip()
        }
        labels = _definition_score_labels(definition)
        questionnaire_title = definition.title
        score_scale = _definition_score_scale(
            definition,
            dimension_ids=allowed_dimensions,
        )
        if score_scale is None:
            return []
        score_unit, scale_min, scale_max = score_scale

        completed_assignments = [
            assignment
            for assignment in received_assignments
            if assignment.status in COMPLETED_ASSIGNMENT_STATUSES
        ]
        if len(completed_assignments) != publication.source_count:
            return []

        cohort_assignments = await self._split_received_feedback_cohorts(
            profile,
            publication.project_id,
            completed_assignments,
            assessment_cycle_id=publication.assessment_cycle_id,
        )
        summaries: list[ParticipantReceivedFeedbackSummary] = []
        for cohort in ("direct_team", "leadership_peers"):
            assignments = cohort_assignments[cohort]
            latest_by_respondent = {
                assignment.respondent_profile_id: assignment for assignment in assignments
            }
            distinct_assignments = list(latest_by_respondent.values())
            summary = await self._build_received_feedback_cohort_summary(
                distinct_assignments,
                publication=publication,
                project_id=project_id,
                project_name=project_name,
                cohort=cohort,
                minimum_completed=minimum_completed,
                allowed_dimensions=allowed_dimensions,
                labels=labels,
                questionnaire_title=questionnaire_title,
                score_unit=score_unit,
                scale_min=scale_min,
                scale_max=scale_max,
            )
            if summary is not None:
                summaries.append(summary)
        return summaries

    async def _build_received_feedback_cohort_summary(
        self,
        completed_assignments: list[QuestionnaireAssignment],
        *,
        publication: ResultPublication,
        project_id: UUID | None,
        project_name: str,
        cohort: str,
        minimum_completed: int,
        allowed_dimensions: set[str],
        labels: dict[str, str],
        questionnaire_title: str,
        score_unit: str,
        scale_min: float,
        scale_max: float,
    ) -> ParticipantReceivedFeedbackSummary | None:
        if not completed_assignments:
            return None
        completed_assignment_ids = {assignment.id for assignment in completed_assignments}
        scoring_result = await self.session.execute(
            select(ScoringResult).where(ScoringResult.assignment_id.in_(completed_assignment_ids))
        )
        scoring_results = list(scoring_result.scalars().all())
        completed_count = len(completed_assignments)
        scoring_unavailable = len(scoring_results) != completed_count
        visible = completed_count >= minimum_completed

        dimension_values: dict[str, list[float]] = {}
        for scoring in scoring_results if visible and not scoring_unavailable else []:
            for dimension_id, value in scoring.scores.items():
                if dimension_id not in allowed_dimensions:
                    continue
                score = _extract_numeric_score(value)
                if score is None:
                    continue
                dimension_values.setdefault(dimension_id, []).append(score)

        visible_dimension_values = {
            dimension_id: values
            for dimension_id, values in dimension_values.items()
            if len(values) >= minimum_completed
        }
        visible_scores = [score for values in visible_dimension_values.values() for score in values]
        dimensions = [
            ParticipantReceivedFeedbackDimension(
                id=dimension_id,
                label=labels.get(dimension_id, _prettify_score_key(dimension_id)),
                average_score=round(sum(values) / len(values), 1),
                completed_count=len(values),
            )
            for dimension_id, values in visible_dimension_values.items()
        ]
        unavailable_reason = None
        if scoring_unavailable:
            unavailable_reason = "scoring_unavailable"
        elif not visible:
            unavailable_reason = "privacy_threshold"
        elif not dimensions:
            unavailable_reason = "no_eligible_dimensions"
        return ParticipantReceivedFeedbackSummary(
            project_id=project_id,
            project_name=project_name,
            assignment_round_id=publication.assignment_round_id,
            assessment_cycle_id=publication.assessment_cycle_id,
            questionnaire_key=publication.questionnaire_key,
            questionnaire_title=questionnaire_title,
            cohort=cohort,  # type: ignore[arg-type]
            completed_count=completed_count,
            minimum_completed=minimum_completed,
            score_unit=score_unit,
            scale_min=scale_min,
            scale_max=scale_max,
            visible=visible and bool(dimensions),
            unavailable_reason=unavailable_reason,  # type: ignore[arg-type]
            overall_average=(
                round(sum(visible_scores) / len(visible_scores), 1) if visible_scores else None
            ),
            dimensions=dimensions,
        )

    async def _split_received_feedback_cohorts(
        self,
        profile: ParticipantProfile,
        project_id: UUID | None,
        assignments: list[QuestionnaireAssignment],
        *,
        assessment_cycle_id: UUID | None = None,
    ) -> dict[str, list[QuestionnaireAssignment]]:
        cycle_scoped_assignments = [
            assignment for assignment in assignments if assignment.assessment_cycle_id is not None
        ]
        legacy_assignments = [
            assignment for assignment in assignments if assignment.assessment_cycle_id is None
        ]
        persisted = {
            "direct_team": [
                assignment
                for assignment in cycle_scoped_assignments
                if assignment.icare_cohort == "direct_team"
            ],
            "leadership_peers": [
                assignment
                for assignment in cycle_scoped_assignments
                if assignment.icare_cohort == "leadership_peers"
            ],
        }
        if not legacy_assignments:
            return persisted
        if project_id is not None:
            rows = (
                await self.session.execute(
                    select(ProjectMembership, ParticipantProfile)
                    .join(
                        ParticipantProfile,
                        ParticipantProfile.id == ProjectMembership.participant_profile_id,
                    )
                    .where(ProjectMembership.project_id == project_id)
                    .where(ProjectMembership.active.is_(True))
                )
            ).all()
            participants = [
                HierarchyParticipant(
                    id=participant.id,
                    full_name=participant.full_name,
                    reports_to_name=membership.reports_to_name,
                    role_group=membership.role_group,
                    user_id=participant.user_id,
                )
                for membership, participant in rows
            ]
        else:
            participants = []
        if not participants or profile.id not in {
            participant.id for participant in participants
        }:
            profiles = list(
                (
                    await self.session.execute(
                        select(ParticipantProfile)
                        .where(ParticipantProfile.company_id == profile.company_id)
                    )
                ).scalars()
            )
            participants = [
                HierarchyParticipant(
                    id=participant.id,
                    full_name=participant.full_name,
                    reports_to_name=participant.reports_to_name,
                    role_group=participant.role_group,
                    user_id=participant.user_id,
                )
                for participant in profiles
            ]
        hierarchy = build_organization_hierarchy(participants)
        if hierarchy.ambiguous_name is not None:
            return persisted
        direct_report_ids = {
            participant.id
            for participant in hierarchy.direct_reports_by_manager_id.get(profile.id, [])
        }
        return {
            "direct_team": persisted["direct_team"] + [
                assignment
                for assignment in legacy_assignments
                if assignment.respondent_profile_id in direct_report_ids
                and assignment.respondent_profile_id not in hierarchy.leadership_ids
            ],
            "leadership_peers": persisted["leadership_peers"] + [
                assignment
                for assignment in legacy_assignments
                if assignment.respondent_profile_id in hierarchy.leadership_ids
                and profile.id in hierarchy.leadership_ids
                and assignment.respondent_profile_id != profile.id
            ],
        }

    async def _received_assignments_for_publication(
        self,
        profile: ParticipantProfile,
        publication: ResultPublication,
    ) -> list[QuestionnaireAssignment]:
        statement = (
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.company_id == profile.company_id)
            .where(QuestionnaireAssignment.questionnaire_key == publication.questionnaire_key)
            .where(
                QuestionnaireAssignment.questionnaire_definition_id
                == publication.questionnaire_definition_id
            )
            .where(QuestionnaireAssignment.target_type == AssignmentTargetType.person)
            .where(QuestionnaireAssignment.target_person_id == profile.id)
            .where(QuestionnaireAssignment.respondent_profile_id != profile.id)
            .order_by(QuestionnaireAssignment.created_at.asc())
        )
        source_assignment_ids = _source_assignment_ids(publication.policy_snapshot)
        statement = (
            statement.where(QuestionnaireAssignment.id.in_(source_assignment_ids))
            if source_assignment_ids
            else statement.where(
                QuestionnaireAssignment.assignment_round_id == publication.assignment_round_id
            )
        )
        statement = (
            statement.where(QuestionnaireAssignment.project_id.is_(None))
            if publication.project_id is None
            else statement.where(QuestionnaireAssignment.project_id == publication.project_id)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def _definition_for_publication(
        self,
        publication: ResultPublication,
    ) -> QuestionnaireDefinition | None:
        if publication.questionnaire_definition_id is None or not publication.definition_checksum:
            return None
        result = await self.session.execute(
            select(QuestionnaireDefinition).where(
                QuestionnaireDefinition.id == publication.questionnaire_definition_id
            )
        )
        definition = result.scalar_one_or_none()
        if (
            definition is None
            or definition_publication_checksum(definition) != publication.definition_checksum
        ):
            return None
        return definition

    async def _list_profiles_and_companies(
        self,
        user_id: UUID,
    ) -> list[tuple[ParticipantProfile, Company]]:
        result = await self.session.execute(
            select(ParticipantProfile, Company)
            .join(Company, Company.id == ParticipantProfile.company_id)
            .where(ParticipantProfile.user_id == user_id)
            .order_by(ParticipantProfile.created_at.asc(), ParticipantProfile.id.asc())
        )
        rows = list(result.all())
        if not rows:
            raise DomainError(
                "Participant profile not found for this account.",
                code="participant_profile_not_found",
            )
        return [(row[0], row[1]) for row in rows]

    async def _get_profile_and_company(
        self,
        user_id: UUID,
        participant_profile_id: UUID | None = None,
    ) -> tuple[ParticipantProfile, Company]:
        rows = await self._list_profiles_and_companies(user_id)
        if participant_profile_id is not None:
            selected = next(
                (row for row in rows if row[0].id == participant_profile_id),
                None,
            )
            if selected is None:
                raise DomainError(
                    "Participant context does not belong to this account.",
                    code="participant_context_forbidden",
                )
            return selected
        if len(rows) != 1:
            raise DomainError(
                "Select a participant context before opening the workspace.",
                code="participant_context_required",
            )
        return rows[0]

    async def _get_authorized_contexts(
        self,
        profile_rows: list[tuple[ParticipantProfile, Company]],
    ) -> list[ParticipantWorkspaceContext]:
        profile_ids = {profile.id for profile, _company in profile_rows}
        membership_result = await self.session.execute(
            select(ProjectMembership).where(
                ProjectMembership.participant_profile_id.in_(profile_ids),
                ProjectMembership.active.is_(True),
            )
        )
        memberships = list(membership_result.scalars().all())
        assignment_result = await self.session.execute(
            select(QuestionnaireAssignment).where(
                QuestionnaireAssignment.respondent_profile_id.in_(profile_ids)
            )
        )
        assignments = list(assignment_result.scalars().all())

        project_ids_by_profile: dict[UUID, set[UUID]] = {
            profile_id: set() for profile_id in profile_ids
        }
        for membership in memberships:
            project_ids_by_profile[membership.participant_profile_id].add(membership.project_id)
        for assignment in assignments:
            if assignment.project_id is not None:
                project_ids_by_profile[assignment.respondent_profile_id].add(assignment.project_id)

        project_ids = {
            project_id
            for profile_project_ids in project_ids_by_profile.values()
            for project_id in profile_project_ids
        }
        projects: dict[UUID, CompanyProject] = {}
        cycles_by_project: dict[UUID, list[AssessmentCycle]] = {}
        if project_ids:
            project_result = await self.session.execute(
                select(CompanyProject).where(CompanyProject.id.in_(project_ids))
            )
            projects = {project.id: project for project in project_result.scalars().all()}
            published_cycle_result = await self.session.execute(
                select(
                    ResultPublication.participant_profile_id,
                    ResultPublication.assessment_cycle_id,
                )
                .where(ResultPublication.participant_profile_id.in_(profile_ids))
                .where(ResultPublication.assessment_cycle_id.is_not(None))
                .where(ResultPublication.revoked_at.is_(None))
            )
            published_cycle_ids_by_profile: dict[UUID, set[UUID]] = {}
            for participant_profile_id, assessment_cycle_id in published_cycle_result.all():
                if assessment_cycle_id is not None:
                    published_cycle_ids_by_profile.setdefault(participant_profile_id, set()).add(
                        assessment_cycle_id
                    )
            cycle_result = await self.session.execute(
                select(AssessmentCycle)
                .where(AssessmentCycle.project_id.in_(project_ids))
                .order_by(AssessmentCycle.project_id, AssessmentCycle.sequence)
            )
            for cycle in cycle_result.scalars().all():
                cycles_by_project.setdefault(cycle.project_id, []).append(cycle)

        contexts: list[ParticipantWorkspaceContext] = []
        for profile, company in profile_rows:
            context_projects: list[ParticipantWorkspaceProject] = []
            for context_project_id in sorted(
                project_ids_by_profile[profile.id],
                key=lambda value: projects[value].name if value in projects else str(value),
            ):
                project = projects.get(context_project_id)
                if project is None or project.status == CompanyProjectStatus.draft:
                    continue
                project_assignments = [
                    assignment
                    for assignment in assignments
                    if assignment.respondent_profile_id == profile.id
                    and assignment.project_id == project.id
                ]
                context_projects.append(
                    ParticipantWorkspaceProject(
                        id=project.id,
                        name=project.name,
                        status=project.status.value,
                        history_bucket=(
                            "current"
                            if project.status == CompanyProjectStatus.active
                            else "history"
                        ),
                        deadline_label=_format_deadline(
                            self._workspace_deadline(project_assignments, {project.id: project})
                        ),
                        deadline_at=self._workspace_deadline(
                            project_assignments,
                            {project.id: project},
                        ),
                        cycles=[
                            self._cycle_to_schema(cycle)
                            for cycle in cycles_by_project.get(project.id, [])
                            if cycle.status == AssessmentCycleStatus.active
                            or (
                                cycle.status == AssessmentCycleStatus.closed
                                and cycle.id
                                in published_cycle_ids_by_profile.get(profile.id, set())
                            )
                        ],
                    )
                )
            contexts.append(
                ParticipantWorkspaceContext(
                    participant_profile_id=profile.id,
                    participant_full_name=profile.full_name,
                    participant_email=profile.email,
                    company_id=company.id,
                    company_name=company.name,
                    projects=context_projects,
                )
            )
        return contexts

    async def _resolve_workspace_context(
        self,
        profile_rows: list[tuple[ParticipantProfile, Company]],
        contexts: list[ParticipantWorkspaceContext],
        *,
        participant_profile_id: UUID | None,
        project_id: UUID | None,
        cycle_id: UUID | None,
        allowed_assignment_ids: tuple[UUID, ...] | None,
        scoped_project_id: UUID | None,
    ) -> tuple[
        ParticipantProfile | None,
        Company | None,
        UUID | None,
        UUID | None,
    ]:
        rows_by_profile = {profile.id: (profile, company) for profile, company in profile_rows}
        effective_project_id = project_id
        if scoped_project_id is not None:
            if project_id is not None and project_id != scoped_project_id:
                raise DomainError(
                    "Requested project is outside the secure invitation scope.",
                    code="participant_context_forbidden",
                )
            effective_project_id = scoped_project_id

        secure_profile_id: UUID | None = None
        secure_cycle_id: UUID | None = None
        if allowed_assignment_ids:
            result = await self.session.execute(
                select(QuestionnaireAssignment).where(
                    QuestionnaireAssignment.id.in_(allowed_assignment_ids)
                )
            )
            allowed_assignments = list(result.scalars().all())
            if {assignment.id for assignment in allowed_assignments} != set(
                allowed_assignment_ids
            ):
                raise DomainError(
                    "Secure invitation assignment scope is invalid.",
                    code="participant_context_forbidden",
                )
            secure_profile_ids = {
                assignment.respondent_profile_id for assignment in allowed_assignments
            }
            if len(secure_profile_ids) != 1 or not secure_profile_ids <= rows_by_profile.keys():
                raise DomainError(
                    "Secure invitation does not belong to this account.",
                    code="participant_context_forbidden",
                )
            secure_profile_id = next(iter(secure_profile_ids))
            secure_project_ids = {
                assignment.project_id
                for assignment in allowed_assignments
                if assignment.project_id is not None
            }
            if effective_project_id is not None and secure_project_ids != {effective_project_id}:
                raise DomainError(
                    "Secure invitation does not belong to the requested project.",
                    code="participant_context_forbidden",
                )
            if effective_project_id is None and len(secure_project_ids) == 1:
                effective_project_id = next(iter(secure_project_ids))
            secure_cycle_ids = {
                assignment.assessment_cycle_id
                for assignment in allowed_assignments
                if assignment.assessment_cycle_id is not None
            }
            if len(secure_cycle_ids) == 1:
                secure_cycle_id = next(iter(secure_cycle_ids))
                if cycle_id is not None and cycle_id != secure_cycle_id:
                    raise DomainError(
                        "Requested cycle is outside the secure invitation scope.",
                        code="participant_cycle_forbidden",
                    )
                cycle_id = secure_cycle_id

        effective_profile_id = participant_profile_id or secure_profile_id
        if participant_profile_id is not None and secure_profile_id not in {
            None,
            participant_profile_id,
        }:
            raise DomainError(
                "Requested profile is outside the secure invitation scope.",
                code="participant_context_forbidden",
            )

        if cycle_id is not None:
            matching_cycles = [
                (context.participant_profile_id, project.id)
                for context in contexts
                for project in context.projects
                for cycle in project.cycles
                if cycle.id == cycle_id
            ]
            if not matching_cycles:
                raise DomainError(
                    "Assessment cycle does not belong to this account.",
                    code="participant_cycle_forbidden",
                )
            cycle_profiles = {
                profile_id for profile_id, _cycle_project_id in matching_cycles
            }
            cycle_project_ids = {
                cycle_project_id for _profile_id, cycle_project_id in matching_cycles
            }
            if effective_profile_id is None and len(cycle_profiles) == 1:
                effective_profile_id = next(iter(cycle_profiles))
            if effective_project_id is None and len(cycle_project_ids) == 1:
                effective_project_id = next(iter(cycle_project_ids))
            if (
                effective_profile_id not in cycle_profiles
                or effective_project_id not in cycle_project_ids
            ):
                raise DomainError(
                    "Assessment cycle is outside the selected participant context.",
                    code="participant_cycle_forbidden",
                )

        if effective_profile_id is None and effective_project_id is not None:
            matching_profile_ids = {
                context.participant_profile_id
                for context in contexts
                if any(project.id == effective_project_id for project in context.projects)
            }
            if len(matching_profile_ids) == 1:
                effective_profile_id = next(iter(matching_profile_ids))
            elif len(matching_profile_ids) > 1:
                return None, None, effective_project_id, cycle_id

        if effective_profile_id is None and effective_project_id is None:
            program_options = [
                (context.participant_profile_id, project.id)
                for context in contexts
                for project in context.projects
            ]
            if len(program_options) == 1:
                effective_profile_id, effective_project_id = program_options[0]

        if effective_profile_id is None:
            if len(profile_rows) != 1:
                return None, None, effective_project_id, cycle_id
            effective_profile_id = profile_rows[0][0].id

        selected = rows_by_profile.get(effective_profile_id)
        if selected is None:
            raise DomainError(
                "Participant context does not belong to this account.",
                code="participant_context_forbidden",
            )
        selected_context = next(
            context
            for context in contexts
            if context.participant_profile_id == effective_profile_id
        )
        if effective_project_id is None:
            if len(selected_context.projects) > 1:
                return None, None, None, cycle_id
            if len(selected_context.projects) == 1:
                effective_project_id = selected_context.projects[0].id
        if effective_project_id is not None and not any(
            project.id == effective_project_id for project in selected_context.projects
        ):
            raise DomainError(
                "Project does not belong to the selected participant context.",
                code="participant_context_forbidden",
            )
        if cycle_id is None and allowed_assignment_ids is None and effective_project_id is not None:
            selected_project = next(
                project
                for project in selected_context.projects
                if project.id == effective_project_id
            )
            active_cycles = [
                cycle for cycle in selected_project.cycles if cycle.status == "active"
            ]
            if len(active_cycles) == 1:
                cycle_id = active_cycles[0].id
        return selected[0], selected[1], effective_project_id, cycle_id

    async def _list_assignments(
        self,
        profile: ParticipantProfile,
        *,
        project_id: UUID | None = None,
        cycle_id: UUID | None = None,
        allowed_assignment_ids: tuple[UUID, ...] | None = None,
        visible_cycle_ids: set[UUID] | None = None,
        history_only: bool = False,
    ) -> list[QuestionnaireAssignment]:
        statement = (
            select(QuestionnaireAssignment)
            .outerjoin(
                CompanyProject,
                CompanyProject.id == QuestionnaireAssignment.project_id,
            )
            .where(QuestionnaireAssignment.company_id == profile.company_id)
            .where(QuestionnaireAssignment.respondent_profile_id == profile.id)
            .where(QuestionnaireAssignment.status != AssignmentStatus.cancelled)
            .order_by(
                QuestionnaireAssignment.due_at.asc().nulls_last(),
                QuestionnaireAssignment.created_at.asc(),
            )
        )
        if history_only:
            statement = statement.where(
                QuestionnaireAssignment.status.in_(COMPLETED_ASSIGNMENT_STATUSES)
            )
        else:
            statement = statement.where(
                or_(
                    QuestionnaireAssignment.project_id.is_(None),
                    CompanyProject.status == CompanyProjectStatus.active,
                )
            )
        if allowed_assignment_ids is not None:
            if not allowed_assignment_ids:
                return []
            statement = statement.where(QuestionnaireAssignment.id.in_(allowed_assignment_ids))
        if project_id is not None:
            statement = statement.where(QuestionnaireAssignment.project_id == project_id)
        if cycle_id is not None:
            statement = statement.where(QuestionnaireAssignment.assessment_cycle_id == cycle_id)
        elif visible_cycle_ids is not None:
            cycle_conditions = [QuestionnaireAssignment.assessment_cycle_id.is_(None)]
            if visible_cycle_ids:
                cycle_conditions.append(
                    QuestionnaireAssignment.assessment_cycle_id.in_(visible_cycle_ids)
                )
            statement = statement.where(or_(*cycle_conditions))
        result = await self.session.execute(statement)
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

    async def _get_cycle_pcm_values(
        self,
        assignments: list[QuestionnaireAssignment],
    ) -> tuple[str | None, str | None]:
        pcm_assignment_ids = {
            assignment.id
            for assignment in assignments
            if assignment.status in COMPLETED_ASSIGNMENT_STATUSES
            and assignment.questionnaire_key in {"pcm_base", "phase", "pcm_phase"}
        }
        if not pcm_assignment_ids:
            return None, None
        result = await self.session.execute(
            select(QuestionnaireResponse)
            .where(QuestionnaireResponse.assignment_id.in_(pcm_assignment_ids))
            .where(QuestionnaireResponse.status == QuestionnaireResponseStatus.submitted)
            .order_by(QuestionnaireResponse.submitted_at.asc().nulls_last())
        )
        pcm_base: str | None = None
        pcm_phase: str | None = None
        for response in result.scalars().all():
            base_value = response.answers.get("pcm_base")
            phase_value = response.answers.get("pcm_phase")
            if isinstance(base_value, str) and base_value.strip():
                pcm_base = base_value.strip()
            if isinstance(phase_value, str) and phase_value.strip():
                pcm_phase = phase_value.strip()
        return pcm_base, pcm_phase

    async def _get_active_individual_publications(
        self,
        profile: ParticipantProfile,
        assignments: list[QuestionnaireAssignment],
    ) -> dict[UUID, ResultPublication]:
        assignment_ids = {assignment.id for assignment in assignments}
        if not assignment_ids:
            return {}
        result = await self.session.execute(
            select(ResultPublication)
            .where(ResultPublication.company_id == profile.company_id)
            .where(ResultPublication.participant_profile_id == profile.id)
            .where(ResultPublication.kind == ResultPublicationKind.individual)
            .where(ResultPublication.revoked_at.is_(None))
            .where(ResultPublication.source_assignment_id.in_(assignment_ids))
        )
        return {
            publication.source_assignment_id: publication
            for publication in result.scalars().all()
            if publication.source_assignment_id is not None
        }

    async def _get_result_definitions(
        self,
        assignments: list[QuestionnaireAssignment],
    ) -> dict[UUID, QuestionnaireDefinition]:
        definition_ids = {
            assignment.questionnaire_definition_id
            for assignment in assignments
            if assignment.questionnaire_definition_id is not None
        }
        definitions_by_id: dict[UUID, QuestionnaireDefinition] = {}
        if definition_ids:
            result = await self.session.execute(
                select(QuestionnaireDefinition).where(
                    QuestionnaireDefinition.id.in_(definition_ids)
                )
            )
            definitions_by_id = {definition.id: definition for definition in result.scalars().all()}

        missing_keys = {
            assignment.questionnaire_key
            for assignment in assignments
            if assignment.questionnaire_definition_id not in definitions_by_id
        }
        latest_by_key: dict[str, QuestionnaireDefinition] = {}
        if missing_keys:
            result = await self.session.execute(
                select(QuestionnaireDefinition)
                .where(QuestionnaireDefinition.key.in_(missing_keys))
                .where(QuestionnaireDefinition.active.is_(True))
                .order_by(
                    QuestionnaireDefinition.key,
                    QuestionnaireDefinition.version.desc(),
                )
            )
            for definition in result.scalars().all():
                latest_by_key.setdefault(definition.key, definition)

        return {
            assignment.id: definition
            for assignment in assignments
            if (
                definition := definitions_by_id.get(assignment.questionnaire_definition_id)
                or latest_by_key.get(assignment.questionnaire_key)
            )
            is not None
        }

    def _assignment_to_task(
        self,
        *,
        assignment: QuestionnaireAssignment,
        teams: dict[UUID, Team],
        people: dict[UUID, ParticipantProfile],
        projects: dict[UUID, CompanyProject],
    ) -> InviteTask:
        title, detail, estimated_minutes = _invite_task_copy(assignment.questionnaire_key)
        target_label = "Autoevaluare"
        if assignment.questionnaire_key in {"lencioni", "lencioni_en"}:
            target_label = "Echipa ta"
        elif assignment.target_type == AssignmentTargetType.team and assignment.target_team_id:
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
            questionnaireDefinitionId=assignment.questionnaire_definition_id,
            projectId=assignment.project_id,
            projectName=(
                projects[assignment.project_id].name
                if assignment.project_id is not None and assignment.project_id in projects
                else None
            ),
            assignmentRoundId=assignment.assignment_round_id,
            assessmentCycleId=getattr(assignment, "assessment_cycle_id", None),
        )

    def _assignment_to_result(
        self,
        *,
        assignment: QuestionnaireAssignment,
        result: ScoringResult,
        definition: QuestionnaireDefinition | None,
        publication: ResultPublication | None,
        teams: dict[UUID, Team],
        people: dict[UUID, ParticipantProfile],
        projects: dict[UUID, CompanyProject],
    ) -> ParticipantWorkspaceResult | None:
        if (
            publication is None
            or definition is None
            or publication.source_count != 1
            or publication.source_assignment_id != assignment.id
            or publication.questionnaire_definition_id != definition.id
            or publication.questionnaire_definition_id
            != assignment.questionnaire_definition_id
            or not publication.definition_checksum
            or publication.definition_checksum != definition_publication_checksum(definition)
            or publication.questionnaire_key != assignment.questionnaire_key
            or publication.assignment_round_id != assignment.assignment_round_id
        ):
            return None
        policy = (
            publication.policy_snapshot
            if isinstance(publication.policy_snapshot, dict)
            else {}
        )
        publication_mode = policy.get("publication", "none")
        target_type = assignment.target_type.value
        allowed_target_types = policy.get("target_types", ["self", "team"])
        if publication_mode == "none" or target_type not in allowed_target_types:
            return None
        if (
            policy.get("require_self_target", False)
            and assignment.target_person_id != assignment.respondent_profile_id
        ):
            return None

        visible_dimension_ids = {
            value
            for value in policy.get("dimension_ids", [])
            if isinstance(value, str) and value.strip()
        }
        labels = _definition_score_labels(definition)
        feedback_by_dimension = _definition_score_feedback(definition)
        public_scores: dict[str, dict[str, float | str]] = {}
        for dimension_id in visible_dimension_ids:
            value = result.scores.get(dimension_id)
            score = _extract_numeric_score(value)
            if score is None:
                continue
            public_value: dict[str, float | str] = {
                "score": score,
                "label": labels.get(dimension_id, _prettify_score_key(dimension_id)),
            }
            if publication_mode == "scores_and_interpretation" and isinstance(value, dict):
                interpretation = value.get("interpretation")
                if isinstance(interpretation, str) and interpretation.strip():
                    public_value["interpretation"] = interpretation.strip()
            feedback = feedback_by_dimension.get(dimension_id)
            if (
                assignment.questionnaire_key
                in {"distress_drivers", "distress_drivers_en"}
                and score > 50
                and feedback
            ):
                public_value["feedback"] = feedback
            public_scores[dimension_id] = public_value

        if not public_scores:
            return None
        derived_scale = derive_definition_score_scale(
            definition,
            dimension_ids=public_scores.keys(),
        )
        score_scale = derived_scale.scale if derived_scale.compatible else None
        task = self._assignment_to_task(
            assignment=assignment,
            teams=teams,
            people=people,
            projects=projects,
        )
        include_primary = policy.get("include_primary_result", True)
        primary_result = (
            result.primary_result
            if include_primary and result.primary_result in public_scores
            else None
        )
        return ParticipantWorkspaceResult(
            assignment_id=assignment.id,
            assessment_cycle_id=getattr(assignment, "assessment_cycle_id", None),
            project_id=assignment.project_id,
            project_name=task.projectName,
            questionnaire_key=assignment.questionnaire_key,
            title=task.title,
            target_label=task.targetLabel,
            scores=public_scores,
            primary_result=primary_result,
            score_unit=score_scale.score_unit if score_scale is not None else None,
            scale_min=score_scale.scale_min if score_scale is not None else None,
            scale_max=score_scale.scale_max if score_scale is not None else None,
            score_scale_compatible=derived_scale.compatible and score_scale is not None,
            unavailable_reason=(
                None
                if derived_scale.compatible and score_scale is not None
                else "incompatible_score_scales"
            ),
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

    def _workspace_projects(
        self,
        assignments: list[QuestionnaireAssignment],
        projects: dict[UUID, CompanyProject],
        *,
        cycles: list[ParticipantWorkspaceCycle] | None = None,
    ) -> list[ParticipantWorkspaceProject]:
        cycles_by_project: dict[UUID, list[ParticipantWorkspaceCycle]] = {}
        for cycle in cycles or []:
            cycles_by_project.setdefault(cycle.project_id, []).append(cycle)
        ordered_project_ids = list(
            dict.fromkeys(
                assignment.project_id
                for assignment in assignments
                if assignment.project_id is not None and assignment.project_id in projects
            )
        )
        workspace_projects: list[ParticipantWorkspaceProject] = []
        for project_id in ordered_project_ids:
            project = projects[project_id]
            project_assignments = [
                assignment for assignment in assignments if assignment.project_id == project_id
            ]
            deadline_at = self._workspace_deadline(project_assignments, {project_id: project})
            workspace_projects.append(
                ParticipantWorkspaceProject(
                    id=project.id,
                    name=project.name,
                    status=project.status.value,
                    history_bucket=(
                        "current"
                        if project.status == CompanyProjectStatus.active
                        else "history"
                    ),
                    deadline_label=_format_deadline(deadline_at),
                    deadline_at=deadline_at,
                    cycles=cycles_by_project.get(project.id, []),
                )
            )
        return workspace_projects

    @staticmethod
    def _cycle_to_schema(cycle: AssessmentCycle) -> ParticipantWorkspaceCycle:
        return ParticipantWorkspaceCycle(
            id=cycle.id,
            project_id=cycle.project_id,
            sequence=cycle.sequence,
            name=cycle.name,
            status=cycle.status.value,
            starts_at=cycle.starts_at,
            due_at=cycle.due_at,
            closed_at=cycle.closed_at,
        )

    @staticmethod
    def _selected_cycles(
        contexts: list[ParticipantWorkspaceContext],
        participant_profile_id: UUID,
        project_id: UUID | None,
    ) -> list[ParticipantWorkspaceCycle]:
        context = next(
            (
                item
                for item in contexts
                if item.participant_profile_id == participant_profile_id
            ),
            None,
        )
        if context is None:
            return []
        return [
            cycle
            for project in context.projects
            if project_id is None or project.id == project_id
            for cycle in project.cycles
        ]

    def _workspace_deadline(
        self,
        assignments: list[QuestionnaireAssignment],
        projects: dict[UUID, CompanyProject],
    ) -> datetime | None:
        candidates = [
            assignment.due_at for assignment in assignments if assignment.due_at is not None
        ]
        candidates.extend(
            project.due_at for project in projects.values() if project.due_at is not None
        )
        if not candidates:
            return None
        return min(candidates)


def _definition_score_labels(
    definition: QuestionnaireDefinition | None,
) -> dict[str, str]:
    if definition is None:
        return {}

    labels: dict[str, str] = {}
    if definition.private_config:
        labels.update(_schema_score_labels(definition.private_config.get("schema")))

    # Participant-safe labels own the UI copy. Private scoring metadata only fills
    # gaps when an older definition does not include labels in its public schema.
    labels.update(_schema_score_labels(definition.schema))
    return labels


def _schema_score_labels(schema: object) -> dict[str, str]:
    if not isinstance(schema, dict):
        return {}
    scoring = schema.get("scoring")
    labels: dict[str, str] = {}
    if isinstance(scoring, dict):
        for collection_name in ("groups", "drivers"):
            for item in scoring.get(collection_name, []):
                if not isinstance(item, dict):
                    continue
                dimension_id = item.get("id")
                label = item.get("label")
                if isinstance(dimension_id, str) and isinstance(label, str) and label.strip():
                    labels[dimension_id] = label.strip()

    for section in schema.get("sections", []):
        if not isinstance(section, dict):
            continue
        for question in section.get("questions", []):
            if not isinstance(question, dict) or question.get("type") != "statement_score_set":
                continue
            dimension_id = question.get("id")
            label = question.get("label")
            if isinstance(dimension_id, str) and isinstance(label, str) and label.strip():
                labels[dimension_id] = label.strip()
    return labels


def _definition_score_feedback(
    definition: QuestionnaireDefinition | None,
) -> dict[str, str]:
    if definition is None:
        return {}
    feedback: dict[str, str] = {}
    for schema in (
        definition.schema,
        (definition.private_config or {}).get("schema"),
    ):
        if not isinstance(schema, dict):
            continue
        scoring = schema.get("scoring")
        if not isinstance(scoring, dict):
            continue
        for item in scoring.get("drivers", []):
            if not isinstance(item, dict):
                continue
            dimension_id = item.get("id")
            if not isinstance(dimension_id, str) or not dimension_id.strip():
                continue
            for key in (
                "feedback_above_50",
                "participant_feedback",
                "feedback",
                "guidance",
            ):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    feedback[dimension_id] = value.strip()
                    break
    return feedback


def _definition_score_scale(
    definition: QuestionnaireDefinition,
    *,
    dimension_ids: set[str] | None = None,
) -> tuple[str, float, float] | None:
    derived = derive_definition_score_scale(
        definition,
        dimension_ids=dimension_ids,
    )
    if not derived.compatible or derived.scale is None:
        return None
    return (
        derived.scale.score_unit,
        derived.scale.scale_min,
        derived.scale.scale_max,
    )


def _definition_scale_max(definition: QuestionnaireDefinition) -> float | None:
    scale = _definition_score_scale(definition)
    return scale[2] if scale is not None else None


def _prettify_score_key(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").split()) or value


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


def _source_assignment_ids(policy: object) -> set[UUID]:
    if not isinstance(policy, dict):
        return set()
    values = policy.get("source_assignment_ids")
    if not isinstance(values, list):
        return set()
    assignment_ids: set[UUID] = set()
    for value in values:
        if not isinstance(value, str):
            return set()
        try:
            assignment_ids.add(UUID(value))
        except ValueError:
            return set()
    return assignment_ids


def _positive_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
