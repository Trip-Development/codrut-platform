from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleQuestionnaire,
    AssessmentCycleStatus,
    AssessmentCycleTeamMembership,
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    IcareCohort,
    QuestionnaireAssignment,
    ResponseVisibilityPolicy,
    Team,
    TeamMembership,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.assignments.repository import AssignmentRepository
from codrut.modules.assignments.schemas import (
    AssessmentCycleCloseRequest,
    AssessmentCycleCreateRequest,
    AssessmentCycleQuestionnaireResponse,
    AssessmentCycleResponse,
    AssessmentCycleUpdateRequest,
    AssignmentCreateRequest,
    AssignmentPlanItemResponse,
    AssignmentPlanResponse,
    AssignmentPlanSaveItem,
    AssignmentPlanSaveRequest,
    AssignmentPlanSaveResponse,
    AssignmentPlanScopeResponse,
    AssignmentStatusUpdateRequest,
    TeamCreateRequest,
    TeamMembershipCreateRequest,
)
from codrut.modules.companies.hierarchy import (
    HierarchyParticipant,
    OrganizationHierarchy,
    build_organization_hierarchy,
)
from codrut.modules.companies.models import (
    CompanyMembershipRole,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.forms.repository import FormsRepository
from codrut.modules.scoring.publication import ResultPublicationService
from codrut.modules.scoring.repository import ScoringRepository

COMPLETED_ASSIGNMENT_STATUSES = frozenset(
    {
        AssignmentStatus.submitted,
        AssignmentStatus.validated,
        AssignmentStatus.scored,
    }
)
EDITABLE_ASSIGNMENT_STATUSES = frozenset(
    {
        AssignmentStatus.assigned,
        AssignmentStatus.invited,
        AssignmentStatus.started,
    }
)

SUPPORTED_CYCLE_PLAN_QUESTIONNAIRES = frozenset(
    {
        "lencioni",
        "lencioni_en",
        "distress_drivers",
        "distress_drivers_en",
        "pcm_base",
        "phase",
        "pcm_phase",
        "boss_360",
        "boss_360_en",
        "icare",
    }
)
ICARE_QUESTIONNAIRE_KEYS = frozenset({"boss_360", "boss_360_en", "icare"})


class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assignment_repository = AssignmentRepository(session)
        self.company_repository = CompanyRepository(session)
        self.forms_repository = FormsRepository(session)
        self.scoring_repository = ScoringRepository(session)
        self.result_publication_service = ResultPublicationService(session)
        self._icare_hierarchy_cache: dict[
            tuple[UUID, UUID | None],
            OrganizationHierarchy,
        ] = {}

    async def list_assessment_cycles(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
    ) -> list[AssessmentCycleResponse]:
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, project_id)
        cycles = await self.assignment_repository.list_assessment_cycles(company_id, project_id)
        return [await self._assessment_cycle_response(cycle) for cycle in cycles]

    async def create_assessment_cycle(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
        payload: AssessmentCycleCreateRequest,
    ) -> AssessmentCycleResponse:
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(
            company_id,
            project_id,
            allow_archived=False,
        )
        if await self.assignment_repository.get_open_assessment_cycle(company_id, project_id):
            raise DomainError(
                "Close the current assessment cycle before creating another one.",
                code="assessment_cycle_open_exists",
            )

        source_cycle = (
            await self.assignment_repository.get_assessment_cycle(
                company_id,
                project_id,
                payload.source_cycle_id,
            )
            if payload.source_cycle_id is not None
            else await self.assignment_repository.get_latest_assessment_cycle(
                company_id,
                project_id,
            )
        )
        if source_cycle is None:
            raise DomainError(
                "A source assessment cycle is required.",
                code="assessment_cycle_source_not_found",
            )
        source_questionnaires = (
            await self.assignment_repository.list_assessment_cycle_questionnaires(source_cycle.id)
        )
        if not source_questionnaires:
            raise DomainError(
                "The source assessment cycle has no pinned questionnaires.",
                code="assessment_cycle_source_empty",
            )
        requested_keys = (
            list(dict.fromkeys(key.strip() for key in payload.questionnaire_keys))
            if payload.questionnaire_keys is not None
            else None
        )
        if requested_keys is not None:
            if not requested_keys or any(not key for key in requested_keys):
                raise DomainError(
                    "Select at least one questionnaire.",
                    code="assessment_cycle_questionnaires_required",
                    details={"field": "questionnaire_keys"},
                )
            source_by_key = {item.questionnaire_key: item for item in source_questionnaires}
            missing_keys = [key for key in requested_keys if key not in source_by_key]
            if missing_keys:
                raise DomainError(
                    "One or more questionnaires are not part of the source cycle.",
                    code="assessment_cycle_questionnaire_not_found",
                    details={"questionnaire_keys": missing_keys},
                )
            source_questionnaires = [source_by_key[key] for key in requested_keys]

        unsupported_keys = sorted(
            item.questionnaire_key
            for item in source_questionnaires
            if item.questionnaire_key not in SUPPORTED_CYCLE_PLAN_QUESTIONNAIRES
        )
        if unsupported_keys:
            raise DomainError(
                "One or more questionnaires do not define a repeat-assignment strategy.",
                code="assessment_cycle_questionnaire_unsupported",
                details={"questionnaire_keys": unsupported_keys},
            )

        sequence = await self.assignment_repository.next_assessment_cycle_sequence(
            company_id,
            project_id,
        )
        starts_at = payload.starts_at
        due_at = payload.due_at
        _validate_cycle_dates(starts_at, due_at)
        name = (
            _normalize_cycle_name(payload.name)
            if payload.name is not None
            else f"Reevaluare {sequence - 1}"
        )
        try:
            cycle = await self.assignment_repository.add_assessment_cycle(
                AssessmentCycle(
                    company_id=company_id,
                    project_id=project_id,
                    sequence=sequence,
                    name=name,
                    status=AssessmentCycleStatus.draft,
                    source_cycle_id=source_cycle.id,
                    starts_at=starts_at,
                    due_at=due_at,
                    created_by_user_id=user_id,
                )
            )
        except IntegrityError as exc:
            await self.session.rollback()
            raise DomainError(
                "Another assessment cycle is already open for this project.",
                code="assessment_cycle_open_exists",
            ) from exc
        questionnaires = [
            AssessmentCycleQuestionnaire(
                assessment_cycle_id=cycle.id,
                questionnaire_definition_id=item.questionnaire_definition_id,
                questionnaire_key=item.questionnaire_key,
                display_order=item.display_order,
            )
            for item in source_questionnaires
        ]
        await self.assignment_repository.add_assessment_cycle_questionnaires(questionnaires)
        return await self._assessment_cycle_response(cycle, questionnaires=questionnaires)

    async def update_assessment_cycle(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
        assessment_cycle_id: UUID,
        payload: AssessmentCycleUpdateRequest,
    ) -> AssessmentCycleResponse:
        await self._require_company_manager(user_id, company_id)
        cycle = await self._require_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
            for_update=True,
        )
        self._require_draft_cycle(cycle)
        if "name" in payload.model_fields_set:
            if payload.name is None:
                raise DomainError(
                    "Assessment cycle name is required.",
                    code="assessment_cycle_name_required",
                    details={"field": "name"},
                )
            cycle.name = _normalize_cycle_name(payload.name)
        if "starts_at" in payload.model_fields_set:
            cycle.starts_at = payload.starts_at
        if "due_at" in payload.model_fields_set:
            cycle.due_at = payload.due_at
        _validate_cycle_dates(cycle.starts_at, cycle.due_at)
        if "due_at" in payload.model_fields_set:
            await self.assignment_repository.synchronize_cycle_assignment_deadlines(
                cycle.id,
                cycle.due_at,
            )
        return await self._assessment_cycle_response(cycle)

    async def delete_assessment_cycle(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
        assessment_cycle_id: UUID,
    ) -> None:
        await self._require_company_manager(user_id, company_id)
        cycle = await self._require_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
            for_update=True,
        )
        self._require_draft_cycle(cycle)
        await self.assignment_repository.delete_assessment_cycle(cycle)

    async def close_assessment_cycle(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID,
        assessment_cycle_id: UUID,
        payload: AssessmentCycleCloseRequest,
    ) -> AssessmentCycleResponse:
        await self._require_company_manager(user_id, company_id)
        cycle = await self._require_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
            for_update=True,
        )
        if cycle.status != AssessmentCycleStatus.active:
            raise DomainError(
                "Only an active assessment cycle can be closed.",
                code="assessment_cycle_not_active",
            )
        unfinished_count = await self.assignment_repository.count_unfinished_cycle_assignments(
            cycle.id
        )
        if unfinished_count and not payload.cancel_unfinished:
            raise DomainError(
                "The assessment cycle still has unfinished assignments.",
                code="assessment_cycle_has_unfinished_assignments",
                details={"unfinished_count": unfinished_count},
            )
        if unfinished_count:
            cancelled = await self.assignment_repository.cancel_unfinished_cycle_assignments(
                cycle.id
            )
            for assignment in cancelled:
                await self.result_publication_service.reconcile_assignment(assignment.id)
        cycle.status = AssessmentCycleStatus.closed
        cycle.closed_at = datetime.now(UTC)
        return await self._assessment_cycle_response(cycle)

    async def activate_assessment_cycle_for_invitation(
        self,
        company_id: UUID,
        project_id: UUID,
        assessment_cycle_id: UUID,
    ) -> AssessmentCycle:
        cycle = await self._require_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
            for_update=True,
        )
        if cycle.status == AssessmentCycleStatus.closed:
            raise DomainError(
                "The assessment cycle is closed.",
                code="assessment_cycle_closed",
            )
        if cycle.status == AssessmentCycleStatus.draft:
            cycle.status = AssessmentCycleStatus.active
            cycle.starts_at = cycle.starts_at or datetime.now(UTC)
        return cycle

    async def create_team(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: TeamCreateRequest,
    ) -> Team:
        await self._require_company_manager(user_id, company_id)
        return await self.assignment_repository.add_team(
            Team(company_id=company_id, name=payload.name.strip(), type=payload.type)
        )

    async def list_teams(self, user_id: UUID, company_id: UUID) -> list[Team]:
        await self._require_company_manager(user_id, company_id)
        return await self.assignment_repository.list_teams(company_id)

    async def add_team_membership(
        self,
        user_id: UUID,
        company_id: UUID,
        team_id: UUID,
        payload: TeamMembershipCreateRequest,
    ) -> TeamMembership:
        await self._require_company_manager(user_id, company_id)
        team = await self.assignment_repository.get_team(company_id, team_id)
        if team is None:
            raise DomainError("Team not found.", code="team_not_found")
        await self._require_company_participant(company_id, payload.participant_profile_id)
        existing = await self.assignment_repository.get_team_membership(
            team_id,
            payload.participant_profile_id,
        )
        if existing is not None:
            raise DomainError("Participant is already in this team.", code="team_membership_exists")
        return await self.assignment_repository.add_team_membership(
            TeamMembership(
                team_id=team_id,
                participant_profile_id=payload.participant_profile_id,
                role=payload.role,
            )
        )

    async def list_team_memberships(
        self,
        user_id: UUID,
        company_id: UUID,
        team_id: UUID,
    ) -> list[TeamMembership]:
        await self._require_company_manager(user_id, company_id)
        team = await self.assignment_repository.get_team(company_id, team_id)
        if team is None:
            raise DomainError("Team not found.", code="team_not_found")
        return await self.assignment_repository.list_team_memberships(team_id)

    async def remove_team_membership(
        self,
        user_id: UUID,
        company_id: UUID,
        team_id: UUID,
        membership_id: UUID,
    ) -> None:
        await self._require_company_manager(user_id, company_id)
        team = await self.assignment_repository.get_team(company_id, team_id)
        if team is None:
            raise DomainError("Team not found.", code="team_not_found")
        membership = await self.assignment_repository.get_team_membership_by_id(
            team_id,
            membership_id,
        )
        if membership is None:
            raise DomainError("Team membership not found.", code="team_membership_not_found")
        await self.assignment_repository.delete_team_membership(membership)

    async def create_assignment(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: AssignmentCreateRequest,
    ) -> QuestionnaireAssignment:
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(
            company_id,
            payload.project_id,
            allow_archived=False,
        )
        cycle = await self._cycle_for_assignment_write(
            company_id,
            payload.project_id,
            payload.assessment_cycle_id,
        )
        _validate_target_shape(payload)
        questionnaire_key = payload.questionnaire_key.strip()
        await self._require_company_participant(company_id, payload.respondent_profile_id)
        await self._require_project_participant(
            company_id,
            payload.project_id,
            payload.respondent_profile_id,
        )
        if payload.target_person_id is not None:
            await self._require_company_participant(company_id, payload.target_person_id)
            await self._require_project_participant(
                company_id,
                payload.project_id,
                payload.target_person_id,
            )
        if payload.target_team_id is not None:
            team = await self.assignment_repository.get_team(company_id, payload.target_team_id)
            if team is None:
                raise DomainError("Target team not found in this company.", code="team_not_found")
            await self._require_project_team_members(
                company_id,
                payload.project_id,
                team.id,
            )
            if cycle is not None:
                await self._snapshot_existing_team_for_cycle(cycle, team.id)
        definition = await self._definition_for_cycle(cycle, questionnaire_key)
        if cycle is not None:
            existing = await self.assignment_repository.get_matching_assignment(
                company_id=company_id,
                project_id=payload.project_id,
                respondent_profile_id=payload.respondent_profile_id,
                questionnaire_key=questionnaire_key,
                target_type=payload.target_type,
                target_person_id=payload.target_person_id,
                target_team_id=payload.target_team_id,
                assessment_cycle_id=cycle.id,
            )
            if existing is not None:
                raise DomainError(
                    "This assignment already exists in the assessment cycle.",
                    code="assessment_cycle_assignment_exists",
                )
        cycle_assignments = (
            await self.assignment_repository.list_assignments(
                company_id,
                payload.project_id,
                cycle.id,
            )
            if cycle is not None
            else []
        )
        if cycle is not None:
            leadership_ids = await self._cycle_icare_leadership_ids(
                cycle,
                cycle_assignments,
            )
            _require_cycle_icare_self_target(
                questionnaire_key=questionnaire_key,
                target_type=payload.target_type,
                respondent_profile_id=payload.respondent_profile_id,
                target_person_id=payload.target_person_id,
                leadership_ids=leadership_ids,
            )
        assignment = QuestionnaireAssignment(
            company_id=company_id,
            project_id=payload.project_id,
            assignment_round_id=(
                cycle_assignments[0].assignment_round_id if cycle_assignments else uuid4()
            ),
            assessment_cycle_id=cycle.id if cycle is not None else None,
            cycle_shape_guard=cycle.id if cycle is not None else None,
            respondent_profile_id=payload.respondent_profile_id,
            questionnaire_key=questionnaire_key,
            questionnaire_definition_id=definition.id,
            target_type=payload.target_type,
            target_person_id=payload.target_person_id,
            target_team_id=payload.target_team_id,
            icare_cohort=await self._icare_cohort_for_assignment(
                company_id=company_id,
                project_id=payload.project_id,
                cycle=cycle,
                questionnaire_key=questionnaire_key,
                respondent_profile_id=payload.respondent_profile_id,
                target_type=payload.target_type,
                target_person_id=payload.target_person_id,
            ),
            access_mode=AssignmentAccessMode.account_link,
            status=AssignmentStatus.assigned,
            visibility_policy=payload.visibility_policy,
            due_at=cycle.due_at if cycle is not None else None,
        )
        if cycle is None:
            return await self.assignment_repository.add_assignment(assignment)
        try:
            async with self.session.begin_nested():
                return await self.assignment_repository.add_assignment(assignment)
        except IntegrityError as exc:
            raise DomainError(
                "This assignment already exists in the assessment cycle.",
                code="assessment_cycle_assignment_exists",
            ) from exc

    async def list_assignments(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
    ) -> list[QuestionnaireAssignment]:
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, project_id)
        if assessment_cycle_id is not None:
            if project_id is None:
                raise DomainError(
                    "A project is required when filtering by assessment cycle.",
                    code="assessment_cycle_project_required",
                )
            await self._require_assessment_cycle(company_id, project_id, assessment_cycle_id)
        return await self.assignment_repository.list_assignments(
            company_id,
            project_id,
            assessment_cycle_id,
        )

    async def require_company_manager(self, user_id: UUID, company_id: UUID) -> None:
        await self._require_company_manager(user_id, company_id)

    async def build_default_assignment_plan(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
        source_cycle_id: UUID | None = None,
    ) -> AssignmentPlanResponse:
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, project_id)
        if assessment_cycle_id is not None and source_cycle_id is not None:
            raise DomainError(
                "Choose either an assessment cycle or a source cycle preview.",
                code="assessment_cycle_scope_conflict",
            )
        self._icare_hierarchy_cache.clear()
        cycle = await self._optional_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
        )
        source_cycle = await self._optional_assessment_cycle(
            company_id,
            project_id,
            source_cycle_id,
        )
        cycle_questionnaire_keys: set[str] | None = None
        questionnaire_cycle = source_cycle or cycle
        if questionnaire_cycle is not None and (
            source_cycle is not None or not self._is_initial_draft_cycle(questionnaire_cycle)
        ):
            cycle_questionnaire_keys = {
                item.questionnaire_key
                for item in await self.assignment_repository.list_assessment_cycle_questionnaires(
                    questionnaire_cycle.id
                )
            }
            if source_cycle is not None and not cycle_questionnaire_keys:
                raise DomainError(
                    "The source assessment cycle has no questionnaire definitions.",
                    code="assessment_cycle_source_empty",
                )
        lencioni_key = _cycle_questionnaire_key(
            cycle_questionnaire_keys,
            ("lencioni", "lencioni_en"),
            "lencioni",
        )
        distress_key = _cycle_questionnaire_key(
            cycle_questionnaire_keys,
            ("distress_drivers", "distress_drivers_en"),
            "distress_drivers",
        )
        pcm_key = _cycle_questionnaire_key(
            cycle_questionnaire_keys,
            ("pcm_base", "phase", "pcm_phase"),
            "pcm_base",
        )
        icare_key = _cycle_questionnaire_key(
            cycle_questionnaire_keys,
            ("boss_360", "boss_360_en", "icare"),
            "boss_360",
        )
        participants = await self.company_repository.list_participants(company_id)
        project_memberships = (
            await self.company_repository.list_project_memberships(company_id, project_id)
            if project_id is not None
            else []
        )
        if project_id is not None:
            participants = [participant for _membership, participant in project_memberships]
        teams = await self.assignment_repository.list_teams(company_id)
        existing_assignments = (
            []
            if source_cycle is not None
            else await self.assignment_repository.list_assignments(
                company_id,
                project_id,
                assessment_cycle_id,
            )
        )

        participant_by_id = {participant.id: participant for participant in participants}
        teams_by_name = {team.name.strip().casefold(): team for team in teams}
        if project_id is not None:
            hierarchy_participants = [
                _hierarchy_participant_from_membership(membership, participant)
                for membership, participant in project_memberships
            ]
        else:
            hierarchy_participants = [
                _hierarchy_participant_from_profile(participant) for participant in participants
            ]
        hierarchy = build_organization_hierarchy(hierarchy_participants)
        if hierarchy.ambiguous_name is not None:
            raise DomainError(
                f'Manager name "{hierarchy.ambiguous_name}" is ambiguous in the project roster.',
                code="manager_name_ambiguous",
            )
        direct_reports_by_manager = {
            manager_id: [direct_report.id for direct_report in direct_reports]
            for manager_id, direct_reports in hierarchy.direct_reports_by_manager_id.items()
        }
        manager_ids = set(hierarchy.leadership_ids)

        scopes: list[AssignmentPlanScopeResponse] = []
        plan_items: list[AssignmentPlanItemResponse] = []

        leadership_ids = sorted(
            manager_ids,
            key=lambda item: participant_by_id[item].full_name,
        )
        top_leader_ids = set(hierarchy.top_level_ids) & manager_ids
        leadership_team_leader_id = (
            next(iter(top_leader_ids)) if len(top_leader_ids) == 1 else None
        )
        if leadership_ids:
            leadership_team = teams_by_name.get("leadership")
            scopes.append(
                AssignmentPlanScopeResponse(
                    id="leadership",
                    name="Leadership",
                    type="leadership_team",
                    participant_ids=leadership_ids,
                )
            )
            for respondent_id in leadership_ids:
                plan_items.append(
                    _plan_team_assignment(
                        scope_id="leadership",
                        scope_name="Leadership",
                        scope_type="leadership_team",
                        respondent=participant_by_id[respondent_id],
                        questionnaire_key=lencioni_key,
                        team_id=leadership_team.id if leadership_team is not None else None,
                        team_name="Leadership",
                        team_type=TeamType.leadership,
                        team_member_ids=leadership_ids,
                        team_leader_id=leadership_team_leader_id,
                    )
                )

        for manager_id in sorted(manager_ids, key=lambda item: participant_by_id[item].full_name):
            manager = participant_by_id[manager_id]
            direct_report_ids = sorted(
                direct_reports_by_manager.get(manager_id, []),
                key=lambda item: participant_by_id[item].full_name,
            )
            direct_member_ids = [
                participant_id
                for participant_id in direct_report_ids
                if participant_id not in manager_ids
            ]
            if direct_member_ids:
                manager_team_ids = [manager_id, *direct_member_ids]
                manager_team_name = f"Echipa {manager.full_name}"
                persisted_team = teams_by_name.get(manager_team_name.casefold())

                scopes.append(
                    AssignmentPlanScopeResponse(
                        id=f"manager-team:{manager_id}",
                        name=manager_team_name,
                        type="manager_team",
                        participant_ids=manager_team_ids,
                    )
                )
                for respondent_id in direct_member_ids:
                    plan_items.append(
                        _plan_team_assignment(
                            scope_id=f"manager-team:{manager_id}",
                            scope_name=manager_team_name,
                            scope_type="manager_team",
                            respondent=participant_by_id[respondent_id],
                            questionnaire_key=lencioni_key,
                            team_id=persisted_team.id if persisted_team is not None else None,
                            team_name=manager_team_name,
                            team_type=TeamType.functional,
                            team_member_ids=manager_team_ids,
                            team_leader_id=manager_id,
                        )
                    )

            scopes.append(
                AssignmentPlanScopeResponse(
                    id=f"manager:{manager_id}",
                    name=manager.full_name,
                    type="manager",
                    participant_ids=[manager_id],
                )
            )
            plan_items.append(
                _plan_self_assignment(
                    scope_id=f"manager:{manager_id}",
                    scope_name=manager.full_name,
                    scope_type="manager",
                    respondent=manager,
                    questionnaire_key=distress_key,
                )
            )
            if (
                (cycle_questionnaire_keys is not None and pcm_key in cycle_questionnaire_keys)
                or not manager.pcm_base
                or not manager.pcm_phase
            ):
                plan_items.append(
                    _plan_self_assignment(
                        scope_id=f"manager:{manager_id}",
                        scope_name=manager.full_name,
                        scope_type="manager",
                        respondent=manager,
                        questionnaire_key=pcm_key,
                    )
                )
            leadership_peer_ids = [
                participant_id for participant_id in leadership_ids if participant_id != manager_id
            ]
            feedback_respondent_ids = [manager_id, *leadership_peer_ids, *direct_report_ids]
            for respondent_id in dict.fromkeys(feedback_respondent_ids):
                plan_items.append(
                    _plan_person_assignment(
                        scope_id=f"manager:{manager_id}",
                        scope_name=manager.full_name,
                        scope_type="manager",
                        respondent=participant_by_id[respondent_id],
                        target=manager,
                        questionnaire_key=icare_key,
                        visibility_policy=ResponseVisibilityPolicy.reviewed_anonymized,
                    )
                )

        for participant in participants:
            if participant.id in manager_ids:
                continue
            scopes.append(
                AssignmentPlanScopeResponse(
                    id=f"member:{participant.id}",
                    name=participant.full_name,
                    type="member",
                    participant_ids=[participant.id],
                )
            )

        if cycle_questionnaire_keys is not None:
            plan_items = [
                item for item in plan_items if item.questionnaire_key in cycle_questionnaire_keys
            ]
            populated_scope_ids = {item.scope_id for item in plan_items}
            scopes = [scope for scope in scopes if scope.id in populated_scope_ids]

        existing_lookup = {
            _assignment_match_key(
                assignment.respondent_profile_id,
                assignment.questionnaire_key,
                assignment.target_type,
                assignment.target_person_id,
                assignment.target_team_id,
            ): assignment.id
            for assignment in existing_assignments
        }
        for item in plan_items:
            existing_id = existing_lookup.get(
                _assignment_match_key(
                    item.respondent_profile_id,
                    item.questionnaire_key,
                    item.target_type,
                    item.target_person_id,
                    item.target_team_id,
                )
            )
            item.existing_assignment_id = existing_id
            item.selected = existing_id is None

        existing_count = sum(1 for item in plan_items if item.existing_assignment_id is not None)
        return AssignmentPlanResponse(
            project_id=project_id,
            assessment_cycle_id=assessment_cycle_id,
            source_cycle_id=source_cycle_id,
            scopes=scopes,
            assignments=plan_items,
            suggested_count=len(plan_items),
            existing_count=existing_count,
        )

    async def save_assignment_plan(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: AssignmentPlanSaveRequest,
    ) -> AssignmentPlanSaveResponse:
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(
            company_id,
            payload.project_id,
            allow_archived=False,
        )
        self._icare_hierarchy_cache.clear()
        cycle = await self._cycle_for_assignment_write(
            company_id,
            payload.project_id,
            payload.assessment_cycle_id,
        )
        saved: list[QuestionnaireAssignment] = []
        seen_assignment_ids: set[UUID] = set()
        created_count = 0
        existing_count = 0
        existing_assignments = await self.assignment_repository.list_assignments(
            company_id,
            payload.project_id,
            payload.assessment_cycle_id,
        )
        cycle_icare_leadership_ids = (
            await self._cycle_icare_leadership_ids(
                cycle,
                existing_assignments,
                payload.assignments,
            )
            if cycle is not None
            else set()
        )
        assignment_round_id = (
            min(
                (assignment.assignment_round_id for assignment in existing_assignments),
                key=str,
            )
            if existing_assignments
            else uuid4()
        )

        for item in payload.assignments:
            assignment, created = await self._create_or_get_planned_assignment(
                company_id,
                payload.project_id,
                item,
                assignment_round_id=assignment_round_id,
                cycle=cycle,
                cycle_icare_leadership_ids=cycle_icare_leadership_ids,
            )
            if assignment.id in seen_assignment_ids:
                continue
            seen_assignment_ids.add(assignment.id)
            saved.append(assignment)
            if created:
                created_count += 1
            else:
                existing_count += 1

        return AssignmentPlanSaveResponse(
            assignments=saved,
            created_count=created_count,
            existing_count=existing_count,
        )

    async def update_assignment_status(
        self,
        user_id: UUID,
        company_id: UUID,
        assignment_id: UUID,
        payload: AssignmentStatusUpdateRequest,
    ) -> QuestionnaireAssignment:
        await self._require_company_manager(user_id, company_id)
        assignment = await self.assignment_repository.get_assignment(
            company_id,
            assignment_id,
            for_update=True,
        )
        if assignment is None:
            raise DomainError("Assignment not found.", code="assignment_not_found")
        previous_status = assignment.status
        assignment.status = payload.status
        if (
            previous_status in COMPLETED_ASSIGNMENT_STATUSES
            and payload.status in EDITABLE_ASSIGNMENT_STATUSES
        ):
            await self.forms_repository.delete_submission_processing_for_assignment(
                assignment_id
            )
            await self.forms_repository.unlock_response_for_assignment(assignment_id)
            await self.scoring_repository.delete_by_assignment(assignment_id)
            await self.result_publication_service.reconcile_assignment(assignment_id)
            assignment.submitted_at = None
            assignment.validated_at = None
            assignment.scored_at = None
        _stamp_status_time(assignment)
        return assignment

    async def _create_or_get_planned_assignment(
        self,
        company_id: UUID,
        project_id: UUID | None,
        item: AssignmentPlanSaveItem,
        *,
        assignment_round_id: UUID,
        cycle: AssessmentCycle | None,
        cycle_icare_leadership_ids: set[UUID] | None = None,
    ) -> tuple[QuestionnaireAssignment, bool]:
        definition = await self._definition_for_cycle(cycle, item.questionnaire_key)
        await self._require_company_participant(company_id, item.respondent_profile_id)
        await self._require_project_participant(
            company_id,
            project_id,
            item.respondent_profile_id,
        )
        target_team_id = item.target_team_id
        if item.target_person_id is not None:
            await self._require_company_participant(company_id, item.target_person_id)
            await self._require_project_participant(
                company_id,
                project_id,
                item.target_person_id,
            )
        if item.target_type == AssignmentTargetType.team:
            target_team_id = await self._resolve_plan_team(
                company_id,
                project_id,
                item,
                cycle=cycle,
            )
        if cycle is not None:
            _require_cycle_icare_self_target(
                questionnaire_key=item.questionnaire_key.strip(),
                target_type=item.target_type,
                respondent_profile_id=item.respondent_profile_id,
                target_person_id=item.target_person_id,
                leadership_ids=cycle_icare_leadership_ids or set(),
            )

        existing = await self.assignment_repository.get_matching_assignment(
            company_id=company_id,
            project_id=project_id,
            respondent_profile_id=item.respondent_profile_id,
            questionnaire_key=item.questionnaire_key.strip(),
            target_type=item.target_type,
            target_person_id=(
                item.target_person_id if item.target_type == AssignmentTargetType.person else None
            ),
            target_team_id=(
                target_team_id if item.target_type == AssignmentTargetType.team else None
            ),
            assessment_cycle_id=cycle.id if cycle is not None else None,
        )
        if existing is not None:
            return existing, False

        payload = AssignmentCreateRequest(
            project_id=project_id,
            assessment_cycle_id=cycle.id if cycle is not None else None,
            respondent_profile_id=item.respondent_profile_id,
            questionnaire_key=item.questionnaire_key,
            target_type=item.target_type,
            target_person_id=(
                item.target_person_id if item.target_type == AssignmentTargetType.person else None
            ),
            target_team_id=(
                target_team_id if item.target_type == AssignmentTargetType.team else None
            ),
            visibility_policy=item.visibility_policy,
        )
        _validate_target_shape(payload)
        assignment = QuestionnaireAssignment(
            company_id=company_id,
            project_id=payload.project_id,
            assignment_round_id=assignment_round_id,
            assessment_cycle_id=payload.assessment_cycle_id,
            cycle_shape_guard=payload.assessment_cycle_id,
            respondent_profile_id=payload.respondent_profile_id,
            questionnaire_key=payload.questionnaire_key.strip(),
            questionnaire_definition_id=definition.id,
            target_type=payload.target_type,
            target_person_id=payload.target_person_id,
            target_team_id=payload.target_team_id,
            icare_cohort=await self._icare_cohort_for_assignment(
                company_id=company_id,
                project_id=project_id,
                cycle=cycle,
                questionnaire_key=payload.questionnaire_key,
                respondent_profile_id=payload.respondent_profile_id,
                target_type=payload.target_type,
                target_person_id=payload.target_person_id,
            ),
            access_mode=AssignmentAccessMode.account_link,
            status=AssignmentStatus.assigned,
            visibility_policy=payload.visibility_policy,
            due_at=cycle.due_at if cycle is not None else None,
        )
        if cycle is None:
            return await self.assignment_repository.add_assignment(assignment), True
        try:
            async with self.session.begin_nested():
                return await self.assignment_repository.add_assignment(assignment), True
        except IntegrityError:
            existing = await self.assignment_repository.get_matching_assignment(
                company_id=company_id,
                project_id=project_id,
                respondent_profile_id=item.respondent_profile_id,
                questionnaire_key=item.questionnaire_key.strip(),
                target_type=item.target_type,
                target_person_id=(
                    item.target_person_id
                    if item.target_type == AssignmentTargetType.person
                    else None
                ),
                target_team_id=(
                    target_team_id if item.target_type == AssignmentTargetType.team else None
                ),
                assessment_cycle_id=cycle.id,
            )
            if existing is None:
                raise DomainError(
                    "The assignment plan changed while it was being saved. Try again.",
                    code="assessment_cycle_assignment_conflict",
                ) from None
            return existing, False

    async def _icare_cohort_for_assignment(
        self,
        *,
        company_id: UUID,
        project_id: UUID | None,
        cycle: AssessmentCycle | None,
        questionnaire_key: str,
        respondent_profile_id: UUID,
        target_type: AssignmentTargetType,
        target_person_id: UUID | None,
    ) -> IcareCohort | None:
        if cycle is None or questionnaire_key.strip() not in ICARE_QUESTIONNAIRE_KEYS:
            return None
        if target_type == AssignmentTargetType.self_assessment:
            return IcareCohort.self
        if target_type != AssignmentTargetType.person or target_person_id is None:
            raise DomainError(
                "iCARE assignments must target a leadership member.",
                code="icare_cohort_unavailable",
            )
        if respondent_profile_id == target_person_id:
            return IcareCohort.self

        cache_key = (company_id, project_id)
        hierarchy = self._icare_hierarchy_cache.get(cache_key)
        if hierarchy is None:
            if project_id is not None:
                rows = await self.company_repository.list_project_memberships(
                    company_id,
                    project_id,
                )
                hierarchy_participants = [
                    _hierarchy_participant_from_membership(membership, participant)
                    for membership, participant in rows
                ]
            else:
                hierarchy_participants = [
                    _hierarchy_participant_from_profile(participant)
                    for participant in await self.company_repository.list_participants(company_id)
                ]
            hierarchy = build_organization_hierarchy(hierarchy_participants)
            self._icare_hierarchy_cache[cache_key] = hierarchy
        if hierarchy.ambiguous_name is not None:
            raise DomainError(
                "Correct the ambiguous reporting lines before assigning iCARE.",
                code="icare_cohort_unavailable",
            )
        if target_person_id not in hierarchy.leadership_ids:
            raise DomainError(
                "iCARE assignments must target a leadership member.",
                code="icare_cohort_unavailable",
            )
        if respondent_profile_id in hierarchy.leadership_ids:
            return IcareCohort.leadership_peers
        direct_report_ids = {
            participant.id
            for participant in hierarchy.direct_reports_by_manager_id.get(target_person_id, [])
        }
        if respondent_profile_id in direct_report_ids:
            return IcareCohort.direct_team
        raise DomainError(
            "The iCARE feedback relationship is not part of this project organigram.",
            code="icare_cohort_unavailable",
        )

    async def _resolve_plan_team(
        self,
        company_id: UUID,
        project_id: UUID | None,
        item: AssignmentPlanSaveItem,
        *,
        cycle: AssessmentCycle | None,
    ) -> UUID:
        if item.target_team_id is not None:
            team = await self.assignment_repository.get_team(company_id, item.target_team_id)
            if team is None:
                raise DomainError("Target team not found in this company.", code="team_not_found")
            if cycle is None:
                await self._require_project_team_members(company_id, project_id, team.id)
            target_team_id = team.id
        else:
            team_name = (item.target_team_name or "").strip()
            if not team_name:
                raise DomainError("Team target is missing.", code="team_target_missing")
            team = await self.assignment_repository.get_team_by_name(company_id, team_name)
            if team is None:
                team = await self.assignment_repository.add_team(
                    Team(
                        company_id=company_id,
                        name=team_name,
                        type=item.target_team_type or TeamType.functional,
                    )
                )
            target_team_id = team.id

        if cycle is not None:
            await self._snapshot_cycle_team_membership(cycle, target_team_id, item)
            return target_team_id

        for member_id in dict.fromkeys(item.target_team_member_ids):
            await self._require_company_participant(company_id, member_id)
            await self._require_project_participant(company_id, project_id, member_id)
            existing = await self.assignment_repository.get_team_membership(
                target_team_id, member_id
            )
            if existing is not None:
                continue
            await self.assignment_repository.add_team_membership(
                TeamMembership(
                    team_id=team.id,
                    participant_profile_id=member_id,
                    role=TeamMembershipRole.leader
                    if member_id == item.target_team_leader_id
                    else TeamMembershipRole.member,
                )
            )
        return target_team_id

    async def _cycle_icare_leadership_ids(
        self,
        cycle: AssessmentCycle,
        persisted_assignments: list[QuestionnaireAssignment],
        planned_assignments: list[AssignmentPlanSaveItem] | None = None,
    ) -> set[UUID]:
        leadership_ids = (
            await self.assignment_repository.list_cycle_leadership_participant_ids(
                cycle.id
            )
        )
        for assignment in [*persisted_assignments, *(planned_assignments or [])]:
            questionnaire_key = assignment.questionnaire_key.strip()
            target_person_id = assignment.target_person_id
            if (
                questionnaire_key in ICARE_QUESTIONNAIRE_KEYS
                and assignment.target_type == AssignmentTargetType.person
                and target_person_id is not None
                and target_person_id != assignment.respondent_profile_id
            ):
                leadership_ids.add(target_person_id)
        return leadership_ids

    async def _snapshot_cycle_team_membership(
        self,
        cycle: AssessmentCycle,
        team_id: UUID,
        item: AssignmentPlanSaveItem,
    ) -> None:
        member_ids = list(dict.fromkeys(item.target_team_member_ids))
        if not member_ids:
            raise DomainError(
                "The cycle team must include at least one participant.",
                code="assessment_cycle_team_members_required",
            )
        expected = {
            member_id: (
                TeamMembershipRole.leader
                if member_id == item.target_team_leader_id
                else TeamMembershipRole.member
            )
            for member_id in member_ids
        }
        existing = await self.assignment_repository.list_cycle_team_memberships(
            cycle.id,
            team_id,
        )
        if existing:
            actual = {membership.participant_profile_id: membership.role for membership in existing}
            removed_members = set(actual.keys()) - set(expected.keys())
            if removed_members:
                raise DomainError(
                    "Cannot remove team members from an assessment cycle team snapshot.",
                    code="assessment_cycle_team_member_removed",
                )
            for member_id, actual_role in actual.items():
                if expected[member_id] != actual_role:
                    raise DomainError(
                        "Cannot change team member roles in an assessment cycle team snapshot.",
                        code="assessment_cycle_team_role_changed",
                    )
            added_member_ids = [m_id for m_id in member_ids if m_id not in actual]
            if not added_member_ids:
                return
            for member_id in added_member_ids:
                await self._require_company_participant(cycle.company_id, member_id)
                await self._require_project_participant(
                    cycle.company_id,
                    cycle.project_id,
                    member_id,
                )
            await self.assignment_repository.add_cycle_team_memberships(
                [
                    AssessmentCycleTeamMembership(
                        assessment_cycle_id=cycle.id,
                        team_id=team_id,
                        participant_profile_id=member_id,
                        role=expected[member_id],
                    )
                    for member_id in added_member_ids
                ]
            )
            return

        for member_id in member_ids:
            await self._require_company_participant(cycle.company_id, member_id)
            await self._require_project_participant(
                cycle.company_id,
                cycle.project_id,
                member_id,
            )
        await self.assignment_repository.add_cycle_team_memberships(
            [
                AssessmentCycleTeamMembership(
                    assessment_cycle_id=cycle.id,
                    team_id=team_id,
                    participant_profile_id=member_id,
                    role=role,
                )
                for member_id, role in expected.items()
            ]
        )

    async def _snapshot_existing_team_for_cycle(
        self,
        cycle: AssessmentCycle,
        team_id: UUID,
    ) -> None:
        existing_snapshot = await self.assignment_repository.list_cycle_team_memberships(
            cycle.id,
            team_id,
        )
        if existing_snapshot:
            return
        memberships = await self.assignment_repository.list_team_memberships(team_id)
        if not memberships:
            raise DomainError(
                "The team must include at least one participant.",
                code="assessment_cycle_team_members_required",
            )
        for membership in memberships:
            await self._require_project_participant(
                cycle.company_id,
                cycle.project_id,
                membership.participant_profile_id,
            )
        await self.assignment_repository.add_cycle_team_memberships(
            [
                AssessmentCycleTeamMembership(
                    assessment_cycle_id=cycle.id,
                    team_id=team_id,
                    participant_profile_id=membership.participant_profile_id,
                    role=membership.role,
                )
                for membership in memberships
            ]
        )

    async def _require_company_manager(self, user_id: UUID, company_id: UUID) -> None:
        if await self.company_repository.get_company(company_id) is None:
            raise DomainError("Company not found.", code="company_not_found")

        membership = await self.company_repository.get_membership(company_id, user_id)
        if membership is not None and membership.role in {
            CompanyMembershipRole.owner,
            CompanyMembershipRole.trainer,
        }:
            return

        raise DomainError(
            "You do not have access to manage assignments for this company.",
            code="company_access_denied",
        )

    async def _require_company_participant(
        self,
        company_id: UUID,
        participant_profile_id: UUID,
    ) -> None:
        participant = await self.company_repository.get_participant_by_id(participant_profile_id)
        if participant is None or participant.company_id != company_id:
            raise DomainError(
                "Participant not found in this company.",
                code="participant_not_found",
            )

    async def _require_company_project(
        self,
        company_id: UUID,
        project_id: UUID | None,
        *,
        allow_archived: bool = True,
    ) -> None:
        if project_id is None:
            return
        project = await self.company_repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError(
                "Project not found in this company.",
                code="project_not_found",
            )
        if not allow_archived and project.status == CompanyProjectStatus.archived:
            raise DomainError(
                "Restore the project before changing its data.",
                code="project_restore_required",
            )

    async def _require_project_participant(
        self,
        company_id: UUID,
        project_id: UUID | None,
        participant_profile_id: UUID,
    ) -> None:
        if project_id is None:
            return
        membership = await self.company_repository.get_project_membership(
            project_id,
            participant_profile_id,
        )
        if membership is None or membership.company_id != company_id or not membership.active:
            raise DomainError(
                "Participant is not active in this project.",
                code="participant_not_in_project",
            )

    async def _require_project_team_members(
        self,
        company_id: UUID,
        project_id: UUID | None,
        team_id: UUID,
    ) -> None:
        if project_id is None:
            return
        memberships = await self.assignment_repository.list_team_memberships(team_id)
        for membership in memberships:
            await self._require_project_participant(
                company_id,
                project_id,
                membership.participant_profile_id,
            )

    async def _require_active_questionnaire_definition(
        self,
        questionnaire_key: str,
    ) -> QuestionnaireDefinition:
        definition = await self.forms_repository.get_definition(questionnaire_key)
        if definition is not None:
            return definition

        raise DomainError(
            "Questionnaire definition not found.",
            code="definition_not_found",
        )

    async def _definition_for_cycle(
        self,
        cycle: AssessmentCycle | None,
        questionnaire_key: str,
    ) -> QuestionnaireDefinition:
        normalized_key = questionnaire_key.strip()
        if cycle is None:
            return await self._require_active_questionnaire_definition(normalized_key)
        questionnaires = await self.assignment_repository.list_assessment_cycle_questionnaires(
            cycle.id
        )
        pinned = next(
            (item for item in questionnaires if item.questionnaire_key == normalized_key),
            None,
        )
        if pinned is None:
            if self._is_initial_draft_cycle(cycle):
                definition = await self._require_active_questionnaire_definition(normalized_key)
                await self.assignment_repository.add_assessment_cycle_questionnaires(
                    [
                        AssessmentCycleQuestionnaire(
                            assessment_cycle_id=cycle.id,
                            questionnaire_definition_id=definition.id,
                            questionnaire_key=normalized_key,
                            display_order=len(questionnaires),
                        )
                    ]
                )
                return definition
            raise DomainError(
                "Questionnaire is not part of this assessment cycle.",
                code="assessment_cycle_questionnaire_not_found",
            )
        definition = await self.forms_repository.get_definition_by_id(
            pinned.questionnaire_definition_id
        )
        if definition is None:
            raise DomainError(
                "Pinned questionnaire definition not found.",
                code="definition_not_found",
            )
        return definition

    @staticmethod
    def _is_initial_draft_cycle(cycle: AssessmentCycle) -> bool:
        return (
            cycle.sequence == 1
            and cycle.source_cycle_id is None
            and cycle.status == AssessmentCycleStatus.draft
        )

    async def _optional_assessment_cycle(
        self,
        company_id: UUID,
        project_id: UUID | None,
        assessment_cycle_id: UUID | None,
        *,
        for_update: bool = False,
    ) -> AssessmentCycle | None:
        if assessment_cycle_id is None:
            return None
        if project_id is None:
            raise DomainError(
                "A project is required for an assessment cycle.",
                code="assessment_cycle_project_required",
            )
        return await self._require_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
            for_update=for_update,
        )

    async def _cycle_for_assignment_write(
        self,
        company_id: UUID,
        project_id: UUID | None,
        assessment_cycle_id: UUID | None,
    ) -> AssessmentCycle | None:
        cycle = await self._optional_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
            for_update=True,
        )
        if cycle is not None:
            self._require_open_cycle_for_assignment_write(cycle)
        return cycle

    async def _require_assessment_cycle(
        self,
        company_id: UUID,
        project_id: UUID,
        assessment_cycle_id: UUID,
        *,
        for_update: bool = False,
    ) -> AssessmentCycle:
        if for_update:
            await self._require_company_project(
                company_id,
                project_id,
                allow_archived=False,
            )
        cycle = await self.assignment_repository.get_assessment_cycle(
            company_id,
            project_id,
            assessment_cycle_id,
            for_update=for_update,
        )
        if cycle is None:
            raise DomainError(
                "Assessment cycle not found in this project.",
                code="assessment_cycle_not_found",
            )
        return cycle

    @staticmethod
    def _require_open_cycle_for_assignment_write(cycle: AssessmentCycle) -> None:
        if cycle.status == AssessmentCycleStatus.closed:
            raise DomainError(
                "Assessment cycle is closed and cannot be changed.",
                code="assessment_cycle_closed",
            )
        if cycle.status not in (AssessmentCycleStatus.draft, AssessmentCycleStatus.active):
            raise DomainError(
                "Only an open assessment cycle can accept assignment changes.",
                code="assessment_cycle_not_open",
            )

    @staticmethod
    def _require_draft_cycle(cycle: AssessmentCycle) -> None:
        if cycle.status != AssessmentCycleStatus.draft:
            raise DomainError(
                "Only a draft assessment cycle can be changed.",
                code="assessment_cycle_not_draft",
            )

    async def _assessment_cycle_response(
        self,
        cycle: AssessmentCycle,
        *,
        questionnaires: list[AssessmentCycleQuestionnaire] | None = None,
    ) -> AssessmentCycleResponse:
        pinned = questionnaires
        if pinned is None:
            pinned = await self.assignment_repository.list_assessment_cycle_questionnaires(cycle.id)
        return AssessmentCycleResponse(
            id=cycle.id,
            company_id=cycle.company_id,
            project_id=cycle.project_id,
            sequence=cycle.sequence,
            name=cycle.name,
            status=cycle.status,
            source_cycle_id=cycle.source_cycle_id,
            starts_at=cycle.starts_at,
            due_at=cycle.due_at,
            closed_at=cycle.closed_at,
            created_by_user_id=cycle.created_by_user_id,
            created_at=cycle.created_at,
            updated_at=cycle.updated_at,
            questionnaires=[
                AssessmentCycleQuestionnaireResponse.model_validate(item) for item in pinned
            ],
        )


