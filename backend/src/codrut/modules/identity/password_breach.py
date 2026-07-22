import logging
from hashlib import sha1

import httpx

from codrut.core.config import Settings, get_settings
from codrut.core.errors import DomainError

logger = logging.getLogger(__name__)


async def ensure_password_not_breached(
    password: str,
    *,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> None:
    active_settings = settings or get_settings()
    if not active_settings.password_breach_check_enabled:
        return

    digest = sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]

    try:
        if client is not None:
            response = await _request_range(client, active_settings, prefix)
        else:
            async with httpx.AsyncClient(
                timeout=active_settings.password_breach_timeout_seconds,
                follow_redirects=False,
            ) as owned_client:
                response = await _request_range(owned_client, active_settings, prefix)
    except httpx.HTTPError as exc:
        logger.warning("Password breach lookup unavailable: %s", type(exc).__name__)
        return

    if _range_contains_suffix(response.text, suffix):
        raise DomainError(
            "Parola apare într-o listă de parole compromise. Alege o altă frază.",
            code="password_breached",
        )


async def _request_range(
    client: httpx.AsyncClient,
    settings: Settings,
    prefix: str,
) -> httpx.Response:
    response = await client.get(
        f"{settings.password_breach_api_url.rstrip('/')}/{prefix}",
        headers={
            "Add-Padding": "true",
            "User-Agent": "Codrut-Platform-Password-Safety",
        },
    )
    response.raise_for_status()
    return response


def _range_contains_suffix(payload: str, suffix: str) -> bool:
    expected = suffix.upper()
    for line in payload.splitlines():
        candidate, separator, count = line.partition(":")
        if separator and candidate.strip().upper() == expected:
            try:
                return int(count.strip()) > 0
            except ValueError:
                return False
    return False
