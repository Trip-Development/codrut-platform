from typing import Protocol

from codrut.contracts.emails import (
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
    make_test_message_id,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError


class EmailProvider(Protocol):
    async def send(self, message: EmailMessage) -> EmailSendResult:
        """Send a prepared email message through the configured provider."""


class LocalEmailProvider:
    key = EmailProviderKey.test

    def __init__(self) -> None:
        self.sent_messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> EmailSendResult:
        self.sent_messages.append(message)
        return EmailSendResult(
            provider=self.key,
            status=EmailDeliveryStatus.accepted,
            message_id=make_test_message_id(),
            recipient=message.to,
        )


def build_email_provider(settings: Settings) -> EmailProvider:
    try:
        provider = EmailProviderKey(settings.email_provider)
    except ValueError as exc:
        raise DomainError("Unsupported email provider.", code="email_provider_unsupported") from exc
    if provider == EmailProviderKey.test:
        if settings.is_production:
            raise DomainError(
                "Production email requires a configured production provider.",
                code="email_provider_not_configured",
            )
        return LocalEmailProvider()
    raise DomainError("Unsupported email provider.", code="email_provider_unsupported")
