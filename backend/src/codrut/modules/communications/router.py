from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.contracts.emails import EmailAddress, EmailMessage
from codrut.core.config import Settings, get_settings
from codrut.core.errors import DomainError
from codrut.modules.communications.email_provider import build_email_provider
from codrut.modules.communications.schemas import (
    CampaignCreateRequest,
    CampaignRecipientBulkCreateRequest,
    EmailOpsSummaryResponse,
    EmailTemplateCreateRequest,
    EmailTemplateResponse,
    EmailTemplateUpdateRequest,
    EmailTestSendRequest,
    EmailTestSendResponse,
)
from codrut.modules.communications.service import CommunicationsService
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal

router = APIRouter()


def _require_trainer(principal: SessionPrincipal) -> None:
    if principal.role != UserRole.trainer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trainer access is required.",
        )


@router.post("/test-email", response_model=EmailTestSendResponse)
async def send_test_email(
    payload: EmailTestSendRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailTestSendResponse:
    if settings.is_production:
        raise DomainError(
            "Test email endpoint is disabled in production.",
            code="test_email_disabled",
        )

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


@router.get("/templates", response_model=list[EmailTemplateResponse])
async def list_email_templates(
    session: Annotated[AsyncSession, Depends(db_session)],
    include_retired: bool = False,
) -> list[EmailTemplateResponse]:
    templates = await CommunicationsService(session).list_templates(
        active_only=not include_retired,
    )
    await session.commit()
    return templates


@router.get("/templates/{key}", response_model=EmailTemplateResponse)
async def get_email_template(
    key: str,
    session: Annotated[AsyncSession, Depends(db_session)],
    version: int | None = None,
) -> EmailTemplateResponse:
    template = await CommunicationsService(session).get_template(key, version=version)
    await session.commit()
    return template


@router.post("/templates", response_model=EmailTemplateResponse)
async def create_email_template(
    payload: EmailTemplateCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> EmailTemplateResponse:
    _require_trainer(principal)
    template = await CommunicationsService(session).create_template(
        payload, owner_id=principal.user_id
    )
    await session.commit()
    return template


@router.patch("/templates/{key}", response_model=EmailTemplateResponse)
async def update_email_template(
    key: str,
    payload: EmailTemplateUpdateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    version: int | None = None,
) -> EmailTemplateResponse:
    _require_trainer(principal)
    template = await CommunicationsService(session).update_template(
        key, payload, version=version
    )
    await session.commit()
    return template


@router.post("/templates/{key}/versions/{version}/activate", response_model=EmailTemplateResponse)
async def activate_email_template(
    key: str,
    version: int,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> EmailTemplateResponse:
    _require_trainer(principal)
    template = await CommunicationsService(session).activate_template(key, version)
    await session.commit()
    return template


@router.delete("/templates/{key}", response_model=EmailTemplateResponse)
async def retire_email_template(
    key: str,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    version: int | None = None,
) -> EmailTemplateResponse:
    _require_trainer(principal)
    template = await CommunicationsService(session).retire_template(key, version=version)
    await session.commit()
    return template


@router.get("/ops-summary", response_model=EmailOpsSummaryResponse)
async def get_email_ops_summary(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> EmailOpsSummaryResponse:
    _require_trainer(principal)
    summary = await CommunicationsService(session).get_email_ops_summary()
    await session.commit()
    return summary


@router.post("/campaigns/recipients/bulk")
async def bulk_create_campaign_recipients(
    payload: CampaignRecipientBulkCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> dict:
    _require_trainer(principal)
    recipients = await CommunicationsService(session).bulk_create_campaign_recipients(payload)
    await session.commit()
    return {"status": "success", "count": len(recipients)}


@router.post("/campaigns")
async def create_campaign(
    payload: CampaignCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> dict:
    _require_trainer(principal)
    campaign = await CommunicationsService(session).create_campaign(payload)
    await session.commit()
    return {"status": "success", "campaign_id": str(campaign.id)}


@router.get("/campaigns")
async def list_campaigns(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[dict]:
    _require_trainer(principal)
    campaigns = await CommunicationsService(session).list_campaigns()
    await session.commit()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "segment": c.segment.value,
            "status": c.status.value,
            "subject": c.subject,
            "html_body": c.html_body,
            "text_body": c.text_body,
            "video_url": c.video_url,
            "thumbnail_url": c.thumbnail_url,
            "landing_page_url": c.landing_page_url,
        }
        for c in campaigns
    ]
