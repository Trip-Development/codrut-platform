from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette import status

from codrut.core.config import Settings, get_settings
from codrut.core.errors import error_response

BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def install_request_limit_middleware(app: FastAPI, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()

    @app.middleware("http")
    async def request_limit_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method.upper() not in BODY_METHODS:
            return await call_next(request)

        declared_length = request.headers.get("content-length")
        if declared_length is None:
            return await call_next(request)

        try:
            size_bytes = int(declared_length)
        except ValueError:
            return error_response(
                request,
                status_code=status.HTTP_400_BAD_REQUEST,
                code="request_length_invalid",
                message="Request Content-Length is invalid.",
            )

        if size_bytes > active_settings.api_request_max_bytes:
            return error_response(
                request,
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                code="request_too_large",
                message="Request body exceeds the configured size limit.",
            )

        return await call_next(request)
