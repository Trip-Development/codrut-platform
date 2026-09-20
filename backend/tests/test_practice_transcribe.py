from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from codrut.api.dependencies import current_principal
from codrut.core.config import get_settings
from codrut.main import create_app
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION


def _aplicatia_cu_participant():
    """Aplicația, cu un participant autentificat — plicul 122.

    Testele astea cereau o fixtură, `test_db_session`, care nu există nicăieri în depozit, și
    treceau `settings=` lui `create_app()`, care nu primește argumente. Deci n-au rulat
    NICIODATĂ: pytest le raporta ca eroare de colectare, iar eroarea se număra printre cele 16
    roșii. Acum se pregătesc ca toate celelalte teste de rută (vezi `test_communications_router`).
    """
    app = create_app()
    setari = get_settings().model_copy(update={"generation_provider": "local"})

    async def principal_override() -> SessionPrincipal:
        return SessionPrincipal(
            user_id=uuid.uuid4(),
            email="participant@example.com",
            role=UserRole.participant,
            terms_accepted_at=datetime.now(UTC),
            terms_version=CURRENT_TERMS_VERSION,
            session_token="test-session",  # noqa: S106
        )

    app.dependency_overrides[current_principal] = principal_override
    app.dependency_overrides[get_settings] = lambda: setari
    return app


@pytest.mark.asyncio
async def test_transcribe_endpoint() -> None:
    app = _aplicatia_cu_participant()

    dummy_audio = io.BytesIO(b"RIFFdummywavecontent1234567890")
    files = {"file": ("test.wav", dummy_audio, "audio/wav")}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/practice/transcribe", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert len(data["text"]) > 0


@pytest.mark.asyncio
async def test_dashboard_endpoint() -> None:
    app = _aplicatia_cu_participant()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/practice/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "xp_today" in data
        assert "streak_days" in data
        assert "competencies" in data
        assert isinstance(data["competencies"], list)
