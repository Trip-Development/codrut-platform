"""Redeschiderea unui chestionar deja trimis.

Cazurile care conteaza:
  · un participant NU are voie sa redeschida, nici trimitand cererea direct
  · daca robotul proceseaza chiar acum trimiterea, redeschiderea REFUZA
  · se arhiveaza INAINTE de a se sterge ceva
  · bonul de lucru ramas in coada se curata, altfel robotul ar scoate un scor
    pentru un chestionar gol
  · numarul de ordine vine din contorul de pe asignare, nu dintr-o numaratoare
    a arhivei
  · asignarea se intoarce intr-o stare din care omul chiar poate completa
"""

import uuid
from typing import Any, cast

import pytest
from fastapi import HTTPException

from codrut.core.errors import DomainError
from codrut.modules.assignments import router as assignments_router
from codrut.modules.assignments.models import (
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    ResponseVisibilityPolicy,
)
from codrut.modules.assignments.service import EDITABLE_ASSIGNMENT_STATUSES, AssignmentService
from codrut.modules.companies.models import CompanyMembership, CompanyMembershipRole
from codrut.modules.forms.models import (
    QuestionnaireResponse,
    QuestionnaireResponseArchive,
    QuestionnaireResponseStatus,
    SubmissionProcessingJob,
    SubmissionProcessingStatus,
)
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.scoring.models import ScoringResult

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROFILE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ASSIGNMENT_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
RESPONSE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
TRAINER_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")


class FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushes = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1


