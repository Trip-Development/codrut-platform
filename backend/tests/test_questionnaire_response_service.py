import asyncio
import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssessmentCycleStatus,
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.assignments.repository import AssignmentRepository
from codrut.modules.assignments.schemas import AssignmentStatusUpdateRequest
from codrut.modules.assignments.service import AssignmentService
from codrut.modules.companies import models as company_models  # noqa: F401
from codrut.modules.companies.models import (
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
)
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
    SubmissionProcessingJob,
    SubmissionProcessingStatus,
)
from codrut.modules.forms.processing import (
    claim_due_submission_processing,
    process_claimed_submission,
    record_submission_processing_failure,
    requires_scoring_result,
)
from codrut.modules.forms.schemas import QuestionnaireResponseSaveRequest
from codrut.modules.forms.service import FormsService
from codrut.modules.identity import models as identity_models  # noqa: F401
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    User,
    UserAccountType,
    UserRole,
)
from codrut.modules.scoring.models import ResultPublication, ScoringResult
from codrut.modules.scoring.service import ScoringService
from codrut.tools.local_preview import (
    PREVIEW_DEFINITION_VERSION,
    build_preview_questionnaire_definitions,
    build_sample_answers,
)

PREVIEW_DEFINITIONS = {
    definition.key: definition for definition in build_preview_questionnaire_definitions()
}


def test_submission_processing_requires_scores_only_for_reportable_families() -> None:
    assert requires_scoring_result("lencioni") is True
    assert requires_scoring_result("icare") is True
    assert requires_scoring_result("distress_drivers") is True
    assert requires_scoring_result("pcm_base") is False
    assert requires_scoring_result("phase") is False


class FakeFormsRepository:
    def __init__(
        self,
        assignment: QuestionnaireAssignment | None,
        project: CompanyProject | None = None,
        cycle: object | None = None,
    ) -> None:
        self.assignment = assignment
        self.project = project
        self.cycle = cycle
        self.response: QuestionnaireResponse | None = None
        self.processing_assignments: list[uuid.UUID] = []
        preview = PREVIEW_DEFINITIONS["lencioni"]
        self.definition = QuestionnaireDefinition(
            id=uuid.uuid4(),
            key=preview.key,
            version=PREVIEW_DEFINITION_VERSION,
            title=preview.title,
            description=preview.description,
            schema=deepcopy(preview.schema),
            active=True,
        )

    async def get_assignment_for_user(
        self,
        assignment_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        participant_profile_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        cycle_id: uuid.UUID | None = None,
        allowed_assignment_ids: tuple[uuid.UUID, ...] | None = None,
        for_update: bool = False,
    ) -> QuestionnaireAssignment | None:
        del for_update
        if allowed_assignment_ids is not None and assignment_id not in allowed_assignment_ids:
            return None
        if (
            self.assignment
            and self.assignment.id == assignment_id
            and (
                participant_profile_id is None
                or self.assignment.respondent_profile_id == participant_profile_id
            )
            and (project_id is None or self.assignment.project_id == project_id)
            and (cycle_id is None or self.assignment.assessment_cycle_id == cycle_id)
        ):
            return self.assignment
        return None

    async def get_response_by_assignment(
        self,
        assignment_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> QuestionnaireResponse | None:
        del for_update
        if self.response and self.response.assignment_id == assignment_id:
            return self.response
        return None

    async def get_definition(
        self,
        key: str,
        *,
        version: int | None = None,
    ) -> QuestionnaireDefinition | None:
        if key != self.definition.key:
            return None
        if version is not None and version != self.definition.version:
            return None
        return self.definition

    async def get_definition_by_id(
        self,
        definition_id: uuid.UUID,
    ) -> QuestionnaireDefinition | None:
        return self.definition if definition_id == self.definition.id else None

    async def add_response(self, response: QuestionnaireResponse) -> QuestionnaireResponse:
        response.id = uuid.uuid4()
        self.response = response
        return response

    async def enqueue_submission_processing(
        self,
        assignment_id: uuid.UUID,
        *,
        now: datetime,
    ) -> SimpleNamespace:
        self.processing_assignments.append(assignment_id)
        return SimpleNamespace(
            assignment_id=assignment_id,
            status=SubmissionProcessingStatus.queued,
            next_attempt_at=now,
        )

    async def get_project_for_assignment(
        self,
        assignment: QuestionnaireAssignment,
    ) -> CompanyProject | None:
        if self.project is None or assignment.project_id != self.project.id:
            return None
        return self.project

    async def get_assessment_cycle_for_assignment(
        self,
        _assignment: QuestionnaireAssignment,
    ) -> object | None:
        return self.cycle


def make_service(repository: FakeFormsRepository) -> FormsService:
    service = FormsService()
    service.repository = cast(Any, repository)
    return service


def make_assignment() -> QuestionnaireAssignment:
    return QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.team,
        target_team_id=uuid.uuid4(),
        status=AssignmentStatus.assigned,
    )


