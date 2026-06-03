import pytest

from codrut.contracts.emails import EmailAddress, EmailDeliveryStatus, EmailMessage
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.communications.email_provider import LocalEmailProvider, build_email_provider


async def test_test_email_provider_accepts_and_records_message() -> None:
    provider = LocalEmailProvider()
    message = EmailMessage(
        to=EmailAddress("participant@example.com"),
        subject="Invitatie assessment",
        html_body="<p>Intra in Codrut</p>",
        text_body="Intra in Codrut",
    )

    result = await provider.send(message)

    assert result.status == EmailDeliveryStatus.accepted
    assert result.message_id.startswith("test:")
    assert result.recipient == message.to
    assert provider.sent_messages == [message]


def test_build_email_provider_defaults_to_test_provider() -> None:
    provider = build_email_provider(Settings())

    assert isinstance(provider, LocalEmailProvider)


def test_build_email_provider_rejects_unknown_provider() -> None:
    settings = Settings(email_provider="unknown")

    with pytest.raises(DomainError, match="Unsupported email provider"):
        build_email_provider(settings)


def test_build_email_provider_blocks_local_provider_in_production() -> None:
    settings = Settings(env="production", email_provider="test")

    with pytest.raises(DomainError, match="Production email requires"):
        build_email_provider(settings)