def _cycle_questionnaire_key(
    cycle_keys: set[str] | None,
    candidates: tuple[str, ...],
    fallback: str,
) -> str:
    if cycle_keys is not None:
        for candidate in candidates:
            if candidate in cycle_keys:
                return candidate
    return fallback


def _validate_target_shape(payload: AssignmentCreateRequest) -> None:
    if payload.target_type == AssignmentTargetType.self_assessment:
        valid = payload.target_person_id is None and payload.target_team_id is None
    elif payload.target_type == AssignmentTargetType.person:
        valid = payload.target_person_id is not None and payload.target_team_id is None
    else:
        valid = payload.target_team_id is not None and payload.target_person_id is None
    if not valid:
        raise DomainError("Assignment target does not match target type.", code="invalid_target")


def _require_cycle_icare_self_target(
    *,
    questionnaire_key: str,
    target_type: AssignmentTargetType,
    respondent_profile_id: UUID,
    target_person_id: UUID | None,
    leadership_ids: set[UUID],
) -> None:
    is_self_target = target_type == AssignmentTargetType.self_assessment or (
        target_type == AssignmentTargetType.person
        and target_person_id == respondent_profile_id
    )
    if (
        questionnaire_key in ICARE_QUESTIONNAIRE_KEYS
        and is_self_target
        and respondent_profile_id not in leadership_ids
    ):
        raise DomainError(
            "Self-evaluation iCARE is available only for this cycle's leadership cohort.",
            code="assessment_cycle_icare_self_target_not_leadership",
        )


