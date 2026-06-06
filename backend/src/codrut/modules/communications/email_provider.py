import asyncio
import smtplib
from email.message import EmailMessage as SmtpMessage
from typing import Protocol

import httpx

from codrut.contracts.emails import (
    EmailAddress,
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


class SmtpEmailProvider:
    key = EmailProviderKey.smtp

    def __init__(self, settings: Settings) -> None:
        self.host = settings.email_smtp_host
        self.port = settings.email_smtp_port
        self.username = settings.email_smtp_username
        self.password = (
            settings.email_smtp_password.get_secret_value()
            if settings.email_smtp_password is not None
            else None
        )
        self.starttls = settings.email_smtp_starttls
        self.from_address = EmailAddress(settings.email_from_address)
        self.from_name = settings.email_from_name

    async def send(self, message: EmailMessage) -> EmailSendResult:
        return await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> EmailSendResult:
        smtp_message = SmtpMessage()
        sender = (message.from_address or self.from_address).value
        smtp_message["From"] = f"{self.from_name} <{sender}>"
        smtp_message["To"] = message.to.value
        smtp_message["Subject"] = message.subject
        if message.reply_to is not None:
            smtp_message["Reply-To"] = message.reply_to.value
        smtp_message.set_content(message.text_body)
        smtp_message.add_alternative(message.html_body, subtype="html")

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10.0) as server:
                if self.starttls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(smtp_message)
        except (OSError, smtplib.SMTPException) as exc:
            return EmailSendResult(
                provider=self.key,
                status=EmailDeliveryStatus.failed,
                message_id="smtp:failed",
                recipient=message.to,
                error_details=str(exc),
            )

        return EmailSendResult(
            provider=self.key,
            status=EmailDeliveryStatus.accepted,
            message_id=make_test_message_id().replace("test:", "smtp:", 1),
            recipient=message.to,
        )


class BrevoEmailProvider:
    key = EmailProviderKey.brevo
    endpoint = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if settings.email_brevo_api_key is None:
            raise DomainError("Brevo API key is required.", code="email_provider_not_configured")
        self.api_key = settings.email_brevo_api_key.get_secret_value()
        self.from_address = EmailAddress(settings.email_from_address)
        self.from_name = settings.email_from_name
        self.client = client

    async def send(self, message: EmailMessage) -> EmailSendResult:
        payload = {
            "sender": {
                "email": (message.from_address or self.from_address).value,
                "name": self.from_name,
            },
            "to": [{"email": message.to.value}],
            "subject": message.subject,
            "htmlContent": message.html_body,
            "textContent": message.text_body,
        }
        if message.reply_to is not None:
            payload["replyTo"] = {"email": message.reply_to.value}

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json",
        }
        try:
            if self.client is not None:
                response = await self.client.post(self.endpoint, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(self.endpoint, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            return EmailSendResult(
                provider=self.key,
                status=EmailDeliveryStatus.failed,
                message_id="brevo:failed:network",
                recipient=message.to,
                error_details=f"Brevo HTTP error: {exc}",
            )

        if response.is_success:
            body = response.json()
            return EmailSendResult(
                provider=self.key,
                status=EmailDeliveryStatus.accepted,
                message_id=str(body.get("messageId") or body.get("message_id") or "brevo:accepted"),
                recipient=message.to,
            )

        error_msg = f"Brevo API error: status {response.status_code}"
        try:
            body = response.json()
            if "message" in body:
                error_msg = f"{error_msg} - {body['message']}"
        except Exception:  # noqa: S110
            pass

        return EmailSendResult(
            provider=self.key,
            status=EmailDeliveryStatus.failed,
            message_id=f"brevo:failed:{response.status_code}",
            recipient=message.to,
            error_details=error_msg,
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
    if provider in {EmailProviderKey.smtp, EmailProviderKey.mailpit}:
        if settings.is_production and provider == EmailProviderKey.mailpit:
            raise DomainError(
                "Mailpit cannot be used in production.",
                code="email_provider_not_configured",
            )
        return SmtpEmailProvider(settings)
    if provider == EmailProviderKey.brevo:
        return BrevoEmailProvider(settings)
    raise DomainError("Unsupported email provider.", code="email_provider_unsupported")
