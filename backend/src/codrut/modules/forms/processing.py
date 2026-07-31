from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus
from codrut.modules.forms.models import (
    QuestionnaireResponseStatus,
    SubmissionProcessingJob,
    SubmissionProcessingStatus,
)
from codrut.modules.forms.repository import FormsRepository
from codrut.modules.scoring.publication import ResultPublicationService
from codrut.modules.scoring.service import ScoringService

SUBMISSION_PROCESSING_LEASE = timedelta(minutes=2)
SUBMISSION_PROCESSING_BATCH_SIZE = 25
SCORING_REQUIRED_QUESTIONNAIRE_KEYS = {
    "lencioni",
    "lencioni_en",
    "distress_drivers",
    "distress_drivers_en",
    "boss_360",
    "boss_360_en",
    "icare",
}


def requires_scoring_result(questionnaire_key: str) -> bool:
    return questionnaire_key in SCORING_REQUIRED_QUESTIONNAIRE_KEYS


@dataclass(frozen=True)
class SubmissionProcessingClaim:
    job_id: UUID
    lease_token: UUID


async def claim_due_submission_processing(
    session: AsyncSession,
    *,
    limit: int = SUBMISSION_PROCESSING_BATCH_SIZE,
) -> list[SubmissionProcessingClaim]:
    now = datetime.now(UTC)
    jobs = await FormsRepository(session).claim_due_submission_processing(
        now=now,
        lease_expires_at=now + SUBMISSION_PROCESSING_LEASE,
        limit=limit,
    )
    return [
        SubmissionProcessingClaim(job_id=job.id, lease_token=job.lease_token)
        for job in jobs
        if job.lease_token is not None
    ]


async def process_claimed_submission(
    session: AsyncSession,
    claim: SubmissionProcessingClaim,
) -> bool:
    repository = FormsRepository(session)
    job_snapshot = await session.get(SubmissionProcessingJob, claim.job_id)
    if job_snapshot is None:
        return False

    # Submission updates lock the assignment before the queue row. Preserve that
    # order here so a resubmission and a worker cannot deadlock each other.
    assignment = await repository.get_assignment_by_id(
        job_snapshot.assignment_id,
        for_update=True,
    )
    job = await repository.get_claimed_submission_processing(
        claim.job_id,
        claim.lease_token,
    )
    if job is None:
        return False

    response = await repository.get_response_by_assignment(
        job.assignment_id,
        for_update=True,
    )
    if (
        assignment is None
        or response is None
        or response.status != QuestionnaireResponseStatus.submitted
    ):
        raise DomainError(
            "Submitted questionnaire response is unavailable for processing.",
            code="submission_processing_source_missing",
        )

    definition = await repository.get_definition_by_id(
        assignment.questionnaire_definition_id
    )
    if definition is None:
        raise DomainError(
            "Questionnaire definition is unavailable for submission processing.",
            code="submission_processing_definition_missing",
        )

    scoring_schema = definition.schema
    if definition.private_config:
        scoring_schema = definition.private_config.get("schema", scoring_schema)
    try:
        await ScoringService(session).compute_and_save_score(
            assignment_id=assignment.id,
            questionnaire_key=definition.key,
            questionnaire_version=definition.version,
            answers=response.answers,
            definition_schema=scoring_schema,
        )
    except DomainError as exc:
        if (
            exc.code not in {"scoring_not_supported", "scoring_metadata_missing"}
            or requires_scoring_result(definition.key)
        ):
            raise
    else:
        assignment.status = AssignmentStatus.scored
        assignment.submitted_at = assignment.submitted_at or response.submitted_at
        assignment.scored_at = datetime.now(UTC)
        await ResultPublicationService(session).reconcile_assignment(assignment.id)

    job.status = SubmissionProcessingStatus.completed
    job.next_attempt_at = None
    job.lease_token = None
    job.lease_expires_at = None
    job.last_error_code = None
    job.processed_at = datetime.now(UTC)
    await session.flush()
    return True


async def record_submission_processing_failure(
    session: AsyncSession,
    claim: SubmissionProcessingClaim,
    error: Exception,
) -> str:
    job = await FormsRepository(session).get_claimed_submission_processing(
        claim.job_id,
        claim.lease_token,
    )
    if job is None:
        return "stale"

    error_code = (
        error.code
        if isinstance(error, DomainError)
        else type(error).__name__
    )
    job.last_error_code = str(error_code)[:120]
    job.lease_token = None
    job.lease_expires_at = None
    if job.attempt_count >= job.max_attempts:
        job.status = SubmissionProcessingStatus.failed
        job.next_attempt_at = None
        return "failed"

    job.status = SubmissionProcessingStatus.queued
    retry_seconds = min(300, 2 ** max(job.attempt_count, 1))
    job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=retry_seconds)
    return "retried"
