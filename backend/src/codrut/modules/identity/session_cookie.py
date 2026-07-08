from datetime import timedelta

from fastapi import Response

from codrut.core.config import get_settings
from codrut.core.csrf import delete_csrf_cookie, set_csrf_cookie

SESSION_COOKIE_NAME = "codrut_session"
SESSION_COOKIE_MAX_AGE_SECONDS = int(timedelta(days=90).total_seconds())


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
    set_csrf_cookie(response, token, settings)


def delete_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )
    delete_csrf_cookie(response, settings)