def _validate_cycle_dates(
    starts_at: datetime | None,
    due_at: datetime | None,
) -> None:
    if starts_at is not None and due_at is not None and due_at < starts_at:
        raise DomainError(
            "The due date must be after the start date.",
            code="assessment_cycle_invalid_dates",
            details={"field": "due_at"},
        )


def _normalize_cycle_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise DomainError(
            "Assessment cycle name is required.",
            code="assessment_cycle_name_required",
            details={"field": "name"},
        )
    return name


def _stamp_status_time(assignment: QuestionnaireAssignment) -> None:
    now = datetime.now(UTC)
    if assignment.status == AssignmentStatus.invited and assignment.invited_at is None:
        assignment.invited_at = now
    elif assignment.status == AssignmentStatus.started and assignment.started_at is None:
        assignment.started_at = now
    elif assignment.status == AssignmentStatus.submitted and assignment.submitted_at is None:
        assignment.submitted_at = now
    elif assignment.status == AssignmentStatus.validated and assignment.validated_at is None:
        assignment.validated_at = now
    elif assignment.status == AssignmentStatus.scored and assignment.scored_at is None:
        assignment.scored_at = now


def _assignment_match_key(
    respondent_profile_id: UUID,
    questionnaire_key: str,
    target_type: AssignmentTargetType,
    target_person_id: UUID | None,
    target_team_id: UUID | None,
) -> tuple[UUID, str, AssignmentTargetType, UUID | None, UUID | None]:
    return (
        respondent_profile_id,
        questionnaire_key,
        target_type,
        target_person_id if target_type == AssignmentTargetType.person else None,
        target_team_id if target_type == AssignmentTargetType.team else None,
    )


