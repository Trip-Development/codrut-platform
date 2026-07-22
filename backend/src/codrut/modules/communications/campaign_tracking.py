import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote, urlparse
from uuid import UUID

from codrut.core.config import Settings
from codrut.core.errors import DomainError


@dataclass(frozen=True)
class CampaignTrackingClaims:
    recipient_id: UUID
    owner_id: UUID
    target_url: str
    event_type: str
    expires_at: datetime
    variant_key: str | None = None


@dataclass(frozen=True)
class CampaignRecipientActionClaims:
    recipient_id: UUID
    owner_id: UUID
    action: str


def create_campaign_tracking_token(claims: CampaignTrackingClaims, settings: Settings) -> str:
    _validate_tracking_target(claims.target_url, event_type=claims.event_type)
    payload = {
        "recipient_id": str(claims.recipient_id),
        "owner_id": str(claims.owner_id),
        "target_url": claims.target_url,
        "event_type": claims.event_type,
        "expires_at": int(claims.expires_at.timestamp()),
        "variant_key": claims.variant_key,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded_payload = _urlsafe_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signature = _sign(encoded_payload, settings)
    return f"{encoded_payload}.{signature}"


def parse_campaign_tracking_token(
    token: str,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> CampaignTrackingClaims:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise DomainError(
            "Invalid campaign tracking link.",
            code="campaign_tracking_invalid",
        ) from exc
    expected = _sign(encoded_payload, settings)
    if not hmac.compare_digest(signature, expected):
        raise DomainError("Invalid campaign tracking link.", code="campaign_tracking_invalid")
    try:
        payload = json.loads(_urlsafe_decode(encoded_payload))
        claims = CampaignTrackingClaims(
            recipient_id=UUID(payload["recipient_id"]),
            owner_id=UUID(payload["owner_id"]),
            target_url=str(payload["target_url"]),
            event_type=str(payload["event_type"]),
            expires_at=datetime.fromtimestamp(payload["expires_at"], UTC),
            variant_key=payload.get("variant_key"),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DomainError(
            "Invalid campaign tracking link.",
            code="campaign_tracking_invalid",
        ) from exc
    if claims.expires_at <= (now or datetime.now(UTC)):
        raise DomainError("Campaign tracking link has expired.", code="campaign_tracking_expired")
    _validate_tracking_target(claims.target_url, event_type=claims.event_type)
    return claims


def build_campaign_tracking_url(
    token: str,
    settings: Settings,
    *,
    event_type: str = "calendly_clicked",
) -> str:
    base_url = settings.public_app_url.rstrip("/")
    path_event = "calendly" if event_type == "calendly_clicked" else event_type
    return f"{base_url}/api/communications/campaigns/track/{path_event}/{quote(token, safe='')}"


def create_campaign_recipient_action_token(
    claims: CampaignRecipientActionClaims,
    settings: Settings,
) -> str:
    payload = {
        "recipient_id": str(claims.recipient_id),
        "owner_id": str(claims.owner_id),
        "action": claims.action,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded_payload = _urlsafe_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signature = _sign(encoded_payload, settings)
    return f"{encoded_payload}.{signature}"


def parse_campaign_recipient_action_token(
    token: str,
    settings: Settings,
) -> CampaignRecipientActionClaims:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise DomainError(
            "Invalid campaign recipient action link.",
            code="campaign_recipient_action_invalid",
        ) from exc
    expected = _sign(encoded_payload, settings)
    if not hmac.compare_digest(signature, expected):
        raise DomainError(
            "Invalid campaign recipient action link.",
            code="campaign_recipient_action_invalid",
        )
    try:
        payload = json.loads(_urlsafe_decode(encoded_payload))
        return CampaignRecipientActionClaims(
            recipient_id=UUID(payload["recipient_id"]),
            owner_id=UUID(payload["owner_id"]),
            action=str(payload["action"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DomainError(
            "Invalid campaign recipient action link.",
            code="campaign_recipient_action_invalid",
        ) from exc


def build_campaign_unsubscribe_url(token: str, settings: Settings) -> str:
    base_url = settings.public_app_url.rstrip("/")
    return f"{base_url}/api/communications/campaigns/unsubscribe/{quote(token, safe='')}"


def _validate_tracking_target(target_url: str, *, event_type: str) -> None:
    parsed = urlparse(target_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DomainError(
            "Campaign tracking target must be an absolute HTTP(S) URL.",
            code="campaign_tracking_invalid_target",
        )
    if event_type != "calendly_clicked":
        return
    host = parsed.hostname or ""
    if host != "calendly.com" and not host.endswith(".calendly.com"):
        raise DomainError(
            "Campaign tracking target must be a Calendly URL.",
            code="campaign_tracking_invalid_target",
        )


def _sign(encoded_payload: str, settings: Settings) -> str:
    digest = hmac.new(
        settings.effective_task_link_secret.encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).digest()
    return _urlsafe_encode(digest)


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode())
