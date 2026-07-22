from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import codrut.modules.identity.router as identity_router
from codrut.api.dependencies import current_principal, db_session
from codrut.core.config import Settings
from codrut.core.csrf import install_csrf_middleware
from codrut.core.errors import DomainError, install_exception_handlers
from codrut.core.rate_limit import RateLimitDecision, install_rate_limit_middleware
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.router import router
from codrut.modules.identity.schemas import InviteVerifyResponse, SessionPrincipal
from codrut.modules.identity.service import InviteVerifyResult
from codrut.modules.identity.session_cookie import SESSION_COOKIE_NAME


class FakeDatabaseSession:
    def __init__(self) -> None:
        self.commit_count = 0

    async def commit(self) -> None:
        self.commit_count += 1


class StubIdentityService:
    verify_calls: list[str] = []
    exchange_calls: list[tuple[str, str | None]] = []
    logout_calls: list[str] = []
    exchange_session_token: str | None = "new-session-token"  # noqa: S105
    reject_exchange = False

    def __init__(self, _session: FakeDatabaseSession) -> None:
        pass

    async def verify_invite_token(self, token: str) -> InviteVerifyResponse:
        self.verify_calls.append(token)
        return invite_response()

    async def verify_invite_token_and_create_session(
        self,
        token: str,
        *,
        existing_session_token: str | None = None,
    ) -> InviteVerifyResult:
        self.exchange_calls.append((token, existing_session_token))
        if self.reject_exchange:
            raise DomainError(
                "The invitation belongs to a different authenticated user.",
                code="invite_session_conflict",
            )
        return InviteVerifyResult(
            response=invite_response(),
            session_token=self.exchange_session_token,
        )

    async def logout(self, token: str) -> None:
        self.logout_calls.append(token)


class CountingRateLimiter:
    def __init__(self) -> None:
        self.count = 0

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        self.count += 1
        return RateLimitDecision(
            allowed=self.count <= limit,
            retry_after_seconds=window_seconds if self.count > limit else None,
        )


def invite_response() -> InviteVerifyResponse:
    return InviteVerifyResponse(
        email="invite@example.com",
        full_name="Invite Participant",
        is_leadership=False,
        already_registered=False,
        project_name="Invite Project",
        expires_at=datetime.now(UTC) + timedelta(days=5),
        token_status="active",  # noqa: S106
        tasks=[],
    )


def create_test_app(
    monkeypatch: pytest.MonkeyPatch,
    database_session: FakeDatabaseSession,
    *,
    csrf: bool = False,
    limiter: CountingRateLimiter | None = None,
) -> FastAPI:
    StubIdentityService.verify_calls = []
    StubIdentityService.exchange_calls = []
    StubIdentityService.logout_calls = []
    StubIdentityService.exchange_session_token = "new-session-token"  # noqa: S105
    StubIdentityService.reject_exchange = False
    monkeypatch.setattr(identity_router, "IdentityService", StubIdentityService)

    app = FastAPI()
    if limiter is not None:
        install_rate_limit_middleware(
            app,
            settings=Settings(
                rate_limit_enabled=True,
                rate_limit_max_requests=1,
                rate_limit_window_seconds=30,
            ),
            limiter=limiter,
        )
    if csrf:
        install_csrf_middleware(app, session_cookie_name=SESSION_COOKIE_NAME)
    install_exception_handlers(app)
    app.include_router(router, prefix="/api/auth")

    async def database_override():
        yield database_session

    async def principal_override() -> SessionPrincipal:
        return SessionPrincipal(
            user_id="11111111-1111-4111-8111-111111111111",
            email="trainer@example.com",
            role=UserRole.trainer,
            session_token="active-session-token",  # noqa: S106
        )

    app.dependency_overrides[db_session] = database_override
    app.dependency_overrides[current_principal] = principal_override
    return app


def test_logout_uses_declared_no_content_response_and_clears_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_session = FakeDatabaseSession()
    client = TestClient(create_test_app(monkeypatch, database_session))
    client.cookies.set(SESSION_COOKIE_NAME, "active-session-token")

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert response.content == b""
    assert database_session.commit_count == 1
    assert StubIdentityService.logout_calls == ["active-session-token"]
    assert f'{SESSION_COOKIE_NAME}=""' in response.headers["set-cookie"]


def test_invite_get_is_read_only_and_does_not_set_a_session_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_session = FakeDatabaseSession()
    client = TestClient(create_test_app(monkeypatch, database_session))

    response = client.get("/api/auth/invite/verify", params={"token": "invite-token"})

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert database_session.commit_count == 0
    assert StubIdentityService.verify_calls == ["invite-token"]
    assert SESSION_COOKIE_NAME not in response.headers.get("set-cookie", "")


def test_invite_post_exchanges_session_without_overwriting_another_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_session = FakeDatabaseSession()
    client = TestClient(create_test_app(monkeypatch, database_session))
    client.cookies.set(SESSION_COOKIE_NAME, "existing-session")
    StubIdentityService.reject_exchange = True

    response = client.post(
        "/api/auth/invite/exchange",
        json={"token": "invite-token"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invite_session_conflict"
    assert database_session.commit_count == 0
    assert StubIdentityService.exchange_calls == [("invite-token", "existing-session")]
    assert SESSION_COOKIE_NAME not in response.headers.get("set-cookie", "")


def test_invite_exchange_post_is_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    database_session = FakeDatabaseSession()
    limiter = CountingRateLimiter()
    client = TestClient(create_test_app(monkeypatch, database_session, limiter=limiter))

    first = client.post("/api/auth/invite/exchange", json={"token": "invite-token"})
    second = client.post("/api/auth/invite/exchange", json={"token": "invite-token"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "30"
    assert limiter.count == 2


def test_invite_exchange_requires_csrf_when_a_session_cookie_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_session = FakeDatabaseSession()
    client = TestClient(create_test_app(monkeypatch, database_session, csrf=True))
    client.cookies.set(SESSION_COOKIE_NAME, "existing-session")

    response = client.post(
        "/api/auth/invite/exchange",
        json={"token": "invite-token"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert StubIdentityService.exchange_calls == []


def test_invite_exchange_allows_unauthenticated_public_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_session = FakeDatabaseSession()
    client = TestClient(create_test_app(monkeypatch, database_session, csrf=True))

    response = client.post(
        "/api/auth/invite/exchange",
        json={"token": "invite-token"},
    )

    assert response.status_code == 200
    assert database_session.commit_count == 1
    assert StubIdentityService.exchange_calls == [("invite-token", None)]
    assert response.cookies[SESSION_COOKIE_NAME] == "new-session-token"
