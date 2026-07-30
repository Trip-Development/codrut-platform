import uuid
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from codrut.modules.assignments import router as assignments_router
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


def _trainer_principal() -> SessionPrincipal:
    return SessionPrincipal(
        user_id=uuid.uuid4(),
        email="trainer@example.com",
        role=UserRole.trainer,
        session_token="test-session",  # noqa: S106
    )


@pytest.mark.asyncio
async def test_report_routes_forward_assessment_cycle_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = uuid.uuid4()
    project_id = uuid.uuid4()
    participant_profile_id = uuid.uuid4()
    baseline_cycle_id = uuid.uuid4()
    comparison_cycle_id = uuid.uuid4()
    principal = _trainer_principal()
    assignment_service = type(
        "AssignmentServiceStub",
        (),
        {"require_company_manager": AsyncMock()},
    )()
    scoring_service = type(
        "ScoringServiceStub",
        (),
        {
            "get_company_report_aggregate": AsyncMock(return_value="aggregate"),
            "get_company_report_comparison": AsyncMock(return_value="comparison"),
            "get_icare_answer_review": AsyncMock(return_value="icare"),
            "get_leadership_member_report": AsyncMock(return_value="leadership"),
        },
    )()
    monkeypatch.setattr(
        assignments_router, "AssignmentService", lambda _session: assignment_service
    )
    monkeypatch.setattr(assignments_router, "ScoringService", lambda _session: scoring_service)
    session = cast(Any, None)

    aggregate = await assignments_router.get_company_report_aggregate(
        company_id,
        principal,
        session,
        project_id,
        comparison_cycle_id,
    )
    comparison = await assignments_router.get_company_report_comparison(
        company_id,
        principal,
        session,
        project_id,
        baseline_cycle_id,
        comparison_cycle_id,
    )
    icare = await assignments_router.get_company_icare_answer_review(
        company_id,
        principal,
        session,
        project_id,
        comparison_cycle_id,
    )
    leadership = await assignments_router.get_leadership_member_report(
        company_id,
        project_id,
        participant_profile_id,
        principal,
        session,
        comparison_cycle_id,
    )

    assert aggregate == "aggregate"
    assert comparison == "comparison"
    assert icare == "icare"
    assert leadership == "leadership"
    assert assignment_service.require_company_manager.await_count == 4
    scoring_service.get_company_report_aggregate.assert_awaited_once_with(
        company_id,
        project_id,
        comparison_cycle_id,
    )
    scoring_service.get_company_report_comparison.assert_awaited_once_with(
        company_id,
        project_id,
        baseline_cycle_id,
        comparison_cycle_id,
    )
    scoring_service.get_icare_answer_review.assert_awaited_once_with(
        company_id,
        project_id,
        comparison_cycle_id,
    )
    scoring_service.get_leadership_member_report.assert_awaited_once_with(
        company_id,
        project_id,
        participant_profile_id,
        comparison_cycle_id,
    )


@pytest.mark.asyncio
async def test_default_plan_route_forwards_source_cycle_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_cycle_id = uuid.uuid4()
    principal = _trainer_principal()
    service = type(
        "AssignmentServiceStub",
        (),
        {"build_default_assignment_plan": AsyncMock(return_value="preview")},
    )()
    monkeypatch.setattr(assignments_router, "AssignmentService", lambda _session: service)

    result = await assignments_router.get_company_default_assignment_plan(
        company_id,
        principal,
        cast(Any, None),
        project_id,
        None,
        source_cycle_id,
    )

    assert result == "preview"
    service.build_default_assignment_plan.assert_awaited_once_with(
        principal.user_id,
        company_id,
        project_id,
        None,
        source_cycle_id,
    )
