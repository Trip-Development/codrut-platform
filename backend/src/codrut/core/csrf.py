import hmac
from collections.abc import Awaitable, Callable
from datetime import timedelta
from hashlib import sha256
from re import Pattern, compile

from fastapi import FastAPI, Request, Response
from starlette import status

from codrut.core.config import Settings, get_settings
from codrut.core.errors import error_response

CSRF_COOKIE_NAME = "codrut_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_MAX_AGE_SECONDS = int(timedelta(days=90).total_seconds())

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
PUBLIC_UNSAFE_EXACT_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/reset-password",
        "/api/auth/reset-password/confirm",
        "/api/companies/access-code-registration",
    }
)
PUBLIC_UNSAFE_PATTERNS: tuple[Pattern[str], ...] = (
    compile(r"^/api/communications/campaigns/recipients/[^/]+/events$"),
    compile(r"^/api/communications/campaigns/unsubscribe/[^/]+$"),
)


def csrf_token_for_session(session_token: str, settings: Settings | None = None) -> str:
    active_settings = settings or get_settings()
    return hmac.new(
        active_settings.session_secret.get_secret_value().encode("utf-8"),
        session_token.encode("utf-8"),
        sha256,
    ).hexdigest()


def is_valid_csrf_token(
    session_token: str,
    csrf_token: str,
    settings: Settings | None = None,
) -> bool:
    expected_token = csrf_token_for_session(session_token, settings)
    return hmac.compare_digest(expected_token, csrf_token)


def set_csrf_cookie(
    response: Response,
    session_token: str,
    settings: Settings | None = None,
) -> None:
    active_settings = settings or get_settings()
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token_for_session(session_token, active_settings),
        max_age=CSRF_COOKIE_MAX_AGE_SECONDS,
        httponly=False,
        secure=active_settings.is_production,
        samesite="lax",
        path="/",
    )


def delete_csrf_cookie(response: Response, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        secure=active_settings.is_production,
        httponly=False,
        samesite="lax",
    )


def is_csrf_exempt_request(request: Request) -> bool:
    if request.method.upper() in SAFE_METHODS:
        return True

    path = request.url.path
    if path in PUBLIC_UNSAFE_EXACT_PATHS:
        return True

    return any(pattern.match(path) for pattern in PUBLIC_UNSAFE_PATTERNS)


def install_csrf_middleware(app: FastAPI, *, session_cookie_name: str) -> None:
    @app.middleware("http")
    async def csrf_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        session_token = request.cookies.get(session_cookie_name)

        if session_token and not is_csrf_exempt_request(request):
            csrf_header = request.headers.get(CSRF_HEADER_NAME)
            csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
            if not csrf_header or not csrf_cookie:
                response = _csrf_error(request, "CSRF token is required.")
                set_csrf_cookie(response, session_token, settings)
                return response
            if not hmac.compare_digest(csrf_header, csrf_cookie) or not is_valid_csrf_token(
                session_token,
                csrf_header,
                settings,
            ):
                response = _csrf_error(request, "CSRF token is invalid.")
                set_csrf_cookie(response, session_token, settings)
                return response

        response = await call_next(request)
        if session_token and not (
            response_sets_cookie(response, session_cookie_name)
            or response_sets_cookie(response, CSRF_COOKIE_NAME)
        ):
            set_csrf_cookie(response, session_token, settings)
        return response


def response_sets_cookie(response: Response, name: str) -> bool:
    prefix = f"{name.lower()}=".encode("latin-1")
    return any(
        header_name.lower() == b"set-cookie" and header_value.lower().startswith(prefix)
        for header_name, header_value in response.raw_headers
    )


def _csrf_error(request: Request, message: str) -> Response:
    return error_response(
        request,
        status_code=status.HTTP_403_FORBIDDEN,
        code="csrf_failed",
        message=message,
    )