def complete_lencioni_answers() -> dict[str, int]:
    return build_sample_answers(PREVIEW_DEFINITIONS["lencioni"].schema)


def persisted_preview_definition(
    key: str,
    *,
    active: bool = False,
) -> QuestionnaireDefinition:
    preview = PREVIEW_DEFINITIONS[key]
    return QuestionnaireDefinition(
        id=uuid.uuid4(),
        key=key,
        version=1_000_000 + uuid.uuid4().int % 1_000_000,
        title=preview.title,
        description=preview.description,
        schema=deepcopy(preview.schema),
        active=active,
    )


async def test_save_assignment_response_creates_draft_and_starts_assignment() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))
    payload = QuestionnaireResponseSaveRequest(answers={"team_sample_1": 3})

    response = await service.save_assignment_response(uuid.uuid4(), assignment.id, payload)

    assert response.status == QuestionnaireResponseStatus.draft
    assert response.questionnaire_key == "lencioni"
    assert response.questionnaire_version == PREVIEW_DEFINITION_VERSION
    assert response.answers == {"team_sample_1": 3}
    assert response.updated_at is not None
    assert assignment.status == AssignmentStatus.started
    assert assignment.started_at is not None


async def test_save_assignment_response_rejects_a_stale_draft_revision() -> None:
    assignment = make_assignment()
    repository = FakeFormsRepository(assignment)
    service = make_service(repository)
    user_id = uuid.uuid4()

    first = await service.save_assignment_response(
        user_id,
        assignment.id,
        QuestionnaireResponseSaveRequest(
            answers={"team_sample_1": 1},
            expected_updated_at=None,
        ),
    )
    assert first.updated_at is not None

    second = await service.save_assignment_response(
        user_id,
        assignment.id,
        QuestionnaireResponseSaveRequest(
            answers={"team_sample_1": 2},
            expected_updated_at=first.updated_at,
        ),
    )
    assert second.updated_at is not None
    assert second.updated_at > first.updated_at

    with pytest.raises(DomainError) as exc_info:
        await service.save_assignment_response(
            user_id,
            assignment.id,
            QuestionnaireResponseSaveRequest(
                answers={"team_sample_1": 3},
                expected_updated_at=first.updated_at,
            ),
        )

    assert exc_info.value.code == "response_conflict"
    assert repository.response is not None
    assert repository.response.answers == {"team_sample_1": 2}


async def test_submit_assignment_response_marks_response_and_assignment_submitted() -> None:
    assignment = make_assignment()
    repository = FakeFormsRepository(assignment)
    service = make_service(repository)

    response = await service.save_assignment_response(
        uuid.uuid4(),
        assignment.id,
        QuestionnaireResponseSaveRequest(answers=complete_lencioni_answers()),
        submit=True,
    )

    assert response.status == QuestionnaireResponseStatus.submitted
    assert assignment.status == AssignmentStatus.submitted
    assert assignment.submitted_at is not None
    assert repository.processing_assignments == [assignment.id]


async def test_save_assignment_response_rejects_changes_after_submission() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))
    user_id = uuid.uuid4()

    await service.save_assignment_response(
        user_id,
        assignment.id,
        QuestionnaireResponseSaveRequest(answers=complete_lencioni_answers()),
        submit=True,
    )

    with pytest.raises(DomainError) as exc_info:
        await service.save_assignment_response(
            user_id,
            assignment.id,
            QuestionnaireResponseSaveRequest(answers={"team_sample_1": 1}),
        )

    assert exc_info.value.code == "response_locked"


