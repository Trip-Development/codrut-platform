from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from codrut.core.database import Base
from codrut.modules.communications.models import (
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
    EmailEventType,
    EmailSendStatus,
)
from codrut.modules.communications.schemas import CampaignCreateRequest
from codrut.modules.companies import models as company_models  # noqa: F401
from codrut.modules.identity import models as identity_models  # noqa: F401


def test_email_delivery_tables_are_registered() -> None:
    assert {"email_sends", "email_events", "campaign_recipients", "campaigns"}.issubset(
        Base.metadata.tables
    )
    configure_mappers()


def test_email_delivery_enums_support_current_workflow() -> None:
    assert {item.value for item in EmailSendStatus} == {
        "queued",
        "accepted",
        "failed",
        "delivered",
        "bounced",
    }
    assert {item.value for item in EmailEventType} == {
        "accepted",
        "failed",
        "delivered",
        "bounced",
        "opened",
        "clicked",
    }


def test_email_sends_can_link_to_assignment_without_blocking_delete() -> None:
    constraints = {
        constraint.name: constraint
        for constraint in Base.metadata.tables["email_sends"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }

    constraint = constraints["fk_email_sends_assignment_id_questionnaire_assignments"]
    assert constraint.ondelete == "SET NULL"


def test_campaign_recipient_model_separates_promotional_contacts() -> None:
    assert {item.value for item in CampaignRecipientSegment} == {
        "past_customer",
        "potential_customer",
    }
    assert {item.value for item in CampaignRecipientStatus} == {
        "active",
        "suppressed",
        "unsubscribed",
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in Base.metadata.tables["campaign_recipients"].constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("email",) in unique_columns
    assert Base.metadata.tables["campaign_recipients"].columns["email"].nullable
    assert "owner_id" in Base.metadata.tables["campaign_recipients"].columns


def test_campaign_model_supports_template_and_video_link_design() -> None:
    assert {item.value for item in CampaignStatus} == {
        "draft",
        "ready",
        "paused",
        "completed",
    }
    columns = Base.metadata.tables["campaigns"].columns
    assert {
        "subject",
        "html_body",
        "text_body",
        "video_url",
        "thumbnail_url",
        "landing_page_url",
    }.issubset(columns.keys())


def test_campaign_create_requires_http_video_asset_urls() -> None:
    request = CampaignCreateRequest(
        name="Video campaign",
        segment="potential_customer",
        subject="Subject",
        html_body="<p>Body</p>",
        text_body="Body",
        video_url="https://video.codrut.ro/watch/demo",
        thumbnail_url="https://cdn.codrut.ro/thumb.jpg",
        landing_page_url="https://codrut.andreivacaru.ro/watch/demo",
    )

    assert request.thumbnail_url == "https://cdn.codrut.ro/thumb.jpg"


def test_campaign_create_allows_vimeo_with_thumbnail_without_landing_page() -> None:
    request = CampaignCreateRequest(
        name="Video campaign",
        segment="potential_customer",
        subject="Subject",
        html_body="<p>Body</p>",
        text_body="Body",
        video_url="https://vimeo.com/123456789",
        thumbnail_url="https://cdn.codrut.ro/thumb.jpg",
    )

    assert request.video_url == "https://vimeo.com/123456789"
    assert request.landing_page_url is None


def test_campaign_create_rejects_missing_thumbnail_for_video_campaign() -> None:
    try:
        CampaignCreateRequest(
            name="Video campaign",
            segment="potential_customer",
            subject="Subject",
            html_body="<p>Body</p>",
            text_body="Body",
            video_url="https://video.codrut.ro/watch/demo",
        )
    except ValueError as exc:
        assert "Video campaigns require" in str(exc)
    else:
        raise AssertionError("Video campaigns without thumbnail should be rejected.")


def test_campaign_create_rejects_non_http_asset_urls() -> None:
    try:
        CampaignCreateRequest(
            name="Video campaign",
            segment="potential_customer",
            subject="Subject",
            html_body="<p>Body</p>",
            text_body="Body",
            video_url="javascript:alert(1)",
            thumbnail_url="https://cdn.codrut.ro/thumb.jpg",
            landing_page_url="https://codrut.andreivacaru.ro/watch/demo",
        )
    except ValueError as exc:
        assert "absolute HTTP(S) URLs" in str(exc)
    else:
        raise AssertionError("Non-HTTP campaign asset URLs should be rejected.")
