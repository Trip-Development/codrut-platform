import json

import httpx
import pytest

from codrut.contracts.emails import (
    EmailAddress,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.communications.email_provider import (
    BrevoEmailProvider,
    LocalEmailProvider,
    SmtpEmailProvider,
    build_email_provider,
)


async def test_test_email_provider_accepts_and_records_message() -> None:
    provider = LocalEmailProvider()
    message = EmailMessage(
        to=EmailAddress("participant@example.com"),
        subject="Invitatie assessment",
        html_body="<p>Intra in Cody</p>",
        text_body="Intra in Cody",
    )

    result = await provider.send(message)

    assert result.status == EmailDeliveryStatus.accepted
    assert result.message_id.startswith("test:")
    assert result.recipient == message.to
    assert provider.sent_messages == [message]


def test_build_email_provider_defaults_to_test_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODRUT_EMAIL_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    provider = build_email_provider(settings)

    assert isinstance(provider, LocalEmailProvider)


def test_build_email_provider_rejects_unknown_provider() -> None:
    settings = Settings(email_provider="unknown")

    with pytest.raises(DomainError, match="Unsupported email provider"):
        build_email_provider(settings)


def test_build_email_provider_blocks_local_provider_in_production() -> None:
    with pytest.raises(ValueError, match="Production email provider must be Brevo"):
        Settings(env="production", email_provider="test")


def test_build_email_provider_supports_brevo_provider() -> None:
    settings = Settings(email_provider="brevo", email_brevo_api_key="brevo-secret")

    provider = build_email_provider(settings)

    assert isinstance(provider, BrevoEmailProvider)


def test_build_email_provider_supports_mailpit_provider() -> None:
    settings = Settings(email_provider="mailpit")

    provider = build_email_provider(settings)

    assert isinstance(provider, SmtpEmailProvider)


def test_build_email_provider_requires_brevo_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODRUT_EMAIL_BREVO_API_KEY", raising=False)
    settings = Settings(_env_file=None, email_provider="brevo")

    with pytest.raises(DomainError, match="Brevo API key is required"):
        build_email_provider(settings)


async def test_brevo_email_provider_sends_transactional_payload() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"messageId": "brevo-message-id"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrevoEmailProvider(
            Settings(
                email_brevo_api_key="brevo-secret",
                email_from_address="hello@codrut.local",
                email_from_name="Cody",
            ),
            client=client,
        )
        message = EmailMessage(
            to=EmailAddress("participant@example.com"),
            subject="Invitatie assessment",
            html_body="<p>Intra in Cody</p>",
            text_body="Intra in Cody",
            provider_idempotency_key="delivery-request-id",
        )

        result = await provider.send(message)

    assert result.provider == EmailProviderKey.brevo
    assert result.status == EmailDeliveryStatus.accepted
    assert result.message_id == "brevo-message-id"
    assert requests[0].headers["api-key"] == "brevo-secret"
    assert requests[0].headers["content-type"] == "application/json"
    assert requests[0].url == "https://api.brevo.com/v3/smtp/email"
    assert requests[0].read()
    assert b'"sender":{"email":"hello@codrut.local","name":"Cody"}' in requests[0].content
    assert b'"to":[{"email":"participant@example.com"}]' in requests[0].content
    assert json.loads(requests[0].content)["headers"] == {
        "idempotencyKey": "delivery-request-id"
    }


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [(400, False), (401, False), (408, True), (500, True)],
)
async def test_brevo_email_provider_classifies_http_failures(
    status_code: int,
    retryable: bool,
) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            status_code,
            json={"code": "provider_error", "message": "Provider rejected request"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrevoEmailProvider(
            Settings(email_brevo_api_key="brevo-secret"),
            client=client,
        )
        result = await provider.send(
            EmailMessage(
                to=EmailAddress("participant@example.com"),
                subject="Invitatie",
                html_body="<p>Mesaj</p>",
                text_body="Mesaj",
            )
        )

    assert result.status == EmailDeliveryStatus.failed
    assert result.retryable is retryable
    assert result.delivery_uncertain is False


async def test_brevo_email_provider_honors_retry_after_for_rate_limits() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            429,
            headers={"Retry-After": "120"},
            json={"code": "too_many_requests", "message": "Slow down"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrevoEmailProvider(
            Settings(email_brevo_api_key="brevo-secret"),
            client=client,
        )
        result = await provider.send(
            EmailMessage(
                to=EmailAddress("participant@example.com"),
                subject="Invitatie",
                html_body="<p>Mesaj</p>",
                text_body="Mesaj",
            )
        )

    assert result.retryable is True
    assert result.retry_after_seconds == 120


async def test_brevo_email_provider_marks_network_outcome_indeterminate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("connection closed after request", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BrevoEmailProvider(
            Settings(email_brevo_api_key="brevo-secret"),
            client=client,
        )
        result = await provider.send(
            EmailMessage(
                to=EmailAddress("participant@example.com"),
                subject="Invitatie",
                html_body="<p>Mesaj</p>",
                text_body="Mesaj",
            )
        )

    assert result.status == EmailDeliveryStatus.failed
    assert result.retryable is False
    assert result.delivery_uncertain is True


async def test_smtp_email_provider_sends_multipart_message(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_messages = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def send_message(self, message: object) -> None:
            sent_messages.append((self.host, self.port, self.timeout, message))

    monkeypatch.setattr("codrut.modules.communications.email_provider.smtplib.SMTP", FakeSmtp)
    provider = SmtpEmailProvider(
        Settings(
            email_provider="mailpit",
            email_smtp_host="mailpit",
            email_smtp_port=1025,
            email_from_address="hello@codrut.local",
            email_from_name="Cody",
        )
    )

    result = await provider.send(
        EmailMessage(
            to=EmailAddress("participant@example.com"),
            subject="Invitatie assessment",
            html_body="<p>Intra in Cody</p>",
            text_body="Intra in Cody",
        )
    )

    assert result.provider == EmailProviderKey.smtp
    assert result.status == EmailDeliveryStatus.accepted
    assert sent_messages
    host, port, _timeout, message = sent_messages[0]
    assert host == "mailpit"
    assert port == 1025
    assert message["To"] == "participant@example.com"
    assert message["Subject"] == "Invitatie assessment"
