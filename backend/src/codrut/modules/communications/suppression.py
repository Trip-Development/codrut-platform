import hashlib
import hmac
from uuid import UUID


def normalize_suppression_email(email: str) -> str:
    return email.strip().casefold()


def email_suppression_fingerprint(
    *,
    owner_id: UUID,
    email: str,
    secret: str,
) -> str:
    normalized_email = normalize_suppression_email(email)
    message = f"codrut-email-suppression:v1:{owner_id}:{normalized_email}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def provider_message_fingerprint(*, message_id: str, secret: str) -> str:
    normalized_message_id = message_id.strip().removeprefix("<").removesuffix(">")
    message = f"codrut-provider-message:v1:{normalized_message_id}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def provider_event_fingerprint(*, provider_event_id: str, secret: str) -> str:
    message = f"codrut-provider-event:v1:{provider_event_id.strip()}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
