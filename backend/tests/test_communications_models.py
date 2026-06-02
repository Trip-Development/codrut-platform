from sqlalchemy import ForeignKeyConstraint
from sqlalchemy.orm import configure_mappers

from codrut.core.database import Base
from codrut.modules.communications.models import EmailEventType, EmailSendStatus
from codrut.modules.companies import models as company_models  # noqa: F401
from codrut.modules.identity import models as identity_models  # noqa: F401


def test_email_delivery_tables_are_registered() -> None:
    assert {"email_sends", "email_events"}.issubset(Base.metadata.tables)
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
