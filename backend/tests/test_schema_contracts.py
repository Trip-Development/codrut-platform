from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from codrut.main import create_app
from codrut.modules.assignments.schemas import (
    AssignmentCreateRequest,
    AssignmentPlanSaveRequest,
)
from codrut.modules.communications.schemas import (
    CampaignRecipientBulkCreateRequest,
    CampaignRecipientCreateRequest,
    CampaignSendRequest,
)
from codrut.modules.companies.schemas import (
    CompanyAccessCodeRegistrationRequest,
    CompanyCreateRequest,
    ParticipantCreateRequest,
)
from codrut.modules.forms.schemas import QuestionnaireResponseSaveRequest
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import LoginRequest, SessionPrincipal

UUID_VALUE = "00000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize(
    ("model", "payload", "unknown_field"),
    [
        (
            LoginRequest,
            {"email": "trainer@example.com", "password": "password"},
            {"role": "trainer"},
        ),
        (CompanyCreateRequest, {"name": "Example"}, {"owner_id": UUID_VALUE}),
        (
            CompanyAccessCodeRegistrationRequest,
            {
                "email": "trainer@example.com",
                "password": "o frază lungă și memorabilă",
                "access_code": "ABCD-1234",
            },
            {"role": "trainer"},
        ),
        (
            ParticipantCreateRequest,
            {"full_name": "Ana Pop", "email": "ana@example.com"},
            {"user_id": UUID_VALUE},
        ),
        (
            AssignmentCreateRequest,
            {
                "respondent_profile_id": UUID_VALUE,
                "questionnaire_key": "pcm_base",
                "target_type": "self",
            },
            {"status": "submitted"},
        ),
        (
            QuestionnaireResponseSaveRequest,
            {"answers": {"q1": "yes"}},
            {"status": "submitted"},
        ),
        (CampaignSendRequest, {"mode": "new"}, {"owner_id": UUID_VALUE}),
        (
            CampaignRecipientCreateRequest,
            {
                "email": "buyer@example.com",
                "contact_name": "Buyer",
                "organization_name": "Example",
                "segment": "potential_customer",
            },
            {"owner_id": UUID_VALUE},
        ),
    ],
)
def test_write_contracts_reject_unknown_fields(
    model: type[BaseModel],
    payload: dict[str, object],
    unknown_field: dict[str, object],
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate({**payload, **unknown_field})

    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_nested_write_contracts_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssignmentPlanSaveRequest.model_validate(
            {
                "assignments": [
                    {
                        "respondent_profile_id": UUID_VALUE,
                        "questionnaire_key": "pcm_base",
                        "target_type": "self",
                        "status": "submitted",
                    }
                ]
            }
        )

    assert exc_info.value.errors()[0]["loc"] == ("assignments", 0, "status")
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_assignment_plan_save_accepts_known_planner_response_fields() -> None:
    payload = AssignmentPlanSaveRequest.model_validate(
        {
            "assignments": [
                {
                    "key": "manager:item",
                    "scope_id": "manager",
                    "scope_name": "Manager",
                    "scope_type": "manager",
                    "respondent_profile_id": UUID_VALUE,
                    "respondent_name": "Manager Ana",
                    "questionnaire_key": "pcm_base",
                    "target_type": "self",
                    "target_person_name": None,
                    "selected": True,
                    "existing_assignment_id": None,
                }
            ]
        }
    )

    assert payload.assignments[0].questionnaire_key == "pcm_base"


def test_campaign_bulk_json_payload_rejects_nested_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CampaignRecipientBulkCreateRequest.model_validate(
            {
                "recipients": [
                    {
                        "email": "buyer@example.com",
                        "contact_name": "Buyer",
                        "organization_name": "Example",
                        "segment": "potential_customer",
                        "owner_id": UUID_VALUE,
                    }
                ]
            }
        )

    assert exc_info.value.errors()[0]["loc"] == ("recipients", 0, "owner_id")
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_campaign_bulk_spreadsheet_payload_normalizes_away_source_columns() -> None:
    payload = CampaignRecipientBulkCreateRequest.model_validate(
        {
            "recipients": [
                {
                    "De trimis": "Da",
                    "Primul prenume": "Ana",
                    "Nume de familie": "Pop",
                    "Tip Client": "Nu e client",
                    "Organizație": "Example",
                    "Email": "ana@example.com",
                    "Telefon": "0700000000",
                }
            ]
        }
    )

    assert payload.recipients[0].email == "ana@example.com"
    assert payload.recipients[0].contact_name == "Ana Pop"
    assert payload.recipients[0].status == "active"


def test_session_principal_serialization_excludes_session_token() -> None:
    principal = SessionPrincipal(
        user_id=UUID(UUID_VALUE),
        email="trainer@example.com",
        role=UserRole.trainer,
        session_token="secret-session-token",  # noqa: S106
    )

    assert "session_token" not in principal.model_dump()
    assert "secret-session-token" not in principal.model_dump_json()


def test_openapi_response_schemas_do_not_expose_internal_secret_fields() -> None:
    schema = create_app().openapi()
    internal_fields = {
        "password_hash",
        "token_hash",
        "code_hash",
        "session_token",
        "session_secret",
        "task_link_secret",
        "email_brevo_api_key",
        "email_smtp_password",
    }

    leaked_fields = {
        field_name
        for component in schema["components"]["schemas"].values()
        for field_name in component.get("properties", {})
        if field_name in internal_fields
    }

    assert leaked_fields == set()