async def test_submit_assignment_response_is_idempotent_for_same_answers() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))
    user_id = uuid.uuid4()
    answers = complete_lencioni_answers()

    first = await service.save_assignment_response(
        user_id,
        assignment.id,
        QuestionnaireResponseSaveRequest(answers=answers),
        submit=True,
    )
    submitted_at = assignment.submitted_at

    second = await service.save_assignment_response(
        user_id,
        assignment.id,
        QuestionnaireResponseSaveRequest(answers=answers),
        submit=True,
    )

    assert second == first
    assert assignment.submitted_at == submitted_at


async def test_save_assignment_response_rejects_assignment_after_due_date() -> None:
    assignment = make_assignment()
    assignment.due_at = datetime.now(UTC) - timedelta(minutes=1)
    service = make_service(FakeFormsRepository(assignment))

    with pytest.raises(DomainError) as exc_info:
        await service.save_assignment_response(
            uuid.uuid4(),
            assignment.id,
            QuestionnaireResponseSaveRequest(answers={"team_sample_1": 3}),
        )

    assert exc_info.value.code == "assignment_closed"


async def test_save_assignment_response_rejects_project_closed_window() -> None:
    assignment = make_assignment()
    assignment.project_id = uuid.uuid4()
    project = CompanyProject(
        id=assignment.project_id,
        company_id=assignment.company_id,
        name="July Pilot",
        form_closes_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    service = make_service(FakeFormsRepository(assignment, project))

    with pytest.raises(DomainError) as exc_info:
        await service.save_assignment_response(
            uuid.uuid4(),
            assignment.id,
            QuestionnaireResponseSaveRequest(answers={"team_sample_1": 3}),
        )

    assert exc_info.value.code == "project_closed"


async def test_cancelled_assignment_rejects_definition_read_save_and_submit() -> None:
    assignment = make_assignment()
    assignment.status = AssignmentStatus.cancelled
    service = make_service(FakeFormsRepository(assignment))
    user_id = uuid.uuid4()
    payload = QuestionnaireResponseSaveRequest(answers={"team_sample_1": 3})

    actions = (
        lambda: service.get_assignment_definition(user_id, assignment.id),
        lambda: service.get_assignment_response(user_id, assignment.id),
        lambda: service.save_assignment_response(user_id, assignment.id, payload),
        lambda: service.save_assignment_response(user_id, assignment.id, payload, submit=True),
    )
    for action in actions:
        with pytest.raises(DomainError) as exc_info:
            await action()
        assert exc_info.value.code == "assignment_cancelled"


async def test_closed_cycle_rejects_definition_read_save_and_submit() -> None:
    assignment = make_assignment()
    assignment.project_id = uuid.uuid4()
    assignment.assessment_cycle_id = uuid.uuid4()
    cycle = SimpleNamespace(
        status=AssessmentCycleStatus.closed,
        starts_at=datetime.now(UTC) - timedelta(minutes=1),
        due_at=None,
    )
    service = make_service(FakeFormsRepository(assignment, cycle=cycle))
    user_id = uuid.uuid4()
    payload = QuestionnaireResponseSaveRequest(answers={"team_sample_1": 3})

    actions = (
        lambda: service.get_assignment_definition(user_id, assignment.id),
        lambda: service.get_assignment_response(user_id, assignment.id),
        lambda: service.save_assignment_response(user_id, assignment.id, payload),
        lambda: service.save_assignment_response(user_id, assignment.id, payload, submit=True),
    )
    for action in actions:
        with pytest.raises(DomainError) as exc_info:
            await action()
        assert exc_info.value.code == "assessment_cycle_closed"


async def test_participant_definition_requires_profile_context_for_multiple_profiles() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"multi-profile-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            first_company = company_models.Company(
                id=uuid.uuid4(),
                name=f"First profile {uuid.uuid4().hex[:8]}",
            )
            second_company = company_models.Company(
                id=uuid.uuid4(),
                name=f"Second profile {uuid.uuid4().hex[:8]}",
            )
            first_definition = persisted_preview_definition("lencioni")
            second_definition = persisted_preview_definition("lencioni")
            session.add_all(
                [user, first_company, second_company, first_definition, second_definition]
            )
            await session.flush()

            first_profile = company_models.ParticipantProfile(
                id=uuid.uuid4(),
                company_id=first_company.id,
                user_id=user.id,
                full_name="First profile",
                email=user.email,
            )
            second_profile = company_models.ParticipantProfile(
                id=uuid.uuid4(),
                company_id=second_company.id,
                user_id=user.id,
                full_name="Second profile",
                email=user.email,
            )
            session.add_all([first_profile, second_profile])
            await session.flush()

            session.add_all(
                [
                    QuestionnaireAssignment(
                        id=uuid.uuid4(),
                        company_id=first_company.id,
                        respondent_profile_id=first_profile.id,
                        questionnaire_key="lencioni",
                        questionnaire_definition_id=first_definition.id,
                        target_type=AssignmentTargetType.self_assessment,
                        status=AssignmentStatus.assigned,
                    ),
                    QuestionnaireAssignment(
                        id=uuid.uuid4(),
                        company_id=second_company.id,
                        respondent_profile_id=second_profile.id,
                        questionnaire_key="lencioni",
                        questionnaire_definition_id=second_definition.id,
                        target_type=AssignmentTargetType.self_assessment,
                        status=AssignmentStatus.assigned,
                    ),
                ]
            )
            await session.flush()

            service = FormsService(session)
            with pytest.raises(DomainError) as ambiguous:
                await service.get_participant_definition_by_key(user.id, "lencioni")
            assert ambiguous.value.code == "participant_context_required"

            selected = await service.get_participant_definition_by_key(
                user.id,
                "lencioni",
                participant_profile_id=second_profile.id,
            )
            assert selected.version == second_definition.version

            await session.rollback()
    finally:
        await engine.dispose()


