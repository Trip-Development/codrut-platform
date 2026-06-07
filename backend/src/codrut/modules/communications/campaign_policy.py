from urllib.parse import urlparse

from codrut.core.errors import DomainError
from codrut.modules.communications.models import CampaignRecipient, CampaignRecipientStatus


def require_campaign_send_allowed(
    recipient: CampaignRecipient,
    *,
    unsubscribe_url: str,
) -> None:
    if recipient.status != CampaignRecipientStatus.active:
        raise DomainError(
            "Campaign recipient is suppressed or unsubscribed.",
            code="campaign_recipient_suppressed",
        )
    if not _is_https_url(unsubscribe_url):
        raise DomainError(
            "Campaign email requires a secure unsubscribe link.",
            code="campaign_unsubscribe_required",
        )


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)
