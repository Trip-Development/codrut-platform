from codrut.modules.communications.schemas import CampaignRecipientBulkCreateRequest


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
                    "Email": "andreicristian.popescu@genpact.com",
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
            ]
        }
    )

    assert len(payload.recipients) == 2
    recipient = payload.recipients[0]
    assert recipient.email == "andreicristian.popescu@genpact.com"
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
