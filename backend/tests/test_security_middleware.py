from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from codrut.api.dependencies import current_principal
from codrut.core.config import Settings, get_settings
from codrut.core.rate_limit import RateLimitDecision, install_rate_limit_middleware
from codrut.core.request_id import REQUEST_ID_HEADER, install_request_id_middleware
from codrut.core.request_limits import install_request_limit_middleware
from codrut.core.security_headers import install_security_headers_middleware
from codrut.main import create_app
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


class CountingRateLimiter:
    def __init__(self) -> None:
        self.count = 0

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        self.count += 1
        return RateLimitDecision(
            allowed=self.count <= limit,
            retry_after_seconds=window_seconds if self.count > limit else None,
        )


def create_middleware_test_app(
    settings: Settings,
    limiter: CountingRateLimiter | None = None,
) -> FastAPI:
    app = FastAPI()
    install_rate_limit_middleware(app, settings=settings, limiter=limiter)
    install_request_limit_middleware(app, settings=settings)
    install_security_headers_middleware(app, settings=settings)
    install_request_id_middleware(app)

    @app.get("/api/ok")
    async def ok() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/echo")
    async def echo() -> dict[str, bool]:
        return {"ok": True}

    return app


def trainer_principal() -> SessionPrincipal:
    return SessionPrincipal(
        user_id=uuid4(),
        email="trainer@example.com",
        role=UserRole.trainer,
        session_token="test-session",  # noqa: S106
    )


def test_api_responses_include_conservative_security_headers() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_header_is_added_only_for_production_settings() -> None:
    settings = Settings(env="production", security_hsts_max_age_seconds=3600)
    client = TestClient(create_middleware_test_app(settings))

    response = client.get("/api/ok")

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == "max-age=3600; includeSubDomains"


def test_request_size_limit_rejects_large_declared_bodies() -> None:
    settings = Settings(api_request_max_bytes=4)
    client = TestClient(create_middleware_test_app(settings))

    response = client.post(
        "/api/echo",
        content=b"12345",
        headers={REQUEST_ID_HEADER: "req-large"},
    )

    assert response.status_code == 413
    assert response.headers[REQUEST_ID_HEADER] == "req-large"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.json() == {
        "error": {
            "code": "request_too_large",
            "message": "Request body exceeds the configured size limit.",
            "request_id": "req-large",
        }
    }


def test_campaign_asset_upload_limit_still_owns_normal_asset_rejections() -> None:
    settings = Settings(campaign_asset_max_bytes=4, api_request_max_bytes=8)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings

    async def principal_override() -> SessionPrincipal:
        return trainer_principal()

    app.dependency_overrides[current_principal] = principal_override
    client = TestClient(app)

    response = client.post(
        "/api/communications/campaign-assets",
        content=b"12345",
        headers={"content-type": "image/png", "x-file-name": "mini.png"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "campaign_asset_too_large"


def test_rate_limiter_hook_can_block_unsafe_requests() -> None:
    limiter = CountingRateLimiter()
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_max_requests=1,
        rate_limit_window_seconds=30,
    )
    client = TestClient(create_middleware_test_app(settings, limiter))

    first = client.post("/api/echo")
    second = client.post("/api/echo", headers={REQUEST_ID_HEADER: "req-rate"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "30"
    assert second.headers[REQUEST_ID_HEADER] == "req-rate"
    assert second.headers["X-Content-Type-Options"] == "nosniff"
    assert second.json() == {
        "error": {
            "code": "rate_limited",
            "message": "Too many requests.",
            "request_id": "req-rate",
        }
    }
