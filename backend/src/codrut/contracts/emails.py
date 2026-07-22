from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4


@dataclass(frozen=True)
class EmailAddress:
    value: str


@dataclass(frozen=True)
class EmailMessage:
    to: EmailAddress
    subject: str
    html_body: str
    text_body: str
    from_address: EmailAddress | None = None
    reply_to: EmailAddress | None = None
    provider_idempotency_key: str | None = None


class EmailProviderKey(StrEnum):
    test = "test"
    smtp = "smtp"
    mailpit = "mailpit"
    brevo = "brevo"


class EmailDeliveryStatus(StrEnum):
    queued = "queued"
    accepted = "accepted"
    failed = "failed"


@dataclass(frozen=True)
class EmailSendResult:
    provider: EmailProviderKey
    status: EmailDeliveryStatus
    message_id: str
    recipient: EmailAddress
    error_details: str | None = None
    retryable: bool = True
    retry_after_seconds: int | None = None
    delivery_uncertain: bool = False


def make_test_message_id() -> str:
    return f"test:{uuid4()}"
