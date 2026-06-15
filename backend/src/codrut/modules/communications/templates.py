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

PROMOTIONAL_SHELL_CLOSE = (
    '</div>'
    '<div style="margin-top:24px;padding-top:24px;border-top:1px solid #eadfdb;'
    'font-size:12px;line-height:1.5;color:#8c7e7b;text-align:center;">'
    '<p style="margin:0 0 8px;">Ai primit acest email deoarece ești abonat la actualizările noastre sau ești un client.</p>'
    '<p style="margin:0 0 8px;">'
    '<a href="https://app.codrut.ro/unsubscribe" style="color:#6d5f5b;text-decoration:underline;">Dezabonare</a>'
    '</p>'
    '<p style="margin:0;">Str. Exemplu Nr. 10, București, România</p>'
    '</div></div>'
)

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
        version=2,
        subject="Codruț: activează contul pentru ${company_name}",
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Contul tău Codruț este pregătit</h1>"
            + f"<p {GREETING_STYLE}>Bună, ${{participant_name}}.</p>"
            + f"<p {BODY_COPY_STYLE}>${{trainer_name}} te-a invitat în spațiul de evaluare "
            + "pentru ${company_name}. Pentru rolul tău, primul pas este activarea contului. "
            + "După înregistrare vei vedea dashboardul tău și sarcinile proiectului.</p>"
            + '<p style="margin:24px 0;"><a href="${action_url}" '
            + f'style="{PRIMARY_BUTTON_STYLE}">Activează contul</a></p>'
            + f"<p {HELP_TEXT_STYLE}>Dacă butonul nu funcționează, copiază linkul în "
            + "browser. Linkul este personal și nu trebuie redirecționat: ${action_url}</p>"
            + EMAIL_SHELL_CLOSE
        ),
        text_body=(
            "Bună, ${participant_name}.\n\n"
            "${trainer_name} te-a invitat în Codruț pentru ${company_name}.\n"
            "Activează contul înainte de a vedea sarcinile proiectului: ${action_url}\n\n"
            "Linkul este personal și nu trebuie redirecționat."
        ),
        required_context=frozenset(
            {"participant_name", "trainer_name", "company_name", "action_url"}
        ),
    ),
    TransactionalTemplateKey.assignment_bundle: TransactionalTemplate(
        key=TransactionalTemplateKey.assignment_bundle,
        version=2,
        subject="Codruț: ai ${task_count} chestionare pentru ${company_name}",
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Chestionarele tale sunt pregătite</h1>"
            + f"<p {GREETING_STYLE}>Bună, ${{participant_name}}.</p>"
            + f"<p {BODY_COPY_STYLE}>Pentru ${{company_name}}, ai ${{task_count}} chestionare "
            + "de completat într-un link securizat. Nu ai nevoie de cont. Răspunsurile sunt "
            + "confidențiale și sunt folosite doar în evaluarea proiectului.</p>"
            + '<p style="margin:24px 0;"><a href="${action_url}" '
            + f'style="{PRIMARY_BUTTON_STYLE}">Deschide chestionarele</a></p>'
            + f"<p {HELP_TEXT_STYLE}>Dacă butonul nu funcționează, copiază linkul în "
            + "browser. Linkul este personal și nu trebuie redirecționat: ${action_url}</p>"
            + EMAIL_SHELL_CLOSE
        ),
        text_body=(
            "Bună, ${participant_name}.\n\n"
            "Ai ${task_count} chestionare Codruț pentru ${company_name}.\n"
            "Deschide chestionarele aici: ${action_url}\n\n"
            "Nu ai nevoie de cont. Linkul este personal și nu trebuie redirecționat."
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
