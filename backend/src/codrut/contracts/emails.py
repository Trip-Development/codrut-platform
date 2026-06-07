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


class EmailProviderKey(StrEnum):
    test = "test"
    smtp = "smtp"
    mailpit = "mailpit"
    brevo = "brevo"


class EmailDeliveryStatus(StrEnum):
    accepted = "accepted"
    failed = "failed"


@dataclass(frozen=True)
class EmailSendResult:
    provider: EmailProviderKey
    status: EmailDeliveryStatus
    message_id: str
    recipient: EmailAddress
    error_details: str | None = None


def make_test_message_id() -> str:
    return f"test:{uuid4()}"