def _hierarchy_participant_from_profile(participant: ParticipantProfile) -> HierarchyParticipant:
    return HierarchyParticipant(
        id=participant.id,
        full_name=participant.full_name,
        reports_to_name=participant.reports_to_name,
        role_group=participant.role_group,
        user_id=participant.user_id,
    )


def _hierarchy_participant_from_membership(
    membership: ProjectMembership,
    participant: ParticipantProfile,
) -> HierarchyParticipant:
    return HierarchyParticipant(
        id=participant.id,
        full_name=participant.full_name,
        reports_to_name=membership.reports_to_name,
        role_group=membership.role_group,
        user_id=participant.user_id,
    )


def _plan_self_assignment(
    *,
    scope_id: str,
    scope_name: str,
    scope_type: str,
    respondent,
    questionnaire_key: str,
) -> AssignmentPlanItemResponse:
    return AssignmentPlanItemResponse(
        key=f"{scope_id}:{respondent.id}:{questionnaire_key}:self",
        scope_id=scope_id,
        scope_name=scope_name,
        scope_type=scope_type,
        respondent_profile_id=respondent.id,
        respondent_name=respondent.full_name,
        questionnaire_key=questionnaire_key,
        target_type=AssignmentTargetType.self_assessment,
    )


def _plan_person_assignment(
    *,
    scope_id: str,
    scope_name: str,
    scope_type: str,
    respondent,
    target,
    questionnaire_key: str,
    visibility_policy: ResponseVisibilityPolicy,
) -> AssignmentPlanItemResponse:
    return AssignmentPlanItemResponse(
        key=f"{scope_id}:{respondent.id}:{questionnaire_key}:person:{target.id}",
        scope_id=scope_id,
        scope_name=scope_name,
        scope_type=scope_type,
        respondent_profile_id=respondent.id,
        respondent_name=respondent.full_name,
        questionnaire_key=questionnaire_key,
        target_type=AssignmentTargetType.person,
        target_person_id=target.id,
        target_person_name=target.full_name,
        visibility_policy=visibility_policy,
    )


def _plan_team_assignment(
    *,
    scope_id: str,
    scope_name: str,
    scope_type: str,
    respondent,
    questionnaire_key: str,
    team_id: UUID | None,
    team_name: str,
    team_type: TeamType,
    team_member_ids: list[UUID],
    team_leader_id: UUID | None,
) -> AssignmentPlanItemResponse:
    return AssignmentPlanItemResponse(
        key=f"{scope_id}:{respondent.id}:{questionnaire_key}:team:{team_id or team_name}",
        scope_id=scope_id,
        scope_name=scope_name,
        scope_type=scope_type,
        respondent_profile_id=respondent.id,
        respondent_name=respondent.full_name,
        questionnaire_key=questionnaire_key,
        target_type=AssignmentTargetType.team,
        target_team_id=team_id,
        target_team_name=team_name,
        target_team_type=team_type,
        target_team_member_ids=team_member_ids,
        target_team_leader_id=team_leader_id,
    )
