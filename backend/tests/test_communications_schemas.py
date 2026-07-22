import pytest
from pydantic import ValidationError

from codrut.modules.communications.schemas import (
    CampaignCreateRequest,
    CampaignRecipientBulkCreateRequest,
    CampaignRecipientCreateRequest,
)


def test_campaign_recipient_bulk_request_normalizes_romanian_import_rows() -> None:
    payload = CampaignRecipientBulkCreateRequest.model_validate(
        {
            "recipients": [
                {
                    "De trimis": "Da",
                    "Primul prenume": "Andrei",
                    "Al doilea prenume": "Cristian",
                    "Nume de familie": "Popescu",
                    "Tip Client": "Nu e client",
                    "Organizație": "(Genpact) Vodaphone",
                    "Email": "andrei.popescu@example.com",
                    "Telefon": "0771 382 348",
                    "Funcția": "-",
                },
                {
                    "De trimis": "Nu",
                    "Primul prenume": "Maria",
                    "Nume de familie": "Ionescu",
                    "Tip Client": "Client",
                    "Organizație": "Example",
                    "Email": "maria@example.com",
                },
                {
                    "De trimis": "Da",
                    "Primul prenume": "Invalid",
                    "Nume de familie": "Email",
                    "Tip Client": "Nu e client",
                    "Organizație": "Example",
                    "Email": "not an email",
                },
                {
                    "De trimis": "Nu",
                    "Primul prenume": "Fără",
                    "Nume de familie": "Email",
                    "Tip Client": "Nu e client",
                    "Organizație": "Missing Email",
                },
            ]
        }
    )

    assert len(payload.recipients) == 4
    recipient = payload.recipients[0]
    assert recipient.email == "andrei.popescu@example.com"
    assert recipient.contact_name == "Andrei Cristian Popescu"
    assert recipient.organization_name == "(Genpact) Vodaphone"
    assert recipient.segment == "potential_customer"
    assert recipient.status == "active"
    assert recipient.source == "excel_import"
    suppressed = payload.recipients[1]
    assert suppressed.email == "maria@example.com"
    assert suppressed.contact_name == "Maria Ionescu"
    assert suppressed.segment == "past_customer"
    assert suppressed.status == "suppressed"
    invalid = payload.recipients[2]
    assert invalid.email is None
    assert invalid.status == "suppressed"
    missing = payload.recipients[3]
    assert missing.email is None
    assert missing.contact_name == "Fără Email"
    assert missing.status == "suppressed"


def test_campaign_recipient_bulk_request_accepts_name_surname_aliases() -> None:
    payload = CampaignRecipientBulkCreateRequest.model_validate(
        {
            "recipients": [
                {
                    "Trimite": "Da",
                    "Prenume": "Cristina",
                    "Nume": "Luncan",
                    "Tip Client": "Nu e client",
                    "Organizatie": "Viarom",
                    "Email": "cristina.luncan@example.com",
                },
                {
                    "Send": "yes",
                    "First name": "Diana",
                    "Middle name": "Maria",
                    "Surname": "Ene",
                    "Segment": "past customer",
                    "Company": "Clinica Meridian",
                    "Email": "diana.ene@example.com",
                },
                {
                    "De trimis": "Nu",
                    "Name": "Full Name Fallback",
                    "Surname": "Fallback",
                    "Company": "Fallback Co",
                    "Email": "fallback@example.com",
                },
            ]
        }
    )

    assert payload.recipients[0].contact_name == "Cristina Luncan"
    assert payload.recipients[0].organization_name == "Viarom"
    assert payload.recipients[0].status == "active"
    assert payload.recipients[1].contact_name == "Diana Maria Ene"
    assert payload.recipients[1].organization_name == "Clinica Meridian"
    assert payload.recipients[1].segment == "past_customer"
    assert payload.recipients[1].status == "active"
    assert payload.recipients[2].contact_name == "Full Name Fallback"
    assert payload.recipients[2].status == "suppressed"


def test_campaign_recipient_create_rejects_invalid_segment() -> None:
    with pytest.raises(ValidationError):
        CampaignRecipientCreateRequest.model_validate(
            {
                "email": "ana@example.com",
                "contact_name": "Ana",
                "organization_name": "Example",
                "segment": "not_a_segment",
            }
        )


def test_campaign_create_rejects_invalid_segment() -> None:
    with pytest.raises(ValidationError):
        CampaignCreateRequest.model_validate(
            {
                "name": "Campanie",
                "segment": "not_a_segment",
                "subject": "Subiect",
                "html_body": "<p>Test</p>",
                "text_body": "Test",
            }
        )


def test_campaign_create_accepts_no_preselected_segment() -> None:
    payload = CampaignCreateRequest.model_validate(
        {
            "name": "Campanie fără grup",
            "segment": None,
            "subject": "Subiect",
            "html_body": "<p>Test</p>",
            "text_body": "Test",
        }
    )

    assert payload.segment is None
