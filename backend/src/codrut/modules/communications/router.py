from fastapi import APIRouter, Depends

from codrut.contracts.emails import EmailAddress, EmailMessage
from codrut.core.config import Settings, get_settings
from codrut.core.errors import DomainError
from codrut.modules.communications.email_provider import build_email_provider
from codrut.modules.communications.schemas import EmailTestSendRequest, EmailTestSendResponse

router = APIRouter()


@router.post("/test-email", response_model=EmailTestSendResponse)
async def send_test_email(
    payload: EmailTestSendRequest,
    settings: Settings = Depends(get_settings),
) -> EmailTestSendResponse:
    if settings.is_production:
        raise DomainError("Test email endpoint is disabled in production.", code="test_email_disabled")

    provider = build_email_provider(settings)
    result = await provider.send(
        EmailMessage(
            to=EmailAddress(payload.to),
            subject=payload.subject,
            html_body=payload.html_body,
            text_body=payload.text_body,
        )
    )
    return EmailTestSendResponse(
        provider=result.provider,
        status=result.status,
        message_id=result.message_id,
        recipient=result.recipient.value,
    )
