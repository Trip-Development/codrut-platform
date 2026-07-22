from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from codrut.api.dependencies import current_principal, db_session
from codrut.main import create_app
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
