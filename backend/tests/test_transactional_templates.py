import pytest

from codrut.contracts.emails import EmailAddress
from codrut.core.errors import DomainError
from codrut.modules.communications.templates import (
    TransactionalTemplateKey,
    get_transactional_template,
)


def test_account_setup_template_renders_email_message() -> None:
    template = get_transactional_template(TransactionalTemplateKey.account_setup)

    message = template.render(
        to=EmailAddress("ana@example.com"),
        context={
            "participant_name": "Ana",
            "trainer_name": "Andrei",
            "company_name": "Demo",
            "action_url": "https://cody.andreivacaru.ro/invite/token",
        },
    )

    assert message.to.value == "ana@example.com"
    assert template.version == 5
    assert "Demo" in message.subject
    assert "Ana" in message.html_body
    assert "Cody" in message.html_body
    assert "https://cody.andreivacaru.ro/invite/token" in message.text_body


def test_assignment_bundle_template_renders_task_count() -> None:
    template = get_transactional_template(TransactionalTemplateKey.assignment_bundle)

    message = template.render(
        to=EmailAddress("ana@example.com"),
        context={
            "participant_name": "Ana",
            "company_name": "Demo",
            "task_count": "3",
            "action_url": "https://cody.andreivacaru.ro/tasks/token",
        },
    )

    assert template.version == 5
    assert "3 chestionare" in message.subject
    assert "3 chestionare" in message.html_body
    assert "Cody" in message.text_body


def test_template_render_rejects_missing_context() -> None:
    template = get_transactional_template(TransactionalTemplateKey.account_setup)

    with pytest.raises(DomainError, match="missing required values"):
        template.render(to=EmailAddress("ana@example.com"), context={})
