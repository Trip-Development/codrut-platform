import uuid

import pytest

from codrut.core.errors import DomainError
from codrut.modules.communications.campaign_policy import require_campaign_send_allowed
from codrut.modules.communications.models import (
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
)


def make_recipient(
    status: CampaignRecipientStatus = CampaignRecipientStatus.active,
) -> CampaignRecipient:
    return CampaignRecipient(
        id=uuid.uuid4(),
        email="lead@example.com",
        segment=CampaignRecipientSegment.potential_customer,
        status=status,
    )


def test_campaign_send_policy_allows_active_recipient_with_https_unsubscribe() -> None:
    require_campaign_send_allowed(
        make_recipient(),
        unsubscribe_url="https://app.codrut.ro/unsubscribe/token",
    )


def test_campaign_send_policy_rejects_suppressed_recipient() -> None:
    with pytest.raises(DomainError, match="suppressed or unsubscribed"):
        require_campaign_send_allowed(
            make_recipient(CampaignRecipientStatus.suppressed),
            unsubscribe_url="https://app.codrut.ro/unsubscribe/token",
        )


def test_campaign_send_policy_requires_secure_unsubscribe_url() -> None:
    with pytest.raises(DomainError, match="secure unsubscribe"):
        require_campaign_send_allowed(make_recipient(), unsubscribe_url="http://example.com")
