from dataclasses import dataclass
from enum import StrEnum
from string import Template

from codrut.contracts.emails import EmailAddress, EmailMessage
from codrut.core.errors import DomainError


class TransactionalTemplateKey(StrEnum):
    account_setup = "account_setup"
    assignment_bundle = "assignment_bundle"


EMAIL_SHELL_OPEN = (
    '<div style="font-family:Inter,Arial,sans-serif;max-width:620px;margin:0 auto;'
    'padding:28px;color:#2b211f;">'
    '<div style="border:1px solid #eadfdb;border-radius:18px;padding:28px;'
    'background:#fffdfb;">'
    '<p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#890505;'
    'letter-spacing:.08em;text-transform:uppercase;">Codruț</p>'
)
EMAIL_SHELL_CLOSE = "</div></div>"
BODY_COPY_STYLE = 'style="margin:0 0 18px;font-size:15px;line-height:1.65;"'
GREETING_STYLE = 'style="margin:0 0 14px;font-size:15px;line-height:1.65;"'
HELP_TEXT_STYLE = 'style="margin:0;font-size:13px;line-height:1.6;color:#6d5f5b;"'
HEADING_STYLE = 'style="margin:0 0 16px;font-size:24px;line-height:1.25;"'
PRIMARY_BUTTON_STYLE = (
    "display:inline-block;background:#890505;color:#ffffff;text-decoration:none;"
    "border-radius:12px;padding:13px 18px;font-weight:700;"
)


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
        subject="Invitație Codruț: activează contul pentru ${company_name}",
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Activează contul pentru ${{company_name}}</h1>"
            + f"<p {GREETING_STYLE}>Bună, ${{participant_name}}.</p>"
            + f"<p {BODY_COPY_STYLE}>${{trainer_name}} te-a invitat în Codruț. După "
            + "activare vei vedea dashboardul tău de participant și sarcinile "
            + "pregătite pentru proiect.</p>"
            + '<p style="margin:24px 0;"><a href="${action_url}" '
            + f'style="{PRIMARY_BUTTON_STYLE}">Activează contul</a></p>'
            + f"<p {HELP_TEXT_STYLE}>Dacă butonul nu funcționează, copiază linkul în "
            + "browser: ${action_url}</p>"
            + EMAIL_SHELL_CLOSE
        ),
        text_body=(
            "Bună, ${participant_name}.\n\n"
            "${trainer_name} te-a invitat în Codruț pentru ${company_name}.\n"
            "Activează contul și vezi sarcinile pregătite pentru proiect: ${action_url}"
        ),
        required_context=frozenset(
            {"participant_name", "trainer_name", "company_name", "action_url"}
        ),
    ),
    TransactionalTemplateKey.assignment_bundle: TransactionalTemplate(
        key=TransactionalTemplateKey.assignment_bundle,
        version=1,
        subject="Chestionarele tale Codruț pentru ${company_name}",
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Ai ${{task_count}} chestionare de completat</h1>"
            + f"<p {GREETING_STYLE}>Bună, ${{participant_name}}.</p>"
            + f"<p {BODY_COPY_STYLE}>Pentru ${{company_name}}, trainerul a pregătit "
            + "sarcinile tale într-un link securizat. Răspunsurile sunt tratate "
            + "confidențial și folosite în agregare.</p>"
            + '<p style="margin:24px 0;"><a href="${action_url}" '
            + f'style="{PRIMARY_BUTTON_STYLE}">Deschide chestionarele</a></p>'
            + f"<p {HELP_TEXT_STYLE}>Dacă butonul nu funcționează, copiază linkul în "
            + "browser: ${action_url}</p>"
            + EMAIL_SHELL_CLOSE
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
