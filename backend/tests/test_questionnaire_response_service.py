import uuid
from typing import Any, cast

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.companies import models as company_models  # noqa: F401
from codrut.modules.forms.models import QuestionnaireResponse, QuestionnaireResponseStatus
from codrut.modules.forms.schemas import QuestionnaireResponseSaveRequest
from codrut.modules.forms.service import FormsService
from codrut.modules.identity import models as identity_models  # noqa: F401
from codrut.modules.identity.models import SHADOW_ACCOUNT_PASSWORD_HASH, User, UserRole


class FakeFormsRepository:
    def __init__(self, assignment: QuestionnaireAssignment | None) -> None:
        self.assignment = assignment
        self.response: QuestionnaireResponse | None = None

    async def get_assignment_for_user(
        self,
        assignment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> QuestionnaireAssignment | None:
        if self.assignment and self.assignment.id == assignment_id:
            return self.assignment
        return None

    async def get_response_by_assignment(
        self,
        assignment_id: uuid.UUID,
    ) -> QuestionnaireResponse | None:
        if self.response and self.response.assignment_id == assignment_id:
            return self.response
        return None

    async def add_response(self, response: QuestionnaireResponse) -> QuestionnaireResponse:
        response.id = uuid.uuid4()
        self.response = response
        return response


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
    return {f"lencioni_q{number:02d}": 3 for number in range(1, 16)}


async def test_save_assignment_response_creates_draft_and_starts_assignment() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))
    payload = QuestionnaireResponseSaveRequest(answers={"lencioni_q01": 3})

    response = await service.save_assignment_response(uuid.uuid4(), assignment.id, payload)

    assert response.status == QuestionnaireResponseStatus.draft
    assert response.questionnaire_key == "lencioni"
    assert response.questionnaire_version == 1
    assert response.answers == {"lencioni_q01": 3}
    assert assignment.status == AssignmentStatus.started
    assert assignment.started_at is not None


async def test_submit_assignment_response_marks_response_and_assignment_submitted() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))

    response = await service.save_assignment_response(
        uuid.uuid4(),
        assignment.id,
        QuestionnaireResponseSaveRequest(answers=complete_lencioni_answers()),
        submit=True,
    )

    assert response.status == QuestionnaireResponseStatus.submitted
    assert assignment.status == AssignmentStatus.submitted
    assert assignment.submitted_at is not None


async def test_submit_scored_assignment_stamps_submitted_and_scored_times() -> None:
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
            session.add_all([user, company])
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
            assert assignment.status == AssignmentStatus.scored
            assert assignment.submitted_at is not None
            assert assignment.scored_at is not None
            assert assignment.scored_at == assignment.submitted_at

            await session.rollback()
    finally:
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
            session.add_all([user, company])
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
            session.add_all([user, company])
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
                await session.execute(
                    select(QuestionnaireAssignment).where(
                        QuestionnaireAssignment.respondent_profile_id == profile.id
                    )
                )
            ).scalars().all()
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


async def test_submit_rejects_incomplete_required_answers() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))

    with pytest.raises(DomainError, match="missing required answers"):
        await service.save_assignment_response(
            uuid.uuid4(),
            assignment.id,
            QuestionnaireResponseSaveRequest(answers={"lencioni_q01": 3}),
            submit=True,
        )


async def test_submit_rejects_answers_outside_question_scale() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))
    answers = complete_lencioni_answers()
    answers["lencioni_q01"] = 999

    with pytest.raises(DomainError, match="outside the allowed scale"):
        await service.save_assignment_response(
            uuid.uuid4(),
            assignment.id,
            QuestionnaireResponseSaveRequest(answers=answers),
            submit=True,
        )
