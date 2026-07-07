from datetime import timedelta

from fastapi import Response

from codrut.core.config import get_settings

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


def delete_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
