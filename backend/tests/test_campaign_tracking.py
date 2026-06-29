import uuid
from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.communications.campaign_tracking import (
    CampaignRecipientActionClaims,
    CampaignTrackingClaims,
    build_campaign_tracking_url,
    build_campaign_unsubscribe_url,
    create_campaign_recipient_action_token,
    create_campaign_tracking_token,
    parse_campaign_recipient_action_token,
    parse_campaign_tracking_token,
)


def make_claims(
    *,
    target_url: str = "https://calendly.com/codrut/demo",
    event_type: str = "calendly_clicked",
    expires_at: datetime | None = None,
) -> CampaignTrackingClaims:
    return CampaignTrackingClaims(
        recipient_id=uuid.uuid4(),
        target_url=target_url,
        event_type=event_type,
        variant_key="variant_a",
        expires_at=expires_at or datetime.now(UTC) + timedelta(days=7),
    )


def test_campaign_tracking_token_round_trips_claims() -> None:
    settings = Settings()
    claims = make_claims()

    token = create_campaign_tracking_token(claims, settings)
    parsed = parse_campaign_tracking_token(token, settings)

    assert parsed.recipient_id == claims.recipient_id
    assert parsed.target_url == claims.target_url
    assert parsed.event_type == "calendly_clicked"
    assert parsed.variant_key == "variant_a"


def test_campaign_tracking_token_rejects_tampering() -> None:
    settings = Settings()
    token = create_campaign_tracking_token(make_claims(), settings)

    with pytest.raises(DomainError, match="Invalid campaign tracking link"):
        parse_campaign_tracking_token(f"{token}x", settings)


def test_campaign_tracking_token_rejects_expired_claims() -> None:
    settings = Settings()
    token = create_campaign_tracking_token(
        make_claims(expires_at=datetime.now(UTC) - timedelta(minutes=1)),
        settings,
    )

    with pytest.raises(DomainError, match="expired"):
        parse_campaign_tracking_token(token, settings)


def test_campaign_tracking_token_rejects_non_http_target() -> None:
    settings = Settings()

    with pytest.raises(DomainError, match="absolute HTTP"):
        create_campaign_tracking_token(
            make_claims(target_url="javascript:alert(1)"),
            settings,
        )


def test_campaign_tracking_token_rejects_non_calendly_target() -> None:
    settings = Settings()

    with pytest.raises(DomainError, match="Calendly URL"):
        create_campaign_tracking_token(
            make_claims(target_url="https://example.com/book-demo"),
            settings,
        )


def test_build_campaign_tracking_url_points_to_public_calendly_redirect() -> None:
    settings = Settings(public_app_url="https://codrut.andreivacaru.ro")

    url = build_campaign_tracking_url("token.value", settings)

    assert url == "https://codrut.andreivacaru.ro/api/communications/campaigns/track/calendly/token.value"


def test_campaign_recipient_action_token_round_trips_unsubscribe_claims() -> None:
    settings = Settings()
    recipient_id = uuid.uuid4()

    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=recipient_id,
            action="unsubscribe",
        ),
        settings,
    )
    parsed = parse_campaign_recipient_action_token(token, settings)

    assert parsed.recipient_id == recipient_id
    assert parsed.action == "unsubscribe"


def test_build_campaign_unsubscribe_url_points_to_public_endpoint() -> None:
    settings = Settings(public_app_url="https://codrut.andreivacaru.ro")

    url = build_campaign_unsubscribe_url("token.value", settings)

    assert url == "https://codrut.andreivacaru.ro/api/communications/campaigns/unsubscribe/token.value"
