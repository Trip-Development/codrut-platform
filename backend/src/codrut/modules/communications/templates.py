from dataclasses import dataclass
from enum import StrEnum
from string import Template

from codrut.contracts.emails import EmailAddress, EmailMessage
from codrut.core.errors import DomainError


class TransactionalTemplateKey(StrEnum):
    account_setup = "account_setup"
    assignment_bundle = "assignment_bundle"


@dataclass(frozen=True)
class TransactionalTemplate:
    key: TransactionalTemplateKey
    version: int
    subject: str
    html_body: str
    text_body: str
    required_context: frozenset[str]

    def render(self, *, to: EmailAddress, context: dict[str, str]) -> EmailMessage:
        missing = sorted(self.required_context - context.keys())
        if missing:
            raise DomainError(
                "Email template context is missing required values.",
                code="email_template_context_incomplete",
            )
        return EmailMessage(
            to=to,
            subject=_render_template(self.subject, context),
            html_body=_render_template(self.html_body, context),
            text_body=_render_template(self.text_body, context),
        )


TRANSACTIONAL_TEMPLATES: dict[TransactionalTemplateKey, TransactionalTemplate] = {
    TransactionalTemplateKey.account_setup: TransactionalTemplate(
        key=TransactionalTemplateKey.account_setup,
        version=1,
        subject="Activează contul Codruț pentru ${company_name}",
        html_body=(
            "<p>Bună, ${participant_name}.</p>"
            "<p>${trainer_name} te-a invitat în Codruț pentru ${company_name}.</p>"
            "<p><a href=\"${action_url}\">Activează contul și vezi sarcinile</a></p>"
        ),
        text_body=(
            "Bună, ${participant_name}.\n\n"
            "${trainer_name} te-a invitat în Codruț pentru ${company_name}.\n"
            "Activează contul și vezi sarcinile: ${action_url}"
        ),
        required_context=frozenset(
            {"participant_name", "trainer_name", "company_name", "action_url"}
        ),
    ),
    TransactionalTemplateKey.assignment_bundle: TransactionalTemplate(
        key=TransactionalTemplateKey.assignment_bundle,
        version=1,
        subject="Ai chestionare Codruț de completat pentru ${company_name}",
        html_body=(
            "<p>Bună, ${participant_name}.</p>"
            "<p>Ai ${task_count} sarcini de assessment pregătite în Codruț.</p>"
            "<p><a href=\"${action_url}\">Deschide sarcinile mele</a></p>"
        ),
        text_body=(
            "Bună, ${participant_name}.\n\n"
            "Ai ${task_count} sarcini de assessment pregătite în Codruț.\n"
            "Deschide sarcinile mele: ${action_url}"
        ),
        required_context=frozenset(
            {"participant_name", "company_name", "task_count", "action_url"}
        ),
    ),
}


def get_transactional_template(key: TransactionalTemplateKey) -> TransactionalTemplate:
    return TRANSACTIONAL_TEMPLATES[key]


def _render_template(template: str, context: dict[str, str]) -> str:
    return Template(template).substitute(context)