async def test_submit_survives_scoring_failure_and_worker_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"scored-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = company_models.Company(
                id=uuid.uuid4(),
                name=f"Scored {uuid.uuid4().hex[:8]}",
            )
            definition = persisted_preview_definition("lencioni")
            session.add_all([user, company, definition])
            await session.flush()

            profile = company_models.ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Scored Participant",
                email=user.email,
            )
            session.add(profile)
            await session.flush()

            assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                respondent_profile_id=profile.id,
                questionnaire_key="lencioni",
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.assigned,
            )
            session.add(assignment)
            await session.flush()

            response = await FormsService(session).save_assignment_response(
                user.id,
                assignment.id,
                QuestionnaireResponseSaveRequest(answers=complete_lencioni_answers()),
                submit=True,
            )

            assert response.status == QuestionnaireResponseStatus.submitted
            assert assignment.status == AssignmentStatus.submitted
            assert assignment.submitted_at is not None
            assert assignment.scored_at is None
            assignment_id = assignment.id
            await session.commit()

        async with SessionLocal() as worker_session:
            claims = await claim_due_submission_processing(worker_session)
            assert len(claims) == 1
            await worker_session.commit()

        original_compute = ScoringService.compute_and_save_score
        worker_error = DomainError(
            "Scoring metadata is unavailable.",
            code="scoring_metadata_missing",
        )
        monkeypatch.setattr(
            ScoringService,
            "compute_and_save_score",
            AsyncMock(side_effect=worker_error),
        )
        async with SessionLocal() as worker_session:
            with pytest.raises(DomainError) as processing_error:
                await process_claimed_submission(worker_session, claims[0])
            assert processing_error.value.code == "scoring_metadata_missing"
            await worker_session.rollback()

        async with SessionLocal() as failure_session:
            assert (
                await record_submission_processing_failure(
                    failure_session,
                    claims[0],
                    worker_error,
                )
                == "retried"
            )
            job = (
                await failure_session.execute(
                    select(SubmissionProcessingJob).where(
                        SubmissionProcessingJob.assignment_id == assignment_id
                    )
                )
            ).scalar_one()
            assert job.status == SubmissionProcessingStatus.queued
            assert job.last_error_code == "scoring_metadata_missing"
            job.next_attempt_at = datetime.now(UTC)
            await failure_session.commit()

        async with SessionLocal() as verification_session:
            persisted_response = (
                await verification_session.execute(
                    select(QuestionnaireResponse).where(
                        QuestionnaireResponse.assignment_id == assignment_id
                    )
                )
            ).scalar_one()
            persisted_assignment = await verification_session.get(
                QuestionnaireAssignment,
                assignment_id,
            )
            assert persisted_response.status == QuestionnaireResponseStatus.submitted
            assert persisted_assignment is not None
            assert persisted_assignment.status == AssignmentStatus.submitted

        monkeypatch.setattr(
            ScoringService,
            "compute_and_save_score",
            original_compute,
        )
        async with SessionLocal() as worker_session:
            retry_claims = await claim_due_submission_processing(worker_session)
            assert len(retry_claims) == 1
            await worker_session.commit()

        async with SessionLocal() as worker_session:
            assert await process_claimed_submission(worker_session, retry_claims[0]) is True
            await worker_session.commit()

        async with SessionLocal() as verification_session:
            persisted_assignment = await verification_session.get(
                QuestionnaireAssignment,
                assignment_id,
            )
            assert persisted_assignment is not None
            assert persisted_assignment.status == AssignmentStatus.scored
            assert persisted_assignment.scored_at is not None

    finally:
        await engine.dispose()


