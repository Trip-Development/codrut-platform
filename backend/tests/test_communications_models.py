from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from codrut.core.database import Base
from codrut.modules.communications.models import (
    CampaignRecipientMembership,
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
    assert {
        "email_sends",
        "email_events",
        "campaign_recipients",
        "campaigns",
        "campaign_recipient_memberships",
    }.issubset(Base.metadata.tables)
    configure_mappers()


def test_email_delivery_enums_support_current_workflow() -> None:
    assert {item.value for item in EmailSendStatus} == {
        "queued",
        "dispatching",
        "accepted",
        "failed",
        "delivered",
        "bounced",
        "cancelled",
        "indeterminate",
    }
    assert {item.value for item in EmailEventType} == {
        "queued",
        "claimed",
        "retry_scheduled",
        "cancelled",
        "accepted",
        "failed",
        "delivered",
        "bounced",
        "opened",
        "clicked",
        "unsubscribed",
        "complained",
        "indeterminate",
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
    unique_indexes = {
        index.name: index
        for index in Base.metadata.tables["campaign_recipients"].indexes
        if index.unique
    }
    email_index = unique_indexes["uq_campaign_recipients_owner_normalized_email"]

    assert ("email",) not in unique_columns
    assert [str(expression) for expression in email_index.expressions] == [
        "campaign_recipients.owner_id",
        "lower(campaign_recipients.email)",
    ]
    assert Base.metadata.tables["campaign_recipients"].columns["email"].nullable
    owner_column = Base.metadata.tables["campaign_recipients"].columns["owner_id"]
    assert not owner_column.nullable
    assert next(iter(owner_column.foreign_keys)).ondelete == "CASCADE"


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
        "recipient_memberships_initialized",
    }.issubset(columns.keys())


def test_campaign_recipient_membership_model_is_campaign_scoped() -> None:
    table = Base.metadata.tables[CampaignRecipientMembership.__tablename__]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    foreign_keys = {
        constraint.name: constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }

    assert ("campaign_id", "recipient_id") in unique_columns
    assert (
        foreign_keys["fk_campaign_recipient_memberships_campaign_id_campaigns"].ondelete
        == "CASCADE"
    )
    assert (
        foreign_keys["fk_campaign_recipient_memberships_recipient_id_campaign_recipients"].ondelete
        == "CASCADE"
    )


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


def test_campaign_create_allows_incomplete_video_draft() -> None:
    request = CampaignCreateRequest(
        name="Video campaign",
        segment="potential_customer",
        subject="Subject",
        html_body="<p>Body</p>",
        text_body="Body",
        video_url="https://video.codrut.ro/watch/demo",
    )

    assert request.video_url == "https://video.codrut.ro/watch/demo"
    assert request.thumbnail_url is None


def test_campaign_create_allows_image_without_video() -> None:
    request = CampaignCreateRequest(
        name="Image campaign",
        segment="potential_customer",
        subject="Subject",
        html_body="<p>Body</p>",
        text_body="Body",
        thumbnail_url="https://cdn.codrut.ro/image.jpg",
    )

    assert request.video_url is None
    assert request.thumbnail_url == "https://cdn.codrut.ro/image.jpg"


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
