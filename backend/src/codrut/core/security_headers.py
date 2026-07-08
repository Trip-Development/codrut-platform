from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from codrut.core.config import Settings, get_settings

API_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def install_security_headers_middleware(app: FastAPI, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()

    @app.middleware("http")
    async def security_headers_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if not active_settings.security_headers_enabled:
            return response

        for name, value in API_SECURITY_HEADERS.items():
            if name not in response.headers:
                response.headers[name] = value

        if active_settings.is_production and "Strict-Transport-Security" not in response.headers:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={active_settings.security_hsts_max_age_seconds}; includeSubDomains"
            )

        return response