async def test_reopen_waits_for_processing_and_removes_committed_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await engine.dispose()
    scoring_started = asyncio.Event()
    allow_scoring_to_finish = asyncio.Event()
    reopen_requested = asyncio.Event()
    try:
        async with SessionLocal() as session:
            trainer = User(
                id=uuid.uuid4(),
                email=f"trainer-reopen-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("trainer-password-123"),
                role=UserRole.trainer,
            )
            participant = User(
                id=uuid.uuid4(),
                email=f"participant-reopen-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = company_models.Company(
                id=uuid.uuid4(),
                name=f"Concurrent reopen {uuid.uuid4().hex[:8]}",
            )
            definition = persisted_preview_definition("lencioni")
            session.add_all([trainer, participant, company, definition])
            await session.flush()
            session.add(
                CompanyMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    user_id=trainer.id,
                    role=CompanyMembershipRole.trainer,
                )
            )
            profile = company_models.ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=participant.id,
                full_name="Concurrent Participant",
                email=participant.email,
            )
            session.add(profile)
            await session.flush()
            assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                respondent_profile_id=profile.id,
                questionnaire_key="lencioni",
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.assigned,
            )
            session.add(assignment)
            await session.flush()
            await FormsService(session).save_assignment_response(
                participant.id,
                assignment.id,
                QuestionnaireResponseSaveRequest(answers=complete_lencioni_answers()),
                submit=True,
            )
            assignment_id = assignment.id
            company_id = company.id
            trainer_id = trainer.id
            await session.commit()

        async with SessionLocal() as claim_session:
            claims = await claim_due_submission_processing(claim_session)
            assert len(claims) == 1
            claim = claims[0]
            await claim_session.commit()

        original_compute = ScoringService.compute_and_save_score

        async def delayed_compute(
            service: ScoringService,
            *args: Any,
            **kwargs: Any,
        ) -> ScoringResult:
            scoring_started.set()
            await allow_scoring_to_finish.wait()
            return await original_compute(service, *args, **kwargs)

        monkeypatch.setattr(
            ScoringService,
            "compute_and_save_score",
            delayed_compute,
        )
        original_get_assignment = AssignmentRepository.get_assignment

        async def observed_get_assignment(
            repository: AssignmentRepository,
            requested_company_id: uuid.UUID,
            requested_assignment_id: uuid.UUID,
            *,
            for_update: bool = False,
        ) -> QuestionnaireAssignment | None:
            if requested_assignment_id == assignment_id and for_update:
                reopen_requested.set()
            return await original_get_assignment(
                repository,
                requested_company_id,
                requested_assignment_id,
                for_update=for_update,
            )

        monkeypatch.setattr(
            AssignmentRepository,
            "get_assignment",
            observed_get_assignment,
        )

        async def process_submission() -> None:
            async with SessionLocal() as worker_session:
                assert await process_claimed_submission(worker_session, claim) is True
                await worker_session.commit()

        async def reopen_assignment() -> None:
            async with SessionLocal() as trainer_session:
                await AssignmentService(trainer_session).update_assignment_status(
                    trainer_id,
                    company_id,
                    assignment_id,
                    AssignmentStatusUpdateRequest(status=AssignmentStatus.started),
                )
                await trainer_session.commit()

        worker_task = asyncio.create_task(process_submission())
        await scoring_started.wait()
        reopen_task = asyncio.create_task(reopen_assignment())
        await reopen_requested.wait()
        await asyncio.sleep(0)
        assert not reopen_task.done()

        allow_scoring_to_finish.set()
        await asyncio.gather(worker_task, reopen_task)

        async with SessionLocal() as verification_session:
            persisted_assignment = await verification_session.get(
                QuestionnaireAssignment,
                assignment_id,
            )
            persisted_response = (
                await verification_session.execute(
                    select(QuestionnaireResponse).where(
                        QuestionnaireResponse.assignment_id == assignment_id
                    )
                )
            ).scalar_one()
            score = (
                await verification_session.execute(
                    select(ScoringResult).where(ScoringResult.assignment_id == assignment_id)
                )
            ).scalar_one_or_none()
            processing_job = (
                await verification_session.execute(
                    select(SubmissionProcessingJob).where(
                        SubmissionProcessingJob.assignment_id == assignment_id
                    )
                )
            ).scalar_one_or_none()
            active_publication = (
                await verification_session.execute(
                    select(ResultPublication).where(
                        ResultPublication.source_assignment_id == assignment_id,
                        ResultPublication.revoked_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

            assert persisted_assignment is not None
            assert persisted_assignment.status == AssignmentStatus.started
            assert persisted_assignment.submitted_at is None
            assert persisted_assignment.scored_at is None
            assert persisted_response.status == QuestionnaireResponseStatus.draft
            assert persisted_response.submitted_at is None
            assert score is None
            assert processing_job is None
            assert active_publication is None
    finally:
        allow_scoring_to_finish.set()
        await engine.dispose()


async def test_submit_pcm_base_updates_participant_profile_without_scoring() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"pcm-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = company_models.Company(
                id=uuid.uuid4(),
                name=f"PCM {uuid.uuid4().hex[:8]}",
            )
            definition = persisted_preview_definition("pcm_base")
            session.add_all([user, company, definition])
            await session.flush()

            profile = company_models.ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="PCM Participant",
                email=user.email,
            )
            session.add(profile)
            await session.flush()

            assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                respondent_profile_id=profile.id,
                questionnaire_key="pcm_base",
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.assigned,
            )
            session.add(assignment)
            await session.flush()

            response = await FormsService(session).save_assignment_response(
                user.id,
                assignment.id,
                QuestionnaireResponseSaveRequest(
                    answers={"pcm_base": "harmonizer", "pcm_phase": "thinker"}
                ),
                submit=True,
            )

            assert response.status == QuestionnaireResponseStatus.submitted
            assert assignment.status == AssignmentStatus.submitted
            assert profile.pcm_base == "harmonizer"
            assert profile.pcm_phase == "thinker"
            assert profile.pcm_profile == "harmonizer"
            assert assignment.scored_at is None

            await session.rollback()
    finally:
        await engine.dispose()


