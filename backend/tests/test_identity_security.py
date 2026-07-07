import pytest
from pydantic import ValidationError
from starlette.responses import Response

from codrut.core.security import hash_password, verify_password
from codrut.modules.identity.schemas import (
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    RegisterRequest,
)
from codrut.modules.identity.session_cookie import (
    SESSION_COOKIE_MAX_AGE_SECONDS,
    set_session_cookie,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


@pytest.mark.parametrize(
    "password",
    [
        "Short1!",
        "lowercase1!",
        "UPPERCASE1!",
        "NoNumber!",
        "NoSpecial1",
    ],
)
def test_new_password_policy_rejects_incomplete_passwords(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="participant@example.com",
            password=password,
            token="invite-token",  # noqa: S106
            terms_accepted=True,
        )


def test_new_password_policy_accepts_eight_char_complex_passwords() -> None:
    password = "Aa12345!"  # noqa: S105

    register = RegisterRequest(
        email="participant@example.com",
        password=password,
        token="invite-token",  # noqa: S106
        terms_accepted=True,
    )
    reset = PasswordResetConfirmRequest(
        token="x" * 32,
        password=password,
    )
    change = PasswordChangeRequest(
        current_password="old-password",  # noqa: S106
        new_password=password,
    )

    assert register.password == password
    assert reset.password == password
    assert change.new_password == password


def test_session_cookie_uses_90_day_max_age() -> None:
    response = Response()

    set_session_cookie(response, "session-token")

    cookie = response.headers["set-cookie"]
    assert "codrut_session=session-token" in cookie
    assert f"Max-Age={SESSION_COOKIE_MAX_AGE_SECONDS}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
