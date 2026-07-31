import hmac
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette import status

from codrut.core.config import Settings, get_settings
from codrut.core.errors import error_response

MAINTENANCE_BYPASS_HEADER = "X-Codrut-Maintenance-Token"
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
ALWAYS_AVAILABLE_MUTATION_PATHS = frozenset(
    {
        "/api/communications/webhooks/brevo",
    }
)


def install_maintenance_middleware(
    app: FastAPI,
    settings: Settings | None = None,
) -> None:
    active_settings = settings or get_settings()

    @app.middleware("http")
    async def maintenance_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if (
            not active_settings.maintenance_mode
            or request.method.upper() not in MUTATING_METHODS
            or _mutation_remains_available(request.url.path)
            or _has_valid_bypass(request, active_settings)
        ):
            return await call_next(request)

        return error_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="maintenance_mode",
            message="Platforma este temporar în mentenanță. Încearcă din nou în câteva minute.",
            headers={"Retry-After": "60"},
        )


def _mutation_remains_available(path: str) -> bool:
    return (
        path in ALWAYS_AVAILABLE_MUTATION_PATHS
        or path.startswith("/api/communications/campaigns/unsubscribe/")
    )


def _has_valid_bypass(request: Request, settings: Settings) -> bool:
    configured = (
        settings.maintenance_bypass_token.get_secret_value().strip()
        if settings.maintenance_bypass_token
        else ""
    )
    supplied = request.headers.get(MAINTENANCE_BYPASS_HEADER, "")
    return bool(configured and supplied and hmac.compare_digest(configured, supplied))
