import hashlib

import httpx
import pytest

from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.identity.password_breach import ensure_password_not_breached


@pytest.mark.asyncio
async def test_breach_lookup_uses_k_anonymity_and_rejects_matching_suffix() -> None:
    password = "o frază compromisă pentru test"  # noqa: S105
    digest = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(digest[:5])
        assert request.headers["Add-Padding"] == "true"
        return httpx.Response(200, text=f"{digest[5:]}:42\nDEADBEEF:0\n")

    settings = Settings(password_breach_check_enabled=True)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(DomainError) as exc_info:
            await ensure_password_not_breached(password, settings=settings, client=client)

    assert exc_info.value.code == "password_breached"


@pytest.mark.asyncio
async def test_breach_lookup_allows_unmatched_password() -> None:
    settings = Settings(password_breach_check_enabled=True)
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text="DEADBEEF:3\n"))

    async with httpx.AsyncClient(transport=transport) as client:
        await ensure_password_not_breached(
            "o frază care nu apare în răspuns",  # noqa: S106
            settings=settings,
            client=client,
        )


@pytest.mark.asyncio
async def test_breach_lookup_fails_open_when_provider_is_unavailable() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    settings = Settings(password_breach_check_enabled=True)
    async with httpx.AsyncClient(transport=httpx.MockTransport(unavailable)) as client:
        await ensure_password_not_breached(
            "o frază suficient de lungă",  # noqa: S106
            settings=settings,
            client=client,
        )
