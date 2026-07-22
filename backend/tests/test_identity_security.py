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
        "prea-scurta",
        "password1234",
        "qwerty123456",
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


def test_new_password_policy_accepts_long_passphrases_without_composition_rules() -> None:
    password = "o frază lungă și memorabilă"  # noqa: S105

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


def test_new_password_policy_accepts_unicode_passphrases() -> None:
    password = "Învăț în fiecare săptămână"  # noqa: S105

    register = RegisterRequest(
        email="participant@example.com",
        password=password,
        token="invite-token",  # noqa: S106
        terms_accepted=True,
    )

    assert register.password == password


def test_new_password_policy_rejects_passwords_over_maximum_length() -> None:
    with pytest.raises(ValidationError):
        PasswordResetConfirmRequest(
            token="x" * 32,
            password="Aa1!" + ("a" * 125),
        )


def test_session_cookie_uses_90_day_max_age() -> None:
    response = Response()

    set_session_cookie(response, "session-token")

    cookie = response.headers["set-cookie"]
    assert "codrut_session=session-token" in cookie
    assert f"Max-Age={SESSION_COOKIE_MAX_AGE_SECONDS}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
