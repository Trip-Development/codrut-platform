from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.companies.models import CompanyProject, ParticipantProfile
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
    SubmissionProcessingJob,
    SubmissionProcessingStatus,
)
from codrut.modules.identity.models import User, UserAccountType


class FormsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_assignment_for_user(
        self,
        assignment_id: UUID,
        user_id: UUID,
        *,
        participant_profile_id: UUID | None = None,
        project_id: UUID | None = None,
        cycle_id: UUID | None = None,
        allowed_assignment_ids: tuple[UUID, ...] | None = None,
        for_update: bool = False,
    ) -> QuestionnaireAssignment | None:
        statement = (
            select(QuestionnaireAssignment)
            .join(
                ParticipantProfile,
                ParticipantProfile.id == QuestionnaireAssignment.respondent_profile_id,
            )
            .where(QuestionnaireAssignment.id == assignment_id)
            .where(ParticipantProfile.user_id == user_id)
        )
        if participant_profile_id is not None:
            statement = statement.where(
                QuestionnaireAssignment.respondent_profile_id == participant_profile_id
            )
        if project_id is not None:
            statement = statement.where(QuestionnaireAssignment.project_id == project_id)
        if cycle_id is not None:
            statement = statement.where(QuestionnaireAssignment.assessment_cycle_id == cycle_id)
        if allowed_assignment_ids is not None:
            if assignment_id not in allowed_assignment_ids:
                return None
            statement = statement.where(QuestionnaireAssignment.id.in_(allowed_assignment_ids))
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_assignments_for_user_by_key(
        self,
        user_id: UUID,
        questionnaire_key: str,
        *,
        version: int | None = None,
        participant_profile_id: UUID | None = None,
        project_id: UUID | None = None,
        cycle_id: UUID | None = None,
        allowed_assignment_ids: tuple[UUID, ...] | None = None,
    ) -> list[QuestionnaireAssignment]:
        statement = (
            select(QuestionnaireAssignment)
            .join(
                ParticipantProfile,
                ParticipantProfile.id == QuestionnaireAssignment.respondent_profile_id,
            )
            .where(ParticipantProfile.user_id == user_id)
            .where(QuestionnaireAssignment.questionnaire_key == questionnaire_key)
            .order_by(QuestionnaireAssignment.created_at.desc())
        )
        if participant_profile_id is not None:
            statement = statement.where(
                QuestionnaireAssignment.respondent_profile_id == participant_profile_id
            )
        if project_id is not None:
            statement = statement.where(QuestionnaireAssignment.project_id == project_id)
        if cycle_id is not None:
            statement = statement.where(QuestionnaireAssignment.assessment_cycle_id == cycle_id)
        if allowed_assignment_ids is not None:
            if not allowed_assignment_ids:
                return []
            statement = statement.where(QuestionnaireAssignment.id.in_(allowed_assignment_ids))
        if version is not None:
            statement = statement.join(
                QuestionnaireDefinition,
                QuestionnaireDefinition.id == QuestionnaireAssignment.questionnaire_definition_id,
            ).where(QuestionnaireDefinition.version == version)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_assignment_by_id(
        self,
        assignment_id: UUID,
        *,
        for_update: bool = False,
    ) -> QuestionnaireAssignment | None:
        statement = select(QuestionnaireAssignment).where(
            QuestionnaireAssignment.id == assignment_id
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_permanent_participants_for_user(self, user_id: UUID) -> list[ParticipantProfile]:
        result = await self.session.execute(
            select(ParticipantProfile)
            .join(User, User.id == ParticipantProfile.user_id)
            .where(ParticipantProfile.user_id == user_id)
            .where(User.account_type == UserAccountType.registered)
        )
        return list(result.scalars().all())

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
            .order_by(QuestionnaireAssignment.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_response_by_assignment(
        self,
        assignment_id: UUID,
        *,
        for_update: bool = False,
    ) -> QuestionnaireResponse | None:
        statement = select(QuestionnaireResponse).where(
            QuestionnaireResponse.assignment_id == assignment_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def enqueue_submission_processing(
        self,
        assignment_id: UUID,
        *,
        now: datetime,
    ) -> SubmissionProcessingJob:
        result = await self.session.execute(
            select(SubmissionProcessingJob)
            .where(SubmissionProcessingJob.assignment_id == assignment_id)
            .with_for_update()
        )
        job = result.scalar_one_or_none()
        if job is None:
            job = SubmissionProcessingJob(
                id=uuid4(),
                assignment_id=assignment_id,
                status=SubmissionProcessingStatus.queued,
                attempt_count=0,
                max_attempts=5,
                next_attempt_at=now,
            )
            self.session.add(job)
        elif job.status != SubmissionProcessingStatus.processing:
            job.status = SubmissionProcessingStatus.queued
            job.attempt_count = 0
            job.next_attempt_at = now
            job.lease_token = None
            job.lease_expires_at = None
            job.last_error_code = None
            job.processed_at = None
        await self.session.flush()
        return job

    async def delete_submission_processing_for_assignment(
        self,
        assignment_id: UUID,
    ) -> None:
        await self.session.execute(
            delete(SubmissionProcessingJob).where(
                SubmissionProcessingJob.assignment_id == assignment_id
            )
        )

    async def claim_due_submission_processing(
        self,
        *,
        now: datetime,
        lease_expires_at: datetime,
        limit: int,
    ) -> list[SubmissionProcessingJob]:
        result = await self.session.execute(
            select(SubmissionProcessingJob)
            .where(
                SubmissionProcessingJob.attempt_count
                < SubmissionProcessingJob.max_attempts,
                or_(
                    (
                        SubmissionProcessingJob.status
                        == SubmissionProcessingStatus.queued
                    )
                    & (SubmissionProcessingJob.next_attempt_at <= now),
                    (
                        SubmissionProcessingJob.status
                        == SubmissionProcessingStatus.processing
                    )
                    & (SubmissionProcessingJob.lease_expires_at <= now),
                ),
            )
            .order_by(
                SubmissionProcessingJob.next_attempt_at,
                SubmissionProcessingJob.created_at,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = list(result.scalars().all())
        for job in jobs:
            job.status = SubmissionProcessingStatus.processing
            job.attempt_count += 1
            job.lease_token = uuid4()
            job.lease_expires_at = lease_expires_at
        await self.session.flush()
        return jobs

    async def get_claimed_submission_processing(
        self,
        job_id: UUID,
        lease_token: UUID,
    ) -> SubmissionProcessingJob | None:
        result = await self.session.execute(
            select(SubmissionProcessingJob)
            .where(
                SubmissionProcessingJob.id == job_id,
                SubmissionProcessingJob.status
                == SubmissionProcessingStatus.processing,
                SubmissionProcessingJob.lease_token == lease_token,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def unlock_response_for_assignment(
        self,
        assignment_id: UUID,
    ) -> QuestionnaireResponse | None:
        response = await self.get_response_by_assignment(assignment_id)
        if response is None:
            return None
        response.status = QuestionnaireResponseStatus.draft
        response.submitted_at = None
        return response

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

    async def get_assessment_cycle_for_assignment(
        self,
        assignment: QuestionnaireAssignment,
    ) -> AssessmentCycle | None:
        if assignment.assessment_cycle_id is None or assignment.project_id is None:
            return None
        result = await self.session.execute(
            select(AssessmentCycle)
            .where(AssessmentCycle.id == assignment.assessment_cycle_id)
            .where(AssessmentCycle.company_id == assignment.company_id)
            .where(AssessmentCycle.project_id == assignment.project_id)
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

    async def get_definition_by_id(
        self,
        definition_id: UUID,
    ) -> QuestionnaireDefinition | None:
        result = await self.session.execute(
            select(QuestionnaireDefinition).where(QuestionnaireDefinition.id == definition_id)
        )
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

    async def has_assignments_for_definition(self, definition_id: UUID) -> bool:
        result = await self.session.execute(
            select(QuestionnaireAssignment.id)
            .where(QuestionnaireAssignment.questionnaire_definition_id == definition_id)
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
