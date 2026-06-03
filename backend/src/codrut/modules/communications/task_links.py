import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import UUID

from codrut.core.config import Settings
from codrut.core.errors import DomainError


@dataclass(frozen=True)
class TaskLinkClaims:
    company_id: UUID
    respondent_profile_id: UUID
    assignment_ids: tuple[UUID, ...]
    expires_at: datetime


def create_task_token(claims: TaskLinkClaims, settings: Settings) -> str:
    payload = {
        "company_id": str(claims.company_id),
        "respondent_profile_id": str(claims.respondent_profile_id),
        "assignment_ids": [str(assignment_id) for assignment_id in claims.assignment_ids],
        "expires_at": int(claims.expires_at.timestamp()),
    }
    encoded_payload = _urlsafe_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signature = _sign(encoded_payload, settings)
    return f"{encoded_payload}.{signature}"


def parse_task_token(
    token: str,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> TaskLinkClaims:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise DomainError("Invalid task link.", code="task_link_invalid") from exc
    expected = _sign(encoded_payload, settings)
    if not hmac.compare_digest(signature, expected):
        raise DomainError("Invalid task link.", code="task_link_invalid")
    payload = json.loads(_urlsafe_decode(encoded_payload))
    expires_at = datetime.fromtimestamp(payload["expires_at"], UTC)
    if expires_at <= (now or datetime.now(UTC)):
        raise DomainError("Task link has expired.", code="task_link_expired")
    return TaskLinkClaims(
        company_id=UUID(payload["company_id"]),
        respondent_profile_id=UUID(payload["respondent_profile_id"]),
        assignment_ids=tuple(UUID(value) for value in payload["assignment_ids"]),
        expires_at=expires_at,
    )


def build_task_url(token: str, settings: Settings) -> str:
    base_url = settings.public_app_url.rstrip("/")
    return f"{base_url}/participant?{urlencode({'taskToken': token})}"


def _sign(encoded_payload: str, settings: Settings) -> str:
    digest = hmac.new(
        settings.session_secret.get_secret_value().encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).digest()
    return _urlsafe_encode(digest)


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode())