async def test_participant_onboarding_creates_single_pcm_profile_task_for_permanent_user() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"pcm-onboarding-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = company_models.Company(
                id=uuid.uuid4(),
                name=f"PCM Onboarding {uuid.uuid4().hex[:8]}",
            )
            definition = persisted_preview_definition("pcm_base", active=True)
            session.add_all([user, company, definition])
            await session.flush()

            profile = company_models.ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Permanent Participant",
                email=user.email,
            )
            session.add(profile)
            await session.flush()

            onboarding = await FormsService(session).get_participant_onboarding(user.id)

            assert onboarding.required is True
            assert onboarding.questionnaire_key == "pcm_base"
            assert onboarding.assignment_id is not None
            assert onboarding.href == (
                f"/participant/questionnaires/pcm_base?assignmentId={onboarding.assignment_id}"
            )

            assignment = (
                await session.execute(
                    select(QuestionnaireAssignment).where(
                        QuestionnaireAssignment.id == onboarding.assignment_id
                    )
                )
            ).scalar_one()
            assert assignment.questionnaire_key == "pcm_base"
            assert assignment.questionnaire_definition_id == definition.id
            assert assignment.target_type == AssignmentTargetType.self_assessment
            assert assignment.access_mode == AssignmentAccessMode.account_link

            await session.rollback()
    finally:
        await engine.dispose()


