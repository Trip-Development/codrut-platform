from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
)
from codrut.modules.assignments.repository import AssignmentRepository
from codrut.modules.assignments.schemas import (
    AssignmentCreateRequest,
    AssignmentStatusUpdateRequest,
    TeamCreateRequest,
    TeamMembershipCreateRequest,
)
from codrut.modules.companies.models import CompanyMembershipRole
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.repository import IdentityRepository


class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.assignment_repository = AssignmentRepository(session)
        self.company_repository = CompanyRepository(session)
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
        return await self.assignment_repository.add_team_membership(
            TeamMembership(
                team_id=team_id,
                participant_profile_id=payload.participant_profile_id,
                role=payload.role,
            )
        )

    async def create_assignment(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: AssignmentCreateRequest,
    ) -> QuestionnaireAssignment:
        await self._require_company_manager(user_id, company_id)
        _validate_target_shape(payload)
        return await self.assignment_repository.add_assignment(
            QuestionnaireAssignment(
                company_id=company_id,
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

    async def list_assignments(
        self,
        user_id: UUID,
        company_id: UUID,
    ) -> list[QuestionnaireAssignment]:
        await self._require_company_manager(user_id, company_id)
        return await self.assignment_repository.list_assignments(company_id)

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
