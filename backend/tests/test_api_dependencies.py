import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import codrut.api.dependencies as dependencies
from codrut.api.dependencies import CURRENT_TERMS_VERSION, current_principal, require_current_terms
from codrut.core.errors import DomainError
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


def principal(
    *,
    role: UserRole = UserRole.participant,
    terms_accepted_at: datetime | None = None,
    terms_version: str | None = None,
) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=uuid.uuid4(),
        email="participant@example.com",
        role=role,
        terms_accepted_at=terms_accepted_at,
        terms_version=terms_version,
        session_token="test-session",  # noqa: S106
    )


def auth_request(
    *,
    role: str | None = None,
    cookie: str | None = None,
    host: str = "localhost",
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if role is not None:
        headers.append((b"x-codrut-dev-role", role.encode()))
    if cookie is not None:
        headers.append((b"cookie", f"codrut_session={cookie}".encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "server": (host, 80),
            "scheme": "http",
        }
    )


def local_auth_settings(*, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        local_auth_bypass=enabled,
        local_auth_trainer_email="trainer@example.com",
        local_auth_participant_email="participant@example.com",
    )


@pytest.mark.asyncio
async def test_current_principal_requires_auth_when_local_bypass_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dependencies, "get_settings", lambda: local_auth_settings(enabled=False))

    with pytest.raises(HTTPException) as exc_info:
        await current_principal(auth_request(), AsyncMock())

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_current_principal_uses_route_role_before_existing_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = principal(
        role=UserRole.participant,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
    )
    service = MagicMock()
    service.principal_for_local_user = AsyncMock(return_value=expected)
    service.principal_from_session_token = AsyncMock()
    monkeypatch.setattr(dependencies, "get_settings", local_auth_settings)
    monkeypatch.setattr(dependencies, "IdentityService", lambda _session: service)

    result = await current_principal(
        auth_request(role="participant", cookie="trainer-cookie"),
        AsyncMock(),
    )

    assert result == expected
    service.principal_for_local_user.assert_awaited_once_with(
        email="participant@example.com",
        role=UserRole.participant,
    )
    service.principal_from_session_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_current_principal_rejects_invalid_local_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dependencies, "get_settings", local_auth_settings)

    with pytest.raises(HTTPException) as exc_info:
        await current_principal(auth_request(role="admin"), AsyncMock())

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_current_principal_does_not_bypass_auth_on_remote_development_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dependencies, "get_settings", local_auth_settings)

    with pytest.raises(HTTPException) as exc_info:
        await current_principal(
            auth_request(role="trainer", host="preview.example.com"),
            AsyncMock(),
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_current_principal_reports_missing_seed_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MagicMock()
    service.principal_for_local_user = AsyncMock(return_value=None)
    monkeypatch.setattr(dependencies, "get_settings", local_auth_settings)
    monkeypatch.setattr(dependencies, "IdentityService", lambda _session: service)

    with pytest.raises(HTTPException) as exc_info:
        await current_principal(auth_request(role="trainer"), AsyncMock())

    assert exc_info.value.status_code == 503
    assert "local preview seed" in str(exc_info.value.detail).lower()


def test_require_current_terms_allows_current_participant_consent() -> None:
    require_current_terms(
        principal(
            terms_accepted_at=datetime.now(UTC),
            terms_version=CURRENT_TERMS_VERSION,
        )
    )


def test_require_current_terms_blocks_unaccepted_participant_consent() -> None:
    with pytest.raises(DomainError) as exc_info:
        require_current_terms(principal())

    assert exc_info.value.code == "terms_required"


def test_require_current_terms_blocks_stale_participant_consent() -> None:
    with pytest.raises(DomainError) as exc_info:
        require_current_terms(
            principal(
                terms_accepted_at=datetime.now(UTC),
                terms_version="privacy-2025-01-01",
            )
        )

    assert exc_info.value.code == "terms_required"


def test_require_current_terms_does_not_apply_to_trainers() -> None:
    require_current_terms(principal(role=UserRole.trainer))