async def test_participant_onboarding_skips_shadow_secure_link_users() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"pcm-shadow-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
                role=UserRole.participant,
                account_type=UserAccountType.guest,
            )
            company = company_models.Company(
                id=uuid.uuid4(),
                name=f"PCM Shadow {uuid.uuid4().hex[:8]}",
            )
            session.add_all([user, company])
            await session.flush()

            profile = company_models.ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Shadow Participant",
                email=user.email,
            )
            session.add(profile)
            await session.flush()

            onboarding = await FormsService(session).get_participant_onboarding(user.id)

            assert onboarding.required is False

            assignment_count = (
                (
                    await session.execute(
                        select(QuestionnaireAssignment).where(
                            QuestionnaireAssignment.respondent_profile_id == profile.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert assignment_count == []

            await session.rollback()
    finally:
        await engine.dispose()


async def test_save_assignment_response_rejects_missing_assignment() -> None:
    service = make_service(FakeFormsRepository(None))

    with pytest.raises(DomainError, match="Assignment not found"):
        await service.save_assignment_response(
            uuid.uuid4(),
            uuid.uuid4(),
            QuestionnaireResponseSaveRequest(answers={}),
        )


async def test_get_assignment_response_does_not_create_draft() -> None:
    assignment = make_assignment()
    repository = FakeFormsRepository(assignment)
    service = make_service(repository)

    res = await service.get_assignment_response(uuid.uuid4(), assignment.id)
    assert res.answers == {}
    assert res.questionnaire_key == assignment.questionnaire_key
    assert repository.response is None


async def test_get_assignment_definition_requires_the_assignment_scope() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))

    definition = await service.get_assignment_definition(
        uuid.uuid4(),
        assignment.id,
        allowed_assignment_ids=(assignment.id,),
    )

    assert definition.key == assignment.questionnaire_key
    assert definition.version == PREVIEW_DEFINITION_VERSION

    with pytest.raises(DomainError) as exc_info:
        await service.get_assignment_definition(
            uuid.uuid4(),
            assignment.id,
            allowed_assignment_ids=(uuid.uuid4(),),
        )

    assert exc_info.value.code == "assignment_not_found"


async def test_get_assignment_response_rejects_assignment_after_due_date() -> None:
    assignment = make_assignment()
    assignment.due_at = datetime.now(UTC) - timedelta(minutes=1)
    service = make_service(FakeFormsRepository(assignment))

    with pytest.raises(DomainError) as exc_info:
        await service.get_assignment_response(uuid.uuid4(), assignment.id)

    assert exc_info.value.code == "assignment_closed"


async def test_get_assignment_response_rejects_project_closed_window() -> None:
    assignment = make_assignment()
    assignment.project_id = uuid.uuid4()
    project = CompanyProject(
        id=assignment.project_id,
        company_id=assignment.company_id,
        name="July Pilot",
        form_closes_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    service = make_service(FakeFormsRepository(assignment, project))

    with pytest.raises(DomainError) as exc_info:
        await service.get_assignment_response(uuid.uuid4(), assignment.id)

    assert exc_info.value.code == "project_closed"


async def test_submit_rejects_incomplete_required_answers() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))

    with pytest.raises(DomainError, match="missing required answers"):
        await service.save_assignment_response(
            uuid.uuid4(),
            assignment.id,
            QuestionnaireResponseSaveRequest(answers={"team_sample_1": 3}),
            submit=True,
        )


async def test_submit_allows_unanswered_optional_questions() -> None:
    assignment = make_assignment()
    repository = FakeFormsRepository(assignment)
    questions = repository.definition.schema["sections"][0]["questions"]
    questions[1]["required"] = False
    answers = complete_lencioni_answers()
    answers.pop(questions[1]["id"])

    response = await make_service(repository).save_assignment_response(
        uuid.uuid4(),
        assignment.id,
        QuestionnaireResponseSaveRequest(answers=answers),
        submit=True,
    )

    assert response.status == QuestionnaireResponseStatus.submitted


async def test_submit_rejects_answers_outside_question_scale() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))
    answers = complete_lencioni_answers()
    question_id = PREVIEW_DEFINITIONS["lencioni"].schema["sections"][0]["questions"][0]["id"]
    answers[question_id] = 999

    with pytest.raises(DomainError, match="outside the allowed scale"):
        await service.save_assignment_response(
            uuid.uuid4(),
            assignment.id,
            QuestionnaireResponseSaveRequest(answers=answers),
            submit=True,
        )
