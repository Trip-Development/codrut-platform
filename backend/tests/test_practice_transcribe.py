from __future__ import annotations

import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from codrut.main import create_app
from codrut.core.config import Settings
from codrut.modules.identity.schemas import SessionPrincipal


@pytest.mark.asyncio
async def test_transcribe_endpoint(test_db_session):
    settings = Settings(
        generation_provider="local",
        jwt_secret="test-secret-key-1234567890",
    )
    app = create_app(settings=settings)

    principal = SessionPrincipal(
        user_id=uuid.uuid4(),
        email="participant@example.com",
        role="participant",
    )

    app.dependency_overrides[
        "codrut.api.dependencies.current_principal"
    ] = lambda: principal

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
async def test_dashboard_endpoint(test_db_session):
    settings = Settings(
        generation_provider="local",
        jwt_secret="test-secret-key-1234567890",
    )
    app = create_app(settings=settings)

    principal = SessionPrincipal(
        user_id=uuid.uuid4(),
        email="participant@example.com",
        role="participant",
    )

    app.dependency_overrides[
        "codrut.api.dependencies.current_principal"
    ] = lambda: principal

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/practice/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "xp_today" in data
        assert "streak_days" in data
        assert "competencies" in data
        assert isinstance(data["competencies"], list)
