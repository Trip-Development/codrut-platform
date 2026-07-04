from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.contracts.emails import EmailAddress, EmailMessage
from codrut.core.config import Settings, get_settings
from codrut.core.errors import DomainError
from codrut.modules.communications.assets import store_campaign_asset
from codrut.modules.communications.email_provider import build_email_provider
from codrut.modules.communications.schemas import (
    CampaignAssetUploadResponse,
    CampaignCreateRequest,
    CampaignRecipientBulkCreateRequest,
    CampaignRecipientEventCreateRequest,
    CampaignRecipientEventResponse,
    CampaignRecipientUpdateRequest,
    CampaignSendRequest,
    CampaignSendResponse,
    CampaignUpdateRequest,
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
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailTestSendResponse:
    _require_trainer(principal)
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


@router.post("/campaign-assets", response_model=CampaignAssetUploadResponse)
async def upload_campaign_asset(
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    settings: Annotated[Settings, Depends(get_settings)],
    content_type: Annotated[str | None, Header(alias="content-type")] = None,
    file_name: Annotated[str | None, Header(alias="x-file-name")] = None,
) -> CampaignAssetUploadResponse:
    _require_trainer(principal)
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            too_large = int(declared_length) > settings.campaign_asset_max_bytes
        except ValueError as exc:
            raise DomainError(
                "Dimensiunea fișierului nu a putut fi citită.",
                code="campaign_asset_length_invalid",
            ) from exc
        if too_large:
            raise DomainError(
                "Thumbnailul depășește limita permisă.",
                code="campaign_asset_too_large",
            )
    asset = store_campaign_asset(
        settings=settings,
        content=await request.body(),
        content_type=content_type,
        original_file_name=file_name,
    )
    return CampaignAssetUploadResponse(
        url=asset.url,
        file_name=asset.file_name,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
    )


@router.get("/templates", response_model=list[EmailTemplateResponse])
async def list_email_templates(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    include_retired: bool = False,
) -> list[EmailTemplateResponse]:
    _require_trainer(principal)
    templates = await CommunicationsService(session).list_templates(
        active_only=not include_retired,
    )
    await session.commit()
    return templates


@router.get("/templates/{key}", response_model=EmailTemplateResponse)
async def get_email_template(
    key: str,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    version: int | None = None,
) -> EmailTemplateResponse:
    _require_trainer(principal)
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


@router.patch("/campaigns/recipients/{recipient_id}")
async def update_campaign_recipient(
    recipient_id: UUID,
    payload: CampaignRecipientUpdateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> dict:
    _require_trainer(principal)
    recipient = await CommunicationsService(session).update_campaign_recipient(
        recipient_id,
        payload,
    )
    await session.commit()
    return {
        "id": str(recipient.id),
        "email": recipient.email or "",
        "contact_name": recipient.contact_name,
        "organization_name": recipient.organization_name,
        "segment": recipient.segment.value,
        "status": recipient.status.value,
        "source": recipient.source,
    }


@router.delete("/campaigns/recipients/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign_recipient(
    recipient_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> Response:
    _require_trainer(principal)
    await CommunicationsService(session).delete_campaign_recipient(recipient_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/campaigns/recipients/{recipient_id}/events",
    response_model=CampaignRecipientEventResponse,
)
async def record_campaign_recipient_event(
    recipient_id: UUID,
    payload: CampaignRecipientEventCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> CampaignRecipientEventResponse:
    _require_trainer(principal)
    event = await CommunicationsService(session).record_campaign_recipient_event(
        recipient_id,
        payload,
    )
    await session.commit()
    return event


@router.get("/campaigns/track/calendly/{token}")
async def track_campaign_calendly_click(
    token: str,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> RedirectResponse:
    target_url = await CommunicationsService(session).record_calendly_tracking_click(
        token,
        settings,
    )
    await session.commit()
    return RedirectResponse(target_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/campaigns/unsubscribe/{token}")
async def unsubscribe_campaign_recipient(
    token: str,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> dict:
    recipient = await CommunicationsService(session).unsubscribe_campaign_recipient(
        token,
        settings,
    )
    await session.commit()
    return {"status": "unsubscribed", "email": recipient.email}


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


@router.post("/campaigns/{campaign_id}/send", response_model=CampaignSendResponse)
async def send_campaign(
    campaign_id: UUID,
    payload: CampaignSendRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> CampaignSendResponse:
    _require_trainer(principal)
    result = await CommunicationsService(session).send_campaign(
        campaign_id,
        payload,
        provider=build_email_provider(settings),
        settings=settings,
    )
    await session.commit()
    return result


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> dict:
    _require_trainer(principal)
    campaign = await CommunicationsService(session).update_campaign(campaign_id, payload)
    await session.commit()
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "segment": campaign.segment.value,
        "status": campaign.status.value,
        "subject": campaign.subject,
        "html_body": campaign.html_body,
        "text_body": campaign.text_body,
        "video_url": campaign.video_url,
        "thumbnail_url": campaign.thumbnail_url,
        "landing_page_url": campaign.landing_page_url,
    }


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> Response:
    _require_trainer(principal)
    await CommunicationsService(session).delete_campaign(campaign_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
