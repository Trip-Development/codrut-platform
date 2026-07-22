import asyncio
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from codrut.contracts.emails import EmailAddress, EmailDeliveryStatus, EmailMessage
from codrut.core.config import get_settings
from codrut.modules.communications.email_provider import build_email_provider


@dataclass(frozen=True)
class MailpitMessageMatch:
    id: str
    subject: str
    recipient: str


def _mailpit_api_url() -> str:
    return os.getenv("CODRUT_MAILPIT_API_URL", "http://mailpit:8025").rstrip("/")


def _recipient() -> str:
    return os.getenv("CODRUT_MAILPIT_SMOKE_TO", "codrut-mailpit-smoke@example.com").strip()


def _message_matches(message: dict[str, Any], *, subject: str, recipient: str) -> bool:
    recipients = message.get("To") or []
    return message.get("Subject") == subject and any(
        str(item.get("Address", "")).lower() == recipient.lower() for item in recipients
    )


async def _find_message(
    client: httpx.AsyncClient,
    *,
    subject: str,
    recipient: str,
) -> MailpitMessageMatch | None:
    response = await client.get("/api/v1/messages")
    response.raise_for_status()
    payload = response.json()

    for message in payload.get("messages", []):
        if _message_matches(message, subject=subject, recipient=recipient):
            return MailpitMessageMatch(
                id=str(message["ID"]),
                subject=str(message["Subject"]),
                recipient=recipient,
            )
    return None


async def smoke_mailpit() -> None:
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("Refusing to run Mailpit smoke in production.")

    recipient = _recipient()
    marker = uuid.uuid4().hex[:12]
    subject = f"Cody Mailpit smoke {marker}"
    text_body = f"Mailpit smoke marker: {marker}"
    html_body = f"<p>Mailpit smoke marker: <strong>{marker}</strong></p>"

    provider = build_email_provider(settings)
    result = await provider.send(
        EmailMessage(
            to=EmailAddress(recipient),
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
    )
    if result.status != EmailDeliveryStatus.accepted:
        raise RuntimeError(f"Provider rejected smoke email: {result.error_details}")

    timeout_seconds = float(os.getenv("CODRUT_MAILPIT_SMOKE_TIMEOUT", "10"))
    deadline = time.monotonic() + timeout_seconds
    async with httpx.AsyncClient(base_url=_mailpit_api_url(), timeout=5.0) as client:
        match: MailpitMessageMatch | None = None
        while time.monotonic() < deadline:
            match = await _find_message(client, subject=subject, recipient=recipient)
            if match is not None:
                break
            await asyncio.sleep(0.25)

        if match is None:
            raise RuntimeError(
                f"Mailpit did not receive smoke email to {recipient} with subject {subject!r}."
            )

        detail_response = await client.get(f"/api/v1/message/{match.id}")
        detail_response.raise_for_status()
        detail = detail_response.json()
        if marker not in str(detail.get("Text", "")):
            raise RuntimeError("Mailpit message text body is missing the smoke marker.")
        if marker not in str(detail.get("HTML", "")):
            raise RuntimeError("Mailpit message HTML body is missing the smoke marker.")

    print(f"Mailpit smoke passed: {recipient} received {subject!r}")


def main() -> None:
    asyncio.run(smoke_mailpit())


if __name__ == "__main__":
    main()