class FakeFormsRepository:
    def __init__(
        self,
        assignment: QuestionnaireAssignment | None,
        response: QuestionnaireResponse | None,
        job: SubmissionProcessingJob | None = None,
    ) -> None:
        self.assignment = assignment
        self.response = response
        self.job = job
        self.locked_assignment = False
        self.locked_response = False
        self.locked_job = False
        self.deleted_responses: list[uuid.UUID] = []
        self.deleted_jobs: list[uuid.UUID] = []
        self.call_order: list[str] = []

    async def get_assignment_by_id(
        self,
        assignment_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> QuestionnaireAssignment | None:
        self.locked_assignment = for_update
        self.call_order.append("get_assignment")
        return self.assignment

    async def get_submission_processing_for_assignment(
        self,
        assignment_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SubmissionProcessingJob | None:
        self.locked_job = for_update
        self.call_order.append("get_job")
        return self.job

    async def get_response_by_assignment(
        self,
        assignment_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> QuestionnaireResponse | None:
        self.locked_response = for_update
        self.call_order.append("get_response")
        return self.response

    async def delete_response_by_assignment(self, assignment_id: uuid.UUID) -> None:
        self.call_order.append("delete_response")
        self.deleted_responses.append(assignment_id)

    async def delete_submission_processing_for_assignment(
        self,
        assignment_id: uuid.UUID,
    ) -> None:
        self.call_order.append("delete_job")
        self.deleted_jobs.append(assignment_id)


class FakeScoringRepository:
    def __init__(self, result: ScoringResult | None) -> None:
        self.result = result
        self.deleted: list[uuid.UUID] = []
        self.call_order: list[str] = []

    async def get_by_assignment(self, assignment_id: uuid.UUID) -> ScoringResult | None:
        self.call_order.append("get_score")
        return self.result

    async def delete_by_assignment(self, assignment_id: uuid.UUID) -> None:
        self.call_order.append("delete_score")
        self.deleted.append(assignment_id)


class FakeCompanyRepository:
    def __init__(self, role: CompanyMembershipRole | None) -> None:
        self.role = role

    async def get_company(self, company_id: uuid.UUID) -> object | None:
        return object()

    async def get_membership(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CompanyMembership | None:
        if self.role is None:
            return None
        return CompanyMembership(
            id=uuid.uuid4(),
            company_id=company_id,
            user_id=user_id,
            role=self.role,
        )


class FakeResultPublicationService:
    def __init__(self) -> None:
        self.reconciled: list[uuid.UUID] = []

    async def reconcile_assignment(self, assignment_id: uuid.UUID) -> None:
        self.reconciled.append(assignment_id)


def _assignment(
    *,
    status: AssignmentStatus = AssignmentStatus.scored,
    reopen_count: int = 0,
    invited_at: object | None = "set",
) -> QuestionnaireAssignment:
    from datetime import UTC, datetime

    stamp = datetime.now(UTC)
    return QuestionnaireAssignment(
        id=ASSIGNMENT_ID,
        company_id=COMPANY_ID,
        project_id=None,
        assignment_round_id=uuid.uuid4(),
        assessment_cycle_id=None,
        respondent_profile_id=PROFILE_ID,
        questionnaire_key="lencioni",
        questionnaire_definition_id=uuid.uuid4(),
        target_type=AssignmentTargetType.self_assessment,
        access_mode=AssignmentAccessMode.account_link,
        status=status,
        visibility_policy=ResponseVisibilityPolicy.trainer_raw_review,
        invited_at=stamp if invited_at == "set" else None,
        started_at=stamp,
        submitted_at=stamp,
        scored_at=stamp,
        reminder_count=0,
        reopen_count=reopen_count,
    )


def _response() -> QuestionnaireResponse:
    from datetime import UTC, datetime

    return QuestionnaireResponse(
        id=RESPONSE_ID,
        assignment_id=ASSIGNMENT_ID,
        questionnaire_key="lencioni",
        questionnaire_version=1,
        status=QuestionnaireResponseStatus.submitted,
        answers={"q1": 3, "q2": 5},
        submitted_at=datetime.now(UTC),
    )


def _service(
    *,
    assignment: QuestionnaireAssignment | None,
    response: QuestionnaireResponse | None,
    job: SubmissionProcessingJob | None = None,
    scoring: ScoringResult | None = None,
    role: CompanyMembershipRole | None = CompanyMembershipRole.trainer,
) -> tuple[AssignmentService, FakeSession, FakeFormsRepository, FakeScoringRepository]:
    session = FakeSession()
    service = AssignmentService(cast(Any, session))
    forms = FakeFormsRepository(assignment, response, job)
    scoring_repo = FakeScoringRepository(scoring)
    service.forms_repository = cast(Any, forms)
    service.scoring_repository = cast(Any, scoring_repo)
    service.company_repository = cast(Any, FakeCompanyRepository(role))
    service.result_publication_service = cast(Any, FakeResultPublicationService())
    return service, session, forms, scoring_repo


@pytest.mark.asyncio
async def test_reopen_refuses_while_the_worker_holds_the_submission() -> None:
    """Punctul 2: robotul proceseaza chiar acum. Nu-i tragem raspunsul de sub picioare."""
    job = SubmissionProcessingJob(
        id=uuid.uuid4(),
        assignment_id=ASSIGNMENT_ID,
        status=SubmissionProcessingStatus.processing,
        attempt_count=1,
        max_attempts=5,
    )
    service, session, forms, scoring_repo = _service(
        assignment=_assignment(),
        response=_response(),
        job=job,
    )

    with pytest.raises(DomainError) as excinfo:
        await service.reopen_assignment(
            TRAINER_ID,
            COMPANY_ID,
            ASSIGNMENT_ID,
            reopened_by_email="trainer@exemplu.invalid",
        )

    assert excinfo.value.code == "reopen_submission_processing"
    # Nimic nu s-a atins: nici arhiva, nici raspunsul, nici scorul, nici bonul.
    assert session.added == []
    assert forms.deleted_responses == []
    assert forms.deleted_jobs == []
    assert scoring_repo.deleted == []


@pytest.mark.asyncio
async def test_reopen_proceeds_when_the_job_is_only_queued() -> None:
    """Un bon in coada (nu in lucru) nu opreste redeschiderea, dar se curata."""
    job = SubmissionProcessingJob(
        id=uuid.uuid4(),
        assignment_id=ASSIGNMENT_ID,
        status=SubmissionProcessingStatus.queued,
        attempt_count=0,
        max_attempts=5,
    )
    service, _session, forms, _scoring = _service(
        assignment=_assignment(),
        response=_response(),
        job=job,
    )

    await service.reopen_assignment(
        TRAINER_ID,
        COMPANY_ID,
        ASSIGNMENT_ID,
        reopened_by_email="trainer@exemplu.invalid",
    )

    # Punctul 1: bonul ramas in coada se sterge, altfel robotul ar calcula
    # un scor pe un chestionar gol si l-ar publica.
    assert forms.deleted_jobs == [ASSIGNMENT_ID]


@pytest.mark.asyncio
async def test_reopen_archives_before_deleting_anything() -> None:
    """Ordinea obligatorie: arhiva se scrie INAINTE de orice stergere."""
    scoring = ScoringResult(
        id=uuid.uuid4(),
        assignment_id=ASSIGNMENT_ID,
        scores={"trust": 4.2},
        primary_result="trust",
    )
    service, session, forms, scoring_repo = _service(
        assignment=_assignment(),
        response=_response(),
        scoring=scoring,
    )

    result = await service.reopen_assignment(
        TRAINER_ID,
        COMPANY_ID,
        ASSIGNMENT_ID,
        reopened_by_email="trainer@exemplu.invalid",
    )

    archive = session.added[0]
    assert isinstance(archive, QuestionnaireResponseArchive)
    # Raspunsul vechi, INTREG, plus scorul vechi.
    assert archive.answers == {"q1": 3, "q2": 5}
    assert archive.response_status == "submitted"
    assert archive.scores == {"trust": 4.2}
    assert archive.primary_result == "trust"
    assert archive.response_id == RESPONSE_ID
    # Cine a redeschis si cand.
    assert archive.reopened_by_user_id == TRAINER_ID
    assert archive.reopened_by_email == "trainer@exemplu.invalid"
    assert archive.reopen_sequence == 1

    # Ordinea: arhiva scrisa (flush) inainte de orice stergere.
    order = forms.call_order + scoring_repo.call_order
    assert order.index("delete_response") > order.index("get_response")
    assert "delete_score" in scoring_repo.call_order
    assert forms.deleted_responses == [ASSIGNMENT_ID]
    assert result.archived_had_score is True


@pytest.mark.asyncio
async def test_reopen_takes_the_sequence_from_the_assignment_counter() -> None:
    """Punctul 3: numarul de ordine vine din contorul de pe asignare, sub blocare."""
    assignment = _assignment(reopen_count=2)
    service, session, forms, _scoring = _service(
        assignment=assignment,
        response=_response(),
    )

    result = await service.reopen_assignment(
        TRAINER_ID,
        COMPANY_ID,
        ASSIGNMENT_ID,
        reopened_by_email="trainer@exemplu.invalid",
    )

    archive = session.added[0]
    assert archive.reopen_sequence == 3
    assert assignment.reopen_count == 3
    assert result.reopen_count == 3
    # Randul asignarii si cel al raspunsului au fost citite sub blocare.
    assert forms.locked_assignment is True
    assert forms.locked_response is True
    assert forms.locked_job is True


@pytest.mark.asyncio
async def test_reopen_returns_the_assignment_to_a_state_the_person_can_fill() -> None:
    """Punctul 4: din starea in care ramane, omul chiar poate completa."""
    assignment = _assignment(status=AssignmentStatus.scored, invited_at="set")
    service, _session, _forms, _scoring = _service(
        assignment=assignment,
        response=_response(),
    )

    await service.reopen_assignment(
        TRAINER_ID,
        COMPANY_ID,
        ASSIGNMENT_ID,
        reopened_by_email="trainer@exemplu.invalid",
    )

    assert assignment.status is AssignmentStatus.invited
    assert assignment.status in EDITABLE_ASSIGNMENT_STATUSES
    # Marcajele de terminare se sterg, altfel omul ar vedea "completat".
    assert assignment.submitted_at is None
    assert assignment.validated_at is None
    assert assignment.scored_at is None
    assert assignment.started_at is None


@pytest.mark.asyncio
async def test_reopen_falls_back_to_assigned_when_never_invited() -> None:
    """Fara invitatie in istoric, asignarea se intoarce la 'assigned', nu la 'invited'."""
    assignment = _assignment(status=AssignmentStatus.submitted, invited_at=None)
    service, _session, _forms, _scoring = _service(
        assignment=assignment,
        response=_response(),
    )

    await service.reopen_assignment(
        TRAINER_ID,
        COMPANY_ID,
        ASSIGNMENT_ID,
        reopened_by_email="trainer@exemplu.invalid",
    )

    assert assignment.status is AssignmentStatus.assigned
    assert assignment.status in EDITABLE_ASSIGNMENT_STATUSES


@pytest.mark.asyncio
async def test_reopen_revokes_the_published_result() -> None:
    """Rezultatul publicat se anuleaza prin mecanismul care exista deja."""
    service, _session, _forms, _scoring = _service(
        assignment=_assignment(),
        response=_response(),
    )

    await service.reopen_assignment(
        TRAINER_ID,
        COMPANY_ID,
        ASSIGNMENT_ID,
        reopened_by_email="trainer@exemplu.invalid",
    )

    publication = cast(Any, service.result_publication_service)
    assert publication.reconciled == [ASSIGNMENT_ID]


@pytest.mark.asyncio
async def test_reopen_refuses_a_user_without_company_management_rights() -> None:
    """Cine nu e trainer sau proprietar al companiei primeste refuz."""
    service, session, forms, _scoring = _service(
        assignment=_assignment(),
        response=_response(),
        role=CompanyMembershipRole.participant,
    )

    with pytest.raises(DomainError) as excinfo:
        await service.reopen_assignment(
            TRAINER_ID,
            COMPANY_ID,
            ASSIGNMENT_ID,
            reopened_by_email="participant@exemplu.invalid",
        )

    assert excinfo.value.code == "company_access_denied"
    assert session.added == []
    assert forms.deleted_responses == []


@pytest.mark.asyncio
async def test_reopen_refuses_an_assignment_from_another_company() -> None:
    """Un id de asignare dintr-o alta companie nu se poate redeschide prin URL strain."""
    service, session, _forms, _scoring = _service(
        assignment=_assignment(),
        response=_response(),
    )

    with pytest.raises(DomainError) as excinfo:
        await service.reopen_assignment(
            TRAINER_ID,
            uuid.uuid4(),
            ASSIGNMENT_ID,
            reopened_by_email="trainer@exemplu.invalid",
        )

    assert excinfo.value.code == "assignment_not_found"
    assert session.added == []


@pytest.mark.asyncio
async def test_reopen_refuses_when_there_is_nothing_to_reopen() -> None:
    service, session, _forms, _scoring = _service(
        assignment=_assignment(),
        response=None,
    )

    with pytest.raises(DomainError) as excinfo:
        await service.reopen_assignment(
            TRAINER_ID,
            COMPANY_ID,
            ASSIGNMENT_ID,
            reopened_by_email="trainer@exemplu.invalid",
        )

    assert excinfo.value.code == "reopen_no_response"
    assert session.added == []


@pytest.mark.asyncio
async def test_participant_cannot_reach_the_reopen_endpoint() -> None:
    """Un participant primeste refuz chiar daca trimite cererea direct, fara ecran."""
    participant = SessionPrincipal(
        user_id=uuid.uuid4(),
        email="participant@example.com",
        role=UserRole.participant,
        session_token="test-session",  # noqa: S106
    )

    with pytest.raises(HTTPException) as excinfo:
        await assignments_router.reopen_company_assignment(
            COMPANY_ID,
            ASSIGNMENT_ID,
            participant,
            cast(Any, None),
        )

    assert excinfo.value.status_code == 403
