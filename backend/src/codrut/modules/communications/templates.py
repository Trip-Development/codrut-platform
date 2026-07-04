# ruff: noqa: E501
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
    'letter-spacing:.08em;text-transform:uppercase;">Andrei Vacaru</p>'
)
EMAIL_SHELL_CLOSE = "</div></div>"

PROMOTIONAL_SHELL_CLOSE = (
    '</div>'
    '<div style="margin-top:24px;padding-top:24px;border-top:1px solid #eadfdb;'
    'font-size:12px;line-height:1.5;color:#8c7e7b;text-align:center;">'
    '<p style="margin:0 0 8px;">'
    "Ai primit acest email deoarece ești abonat la actualizările noastre sau ești un client."
    "</p>"
    '<p style="margin:0 0 8px;">'
    '<a href="${unsubscribe_url}" '
    'style="color:#6d5f5b;text-decoration:underline;">Dezabonare</a>'
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


@dataclass(frozen=True)
class CatalogEmailTemplate:
    key: str
    version: int
    subject: str
    html_body: str
    text_body: str
    required_context: frozenset[str]
    audience: str


def _paragraphs(*items: str) -> str:
    return "".join(f"<p {BODY_COPY_STYLE}>{item}</p>" for item in items)


def _cta(label: str, url_placeholder: str = "action_url") -> str:
    return (
        f'<p style="margin:24px 0;"><a href="${{{url_placeholder}}}" '
        f'style="{PRIMARY_BUTTON_STYLE}">{label}</a></p>'
    )


def _video_cta(alt: str = "Vezi video-ul") -> str:
    return (
        '<p style="margin:24px 0;">'
        '<a href="${landing_page_url}" style="display:block;text-decoration:none;color:inherit;">'
        '<span style="display:block;position:relative;max-width:420px;border-radius:14px;'
        'overflow:hidden;background:#2b211f;">'
        '<img src="${thumbnail_url}" alt="'
        + alt
        + '" style="display:block;width:100%;max-width:420px;height:auto;border:0;'
        'border-radius:14px;" />'
        '<span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);'
        'width:64px;height:64px;border-radius:999px;background:rgba(255,255,255,.92);'
        'box-shadow:0 14px 35px rgba(0,0,0,.22);text-align:center;line-height:64px;'
        'color:#890505;font-size:28px;font-weight:700;">&#9654;</span>'
        "</span></a></p>"
    )


PROMOTIONAL_TEMPLATES: tuple[CatalogEmailTemplate, ...] = (
    CatalogEmailTemplate(
        key="promo_past_report_2022_2025",
        version=1,
        subject="Raportul de activitate pe care nu l-a cerut nimeni",
        audience="campaign:past_customer",
        required_context=frozenset({"first_name", "landing_page_url", "thumbnail_url", "unsubscribe_url"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Raport 2022-2025. Nesolicitat, dar sincer.</h1>"
            + f"<p {GREETING_STYLE}>Salut, ${{first_name}}.</p>"
            + _paragraphs(
                "Nu mi-ai cerut niciun update. Dar ți-l dau oricum, pentru că am 3 ani de freelancing și tu ești unul dintre oamenii pe care îmi doresc să îi revăd.",
                "Andrei Vacaru. Raport 2022-2025: freelancer din 2022, certificat Process Communication Model, certificat Rapid Transformation Therapy by Marisa Peer și peste 1200 de sesiuni livrate.",
                "A neglijat să se reconecteze cu oameni cu care a lucrat bine. Ultimul punct e motivul pentru care ești pe lista mea de primit emailul ăsta.",
                "Nu am nimic de vândut. Am chef de o conversație cu cineva care știe deja cum lucrez.",
            )
            + _video_cta("Video de reconectare")
            + _paragraphs("Dă reply acestui email sau alege un slot și revin eu cu propuneri de întâlnire.", "Andrei")
            + PROMOTIONAL_SHELL_CLOSE
        ),
        text_body=(
            "Salut, ${first_name}.\n\n"
            "Raport 2022-2025: freelancer din 2022, certificat PCM, certificat RTT și 1200+ sesiuni livrate.\n"
            "Mi-ar plăcea să ne reconectăm. Vezi video-ul aici: ${landing_page_url}\n\n"
            "Dezabonare: ${unsubscribe_url}"
        ),
    ),
    CatalogEmailTemplate(
        key="promo_past_reactivation",
        version=1,
        subject="Departamentul de Reconectări Nesolicitate",
        audience="campaign:past_customer",
        required_context=frozenset({"first_name", "company_name", "landing_page_url", "thumbnail_url", "unsubscribe_url"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Relația profesională poate fi reactivată</h1>"
            + f"<p {GREETING_STYLE}>Salut, ${{first_name}}.</p>"
            + _paragraphs(
                "Îți scriu pentru a te informa că relația profesională cu Andrei Vacaru a fost marcată ca inactivă în sistem.",
                "Conform datelor disponibile, ultima interacțiune cu ${company_name} a avut loc în urmă cu mai mult timp decât ar fi trebuit.",
                "Ai la dispoziție două opțiuni: ignori emailul și toată lumea merge mai departe, sau reactivezi contul printr-o cafea, un apel ori 30 de minute de Zoom în care nimeni nu vinde nimic.",
                "Motive de reactivare recomandate: curiozitate și chef de o discuție bună.",
            )
            + _video_cta("Video reactivare cont")
            + _paragraphs("Dă reply și revin eu cu un mail pentru stabilirea unei întâlniri.", "Andrei Vacaru")
            + PROMOTIONAL_SHELL_CLOSE
        ),
        text_body=(
            "Salut, ${first_name}.\n\n"
            "Relația profesională cu Andrei Vacaru poate fi reactivată printr-o cafea, un apel sau 30 de minute de Zoom.\n"
            "Vezi contextul aici: ${landing_page_url}\n\n"
            "Dezabonare: ${unsubscribe_url}"
        ),
    ),
    CatalogEmailTemplate(
        key="promo_current_programs",
        version=1,
        subject="Acesta nu e un email de vânzare. (Dar dacă era, era bun.)",
        audience="campaign:past_customer",
        required_context=frozenset({"first_name", "landing_page_url", "thumbnail_url", "unsubscribe_url"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Am terminat ceva și vreau să îți arăt</h1>"
            + f"<p {GREETING_STYLE}>Salut, ${{first_name}}.</p>"
            + _paragraphs(
                "Știu ce crezi: Andrei vrea ceva. Nu. Andrei a terminat ceva și vrea să îți arate.",
                "Programul 1: Influencing Skills - cum să convingi oameni fără să te simți că ești politician în campanie electorală. Cu PCM, Cialdini, stakeholder maps și conversații dificile.",
                "Programul 2: Născut pentru a Învinge - mind & well-being pentru oameni care nu vor corporate yoga. Scenarii de viață, subconștient, stări alterate și RTT.",
                "Am dezvoltat și un companion digital cu inteligență artificială pentru testarea cunoștințelor, role-play și măsurarea evoluției în timp.",
            )
            + _video_cta("Video programe noi")
            + _paragraphs("Dacă îți vine să vorbim despre idei, dă reply sau alege un slot.", "Zi faină să ai! Andrei")
            + PROMOTIONAL_SHELL_CLOSE
        ),
        text_body=(
            "Salut, ${first_name}.\n\n"
            "Am construit Influencing Skills, Născut pentru a Învinge și un companion digital cu AI.\n"
            "Vezi video-ul aici: ${landing_page_url}\n\n"
            "Dezabonare: ${unsubscribe_url}"
        ),
    ),
    CatalogEmailTemplate(
        key="promo_potential_intro",
        version=1,
        subject="Asta e un spam, dar e un spam bun. Nu am avut cum să fac altfel prima interacțiune.",
        audience="campaign:potential_customer",
        required_context=frozenset({"first_name", "landing_page_url", "thumbnail_url", "unsubscribe_url"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>O întrebare despre influență, comunicare și presiune</h1>"
            + f"<p {GREETING_STYLE}>Salut, ${{first_name}}.</p>"
            + _paragraphs(
                "Dacă totul merge perfect - stakeholderii sunt încântați, conversațiile dificile se rezolvă singure și toată lumea pleacă din ședințe motivată - poți închide acum.",
                "Dacă ai continuat, probabil recunoști momentul în care ai știut exact ce trebuia spus și tot nu a ieșit cum trebuia.",
                "Mă numesc Andrei Vacaru. 13 ani jurnalist TV, 10 ani trainer, 1200+ sesiuni, 15000+ oameni. Certificat PCM și din 2025 certificat Rapid Transformation Therapy by Marisa Peer.",
                "Nu am un pitch. Am o întrebare: dacă ai putea schimba un singur lucru în felul în care oamenii tăi influențează, comunică sau gestionează presiunea, ce ar fi?",
            )
            + _video_cta("Video de prezentare")
            + _paragraphs("Poți răspunde la emailul ăsta sau putem stabili o conversație online.", "Zi faină să ai! Andrei Vacaru")
            + PROMOTIONAL_SHELL_CLOSE
        ),
        text_body=(
            "Salut, ${first_name}.\n\n"
            "Mă numesc Andrei Vacaru: 13 ani jurnalist TV, 10 ani trainer, 1200+ sesiuni, certificat PCM și RTT.\n"
            "Dacă ai putea schimba un singur lucru în felul în care oamenii tăi comunică sau gestionează presiunea, ce ar fi?\n"
            "Video: ${landing_page_url}\n\n"
            "Dezabonare: ${unsubscribe_url}"
        ),
    ),
)


EVALUATION_TEMPLATES: tuple[CatalogEmailTemplate, ...] = (
    CatalogEmailTemplate(
        key="evaluation_leadership_invite",
        version=1,
        subject="Primul pas pe drumul nostru: o radiografie sinceră a echipei de direcție",
        audience="transactional:leadership",
        required_context=frozenset({"participant_name", "company_name", "action_url", "due_date", "sender_name"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Primul pas pe drumul nostru</h1>"
            + f"<p {GREETING_STYLE}>Dragi colegi,</p>"
            + _paragraphs(
                "Pornim împreună la un drum care țintește dezvoltarea, creșterea și evoluția noastră ca echipă de direcție.",
                "Ca orice demers serios, acesta începe cu o radiografie onestă: o imagine cât mai clară a punctului din care plecăm.",
                "Vă invit să completați câteva chestionare scurte. Ne vor ajuta să înțelegem nivelul de la care pornim, cum ne percepem reciproc, tiparele proprii sub presiune și felul în care funcționează echipele pe care le conducem.",
                "Totul este confidențial. Rezultatele sunt analizate agregat, la nivel de concluzii, nu de răspunsuri individuale.",
                "Vă rog să finalizați chestionarele până la ${due_date}.",
            )
            + _cta("Deschide chestionarele")
            + _paragraphs("Mă bucur că pornim la drum împreună.", "Cu respect, ${sender_name}")
            + EMAIL_SHELL_CLOSE
        ),
        text_body="Dragi colegi,\n\nVă invit să completați chestionarele pentru ${company_name} până la ${due_date}: ${action_url}\n\nCu respect,\n${sender_name}",
    ),
    CatalogEmailTemplate(
        key="evaluation_leadership_reminder",
        version=1,
        subject="Reminder: mai sunt câteva zile pentru chestionare",
        audience="transactional:leadership",
        required_context=frozenset({"participant_name", "company_name", "action_url", "due_date", "sender_name"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Reminder pentru chestionare</h1>"
            + f"<p {GREETING_STYLE}>Dragi colegi,</p>"
            + _paragraphs(
                "Mai avem puțin până la ${due_date}, termenul pentru completarea chestionarelor cu care pornim pe acest drum.",
                "Radiografia noastră de început este completă și corectă doar dacă suntem toți în ea.",
            )
            + _cta("Continuă chestionarele")
            + _paragraphs("Hai să închidem împreună acest prim pas.", "Cu respect, ${sender_name}")
            + EMAIL_SHELL_CLOSE
        ),
        text_body="Dragi colegi,\n\nReminder: termenul este ${due_date}. Deschide chestionarele aici: ${action_url}\n\n${sender_name}",
    ),
    CatalogEmailTemplate(
        key="evaluation_team_invite",
        version=1,
        subject="Avem nevoie de părerea ta",
        audience="transactional:team",
        required_context=frozenset({"participant_name", "company_name", "action_url", "due_date", "sender_name"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Avem nevoie de părerea ta</h1>"
            + f"<p {GREETING_STYLE}>Bună ziua,</p>"
            + _paragraphs(
                "Echipa de direcție a pornit un proces prin care își dorește să mențină aceleași standarde înalte pe care le cere fiecăruia dintre voi.",
                "Te invităm să completezi două chestionare scurte care ne ajută să înțelegem cât de bine reușim să fim alături de tine și cum se vede, din interior, echipa din care faci parte.",
                "Răspunsurile tale sunt 100% anonime și confidențiale. Vedem doar concluziile agregate, nu răspunsul individual.",
                "Te rugăm să finalizezi chestionarele până la ${due_date}.",
            )
            + _cta("Deschide chestionarele")
            + _paragraphs("Îți mulțumim că ne ajuți să fim o echipă de conducere mai bună.", "Cu mulțumiri, ${sender_name}")
            + EMAIL_SHELL_CLOSE
        ),
        text_body="Bună ziua,\n\nTe invităm să completezi chestionarele pentru ${company_name} până la ${due_date}: ${action_url}\n\nMulțumim,\n${sender_name}",
    ),
    CatalogEmailTemplate(
        key="evaluation_team_reminder",
        version=1,
        subject="Mai e puțin timp — părerea ta încă lipsește",
        audience="transactional:team",
        required_context=frozenset({"participant_name", "company_name", "action_url", "due_date", "sender_name"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Mai e puțin timp</h1>"
            + f"<p {GREETING_STYLE}>Bună ziua,</p>"
            + _paragraphs(
                "Mai sunt câteva zile până la ${due_date}, ultima zi în care poți completa chestionarele.",
                "Fiecare răspuns în plus face imaginea mai corectă, iar al tău încă lipsește.",
                "Totul rămâne 100% anonim. Vedem doar concluzii la nivel de ansamblu.",
            )
            + _cta("Completează chestionarele")
            + _paragraphs("Mulțumim, ${sender_name}")
            + EMAIL_SHELL_CLOSE
        ),
        text_body="Bună ziua,\n\nMai este puțin timp până la ${due_date}. Completează aici: ${action_url}\n\nMulțumim,\n${sender_name}",
    ),
)


TRANSACTIONAL_TEMPLATES: dict[TransactionalTemplateKey, TransactionalTemplate] = {
    TransactionalTemplateKey.account_setup: TransactionalTemplate(
        key=TransactionalTemplateKey.account_setup,
        version=2,
        subject="Andrei Vacaru: activează contul pentru ${company_name}",
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
        subject="Andrei Vacaru: ai ${task_count} chestionare pentru ${company_name}",
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
