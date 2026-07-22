from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from codrut.api.dependencies import current_principal, db_session
from codrut.main import create_app
from codrut.modules.companies.schemas import (
    ParticipantInvitationStatusResponse,
    ParticipantInviteBatchResponse,
    RosterImportResponse,
)
from codrut.modules.companies.service import CompanyService
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


def test_company_object_routes_require_authenticated_actor() -> None:
    app = create_app()

    async def db_override():
        yield None

    app.dependency_overrides[db_session] = db_override

    response = TestClient(app).get(f"/api/companies/{uuid4()}/participants")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "http_401"


def test_company_listing_is_scoped_to_current_trainer(monkeypatch) -> None:
    trainer_id = uuid4()
    app = create_app()

    async def principal_override() -> SessionPrincipal:
        return SessionPrincipal(
            user_id=trainer_id,
            email="trainer@example.com",
            role=UserRole.trainer,
            terms_accepted_at=datetime.now(UTC),
            terms_version="privacy-2026-07-16",
            session_token="test-session",  # noqa: S106
        )

    async def db_override():
        yield None

    async def list_companies_override(self, user_id):
        assert user_id == trainer_id
        return []

    app.dependency_overrides[current_principal] = principal_override
    app.dependency_overrides[db_session] = db_override
    monkeypatch.setattr(CompanyService, "list_companies", list_companies_override)

    response = TestClient(app).get("/api/companies")

    assert response.status_code == 200
    assert response.json() == []


def test_invitation_routes_forward_assessment_cycle_scope(monkeypatch) -> None:
    trainer_id = uuid4()
    company_id = uuid4()
    participant_id = uuid4()
    project_id = uuid4()
    assessment_cycle_id = uuid4()
    calls: dict[str, tuple] = {}

    class CommitTrackingSession:
        def __init__(self) -> None:
            self.commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    session = CommitTrackingSession()
    app = create_app()

    async def principal_override() -> SessionPrincipal:
        return SessionPrincipal(
            user_id=trainer_id,
            email="trainer@example.com",
            role=UserRole.trainer,
            terms_accepted_at=datetime.now(UTC),
            terms_version="privacy-2026-07-16",
            session_token="test-session",  # noqa: S106
        )

    async def db_override():
        yield session

    async def send_override(self, user_id, requested_company_id, payload, *, idempotency_key):
        calls["send"] = (user_id, requested_company_id, payload, idempotency_key)
        return ParticipantInviteBatchResponse(
            results=[],
            total=0,
            emails_sent=0,
            emails_queued=0,
            emails_failed=0,
            links_generated=0,
        )

    async def status_override(
        self,
        user_id,
        requested_company_id,
        requested_project_id,
        requested_assessment_cycle_id,
    ):
        calls["status"] = (
            user_id,
            requested_company_id,
            requested_project_id,
            requested_assessment_cycle_id,
        )
        return [ParticipantInvitationStatusResponse(participant_id=participant_id)]

    async def resend_override(
        self,
        user_id,
        requested_company_id,
        requested_participant_id,
        requested_project_id,
        requested_assessment_cycle_id,
        *,
        idempotency_key,
    ):
        calls["resend"] = (
            user_id,
            requested_company_id,
            requested_participant_id,
            requested_project_id,
            requested_assessment_cycle_id,
            idempotency_key,
        )
        return RosterImportResponse(
            participants=[],
            email_results=[],
            total_imported=0,
            emails_sent=0,
            emails_queued=0,
            emails_failed=0,
        )

    app.dependency_overrides[current_principal] = principal_override
    app.dependency_overrides[db_session] = db_override
    monkeypatch.setattr(CompanyService, "send_participant_invites", send_override)
    monkeypatch.setattr(CompanyService, "list_participant_invitation_statuses", status_override)
    monkeypatch.setattr(CompanyService, "resend_invite", resend_override)

    client = TestClient(app)
    send_response = client.post(
        f"/api/companies/{company_id}/participants/invitations",
        json={
            "participant_ids": [str(participant_id)],
            "project_id": str(project_id),
            "assessment_cycle_id": str(assessment_cycle_id),
            "mode": "secure_links",
            "target_mode": "selected",
        },
        headers={"Idempotency-Key": "cycle-send-key"},
    )
    status_response = client.get(
        f"/api/companies/{company_id}/participants/invitations/status",
        params={
            "project_id": str(project_id),
            "assessment_cycle_id": str(assessment_cycle_id),
        },
    )
    resend_response = client.post(
        f"/api/companies/{company_id}/participants/{participant_id}/resend-invite",
        params={
            "project_id": str(project_id),
            "assessment_cycle_id": str(assessment_cycle_id),
        },
        headers={"Idempotency-Key": "cycle-resend-key"},
    )

    assert send_response.status_code == 200
    assert status_response.status_code == 200
    assert resend_response.status_code == 200
    assert calls["send"][0] == trainer_id
    assert calls["send"][1] == company_id
    assert calls["send"][3] == "cycle-send-key"
    assert calls["send"][2].project_id == project_id
    assert calls["send"][2].assessment_cycle_id == assessment_cycle_id
    assert calls["status"] == (trainer_id, company_id, project_id, assessment_cycle_id)
    assert calls["resend"] == (
        trainer_id,
        company_id,
        participant_id,
        project_id,
        assessment_cycle_id,
        "cycle-resend-key",
    )
    assert session.commit_count == 2
