from dataclasses import dataclass


@dataclass(frozen=True)
class EmailAddress:
    value: str


@dataclass(frozen=True)
class EmailMessage:
    to: EmailAddress
    subject: str
    html_body: str
    text_body: str
