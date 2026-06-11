from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    ResponseVisibilityPolicy,
    Team,
    TeamMembership,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.assignments.repository import AssignmentRepository
from codrut.modules.assignments.schemas import (
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
from codrut.modules.companies.models import CompanyMembershipRole
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.forms.definitions import get_approved_questionnaire_definition
from codrut.modules.forms.repository import FormsRepository
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.repository import IdentityRepository


class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.assignment_repository = AssignmentRepository(session)
        self.company_repository = CompanyRepository(session)
        self.forms_repository = FormsRepository(session)
        self.identity_repository = IdentityRepository(session)

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

    async def create_assignment(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: AssignmentCreateRequest,
    ) -> QuestionnaireAssignment:
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, payload.project_id)
        _validate_target_shape(payload)
        questionnaire_key = payload.questionnaire_key.strip()
        await self._require_active_questionnaire_definition(questionnaire_key)
        await self._require_company_participant(company_id, payload.respondent_profile_id)
        if payload.target_person_id is not None:
            await self._require_company_participant(company_id, payload.target_person_id)
        if payload.target_team_id is not None:
            team = await self.assignment_repository.get_team(company_id, payload.target_team_id)
            if team is None:
                raise DomainError("Target team not found in this company.", code="team_not_found")
        return await self.assignment_repository.add_assignment(
            QuestionnaireAssignment(
                company_id=company_id,
                project_id=payload.project_id,
                respondent_profile_id=payload.respondent_profile_id,
                questionnaire_key=questionnaire_key,
                target_type=payload.target_type,
                target_person_id=payload.target_person_id,
                target_team_id=payload.target_team_id,
                access_mode=AssignmentAccessMode.account_link,
                status=AssignmentStatus.assigned,
                visibility_policy=payload.visibility_policy,
            )
        )

    async def list_assignments(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID | None = None,
    ) -> list[QuestionnaireAssignment]:
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, project_id)
        return await self.assignment_repository.list_assignments(company_id, project_id)

    async def build_default_assignment_plan(
        self,
        user_id: UUID,
        company_id: UUID,
        project_id: UUID | None = None,
    ) -> AssignmentPlanResponse:
        await self._require_company_manager(user_id, company_id)
        await self._require_company_project(company_id, project_id)
        participants = await self.company_repository.list_participants(company_id)
        teams = await self.assignment_repository.list_teams(company_id)
        relationships = await self.company_repository.list_reporting_relationships(company_id)
        existing_assignments = await self.assignment_repository.list_assignments(
            company_id,
            project_id,
        )

        participant_by_id = {participant.id: participant for participant in participants}
        teams_by_name = {team.name.strip().casefold(): team for team in teams}
        direct_reports_by_manager: dict[UUID, list[UUID]] = {}
        for relationship in relationships:
            if (
                relationship.manager_profile_id not in participant_by_id
                or relationship.participant_profile_id not in participant_by_id
            ):
                continue
            direct_reports_by_manager.setdefault(relationship.manager_profile_id, []).append(
                relationship.participant_profile_id
            )

        manager_ids = set(direct_reports_by_manager)
        manager_ids.update(
            participant.id
            for participant in participants
            if (participant.role_group or "").casefold() == "leadership"
        )

        scopes: list[AssignmentPlanScopeResponse] = []
        plan_items: list[AssignmentPlanItemResponse] = []

        leadership_ids = [
            participant.id
            for participant in participants
            if (participant.role_group or "").casefold() == "leadership"
        ]
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
                        questionnaire_key="lencioni",
                        team_id=leadership_team.id if leadership_team is not None else None,
                        team_name="Leadership",
                        team_type=TeamType.leadership,
                        team_member_ids=leadership_ids,
                        team_leader_id=None,
                    )
                )

        for manager_id in sorted(manager_ids, key=lambda item: participant_by_id[item].full_name):
            manager = participant_by_id[manager_id]
            direct_report_ids = sorted(
                direct_reports_by_manager.get(manager_id, []),
                key=lambda item: participant_by_id[item].full_name,
            )
            if direct_report_ids:
                manager_team_ids = [manager_id, *direct_report_ids]
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
                for respondent_id in manager_team_ids:
                    plan_items.append(
                        _plan_team_assignment(
                            scope_id=f"manager-team:{manager_id}",
                            scope_name=manager_team_name,
                            scope_type="manager_team",
                            respondent=participant_by_id[respondent_id],
                            questionnaire_key="lencioni",
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
                    questionnaire_key="distress_drivers",
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
                        questionnaire_key="boss_360",
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
        await self._require_company_project(company_id, payload.project_id)
        saved: list[QuestionnaireAssignment] = []
        seen_assignment_ids: set[UUID] = set()
        created_count = 0
        existing_count = 0

        for item in payload.assignments:
            assignment, created = await self._create_or_get_planned_assignment(
                company_id,
                payload.project_id,
                item,
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
        assignment = await self.assignment_repository.get_assignment(company_id, assignment_id)
        if assignment is None:
            raise DomainError("Assignment not found.", code="assignment_not_found")
        assignment.status = payload.status
        _stamp_status_time(assignment)
        return assignment

    async def _create_or_get_planned_assignment(
        self,
        company_id: UUID,
        project_id: UUID | None,
        item: AssignmentPlanSaveItem,
    ) -> tuple[QuestionnaireAssignment, bool]:
        await self._require_active_questionnaire_definition(item.questionnaire_key)
        await self._require_company_participant(company_id, item.respondent_profile_id)
        target_team_id = item.target_team_id
        if item.target_person_id is not None:
            await self._require_company_participant(company_id, item.target_person_id)
        if item.target_type == AssignmentTargetType.team:
            target_team_id = await self._resolve_plan_team(company_id, item)

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
        )
        if existing is not None:
            return existing, False

        payload = AssignmentCreateRequest(
            project_id=project_id,
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
        assignment = await self.assignment_repository.add_assignment(
            QuestionnaireAssignment(
                company_id=company_id,
                project_id=payload.project_id,
                respondent_profile_id=payload.respondent_profile_id,
                questionnaire_key=payload.questionnaire_key.strip(),
                target_type=payload.target_type,
                target_person_id=payload.target_person_id,
                target_team_id=payload.target_team_id,
                access_mode=AssignmentAccessMode.account_link,
                status=AssignmentStatus.assigned,
                visibility_policy=payload.visibility_policy,
            )
        )
        return assignment, True

    async def _resolve_plan_team(
        self,
        company_id: UUID,
        item: AssignmentPlanSaveItem,
    ) -> UUID:
        if item.target_team_id is not None:
            team = await self.assignment_repository.get_team(company_id, item.target_team_id)
            if team is None:
                raise DomainError("Target team not found in this company.", code="team_not_found")
            return team.id

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

        for member_id in dict.fromkeys(item.target_team_member_ids):
            await self._require_company_participant(company_id, member_id)
            existing = await self.assignment_repository.get_team_membership(team.id, member_id)
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
        return team.id

    async def _require_company_manager(self, user_id: UUID, company_id: UUID) -> None:
        if await self.company_repository.get_company(company_id) is None:
            raise DomainError("Company not found.", code="company_not_found")

        membership = await self.company_repository.get_membership(company_id, user_id)
        if membership is not None and membership.role in {
            CompanyMembershipRole.owner,
            CompanyMembershipRole.trainer,
        }:
            return

        user = await self.identity_repository.get_user_by_id(user_id)
        if user is not None and user.role == UserRole.trainer:
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
    ) -> None:
        if project_id is None:
            return
        project = await self.company_repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError(
                "Project not found in this company.",
                code="project_not_found",
            )

    async def _require_active_questionnaire_definition(self, questionnaire_key: str) -> None:
        definition = await self.forms_repository.get_definition(questionnaire_key)
        if definition is not None:
            return

        if await self.forms_repository.get_latest_version(questionnaire_key) > 0:
            raise DomainError(
                "Questionnaire definition not found.",
                code="definition_not_found",
            )

        try:
            get_approved_questionnaire_definition(questionnaire_key)
        except KeyError as exc:
            raise DomainError(
                "Questionnaire definition not found.",
                code="definition_not_found",
            ) from exc


def _validate_target_shape(payload: AssignmentCreateRequest) -> None:
    if payload.target_type == AssignmentTargetType.self_assessment:
        valid = payload.target_person_id is None and payload.target_team_id is None
    elif payload.target_type == AssignmentTargetType.person:
        valid = payload.target_person_id is not None and payload.target_team_id is None
    else:
        valid = payload.target_team_id is not None and payload.target_person_id is None
    if not valid:
        raise DomainError("Assignment target does not match target type.", code="invalid_target")


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
