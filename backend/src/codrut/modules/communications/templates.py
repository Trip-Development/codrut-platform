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


def _bullets(*items: str) -> str:
    return (
        '<ul style="margin:0 0 18px;padding-left:0;font-size:15px;line-height:1.65;list-style:none;">'
        + "".join(f'<li style="margin:0 0 8px;">{item}</li>' for item in items)
        + "</ul>"
    )


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


def _calendly_cta(label: str = "Alege un slot") -> str:
    return (
        f'<p style="margin:24px 0;"><a href="${{calendly_url}}" '
        f'data-codrut-cta="calendly" style="{PRIMARY_BUTTON_STYLE}">{label}</a></p>'
    )


PROMOTIONAL_REQUIRED_CONTEXT = frozenset({
    "first_name",
    "landing_page_url",
    "thumbnail_url",
    "calendly_url",
    "unsubscribe_url",
})


PROMOTIONAL_TEMPLATES: tuple[CatalogEmailTemplate, ...] = (
    CatalogEmailTemplate(
        key="promo_past_report_2022_2025",
        version=4,
        subject="Raportul de activitate pe care nu l-a cerut nimeni",
        audience="campaign:past_customer",
        required_context=PROMOTIONAL_REQUIRED_CONTEXT,
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Raport 2022-2025. Nesolicitat, dar sincer.</h1>"
            + f"<p {GREETING_STYLE}>${{first_name}},</p>"
            + _paragraphs(
                "Nu mi-ai cerut niciun update. Dar ți-l dau oricum, pentru că am 3 ani de freelancing și tu ești unul dintre oamenii pe care îmi doresc să îi revăd.",
                "Andrei Văcaru. Raport 2022-2025. Nesolicitat, dar sincer.",
            )
            + _bullets(
                "✓ A supraviețuit tranziției la freelancing fără episoade dramatice majore.",
                "✓ A obținut o certificare în Process Communication Model - pentru a duce comunicarea și înțelegerea personalității umane la următorul nivel.",
                "✓ A construit Influencing Skills for Trusted Stakeholder Partnerships - un program de 3 zile despre cum influențezi oameni fără să devii un personaj pe care nu ți-ar plăcea să îl întâlnești la o negociere.",
                "✓ A construit Născut pentru a Învinge - un program despre mintea subconștientă, starea de bine și de ce sabotăm exact ce ne dorim.",
                "✓ A adăugat în 2025 certificarea în Rapid Transformation Therapy by Marisa Peer - pentru ca rezultatele să fie cât mai rapide.",
                "✓ A livrat peste 1200 de sesiuni fără să adoarmă nimeni în sală, cel puțin nimeni pe care l-a văzut.",
                "✗ A neglijat să se reconecteze cu oameni cu care a lucrat bine.",
            )
            + _paragraphs(
                "Ultimul punct e motivul pentru care ești pe lista mea de primit emailul ăsta.",
                "Nu am nimic de vândut. Am chef de o conversație cu cineva care știe deja cum lucrez.",
            )
            + _video_cta("Video — 2 minute, mai interesante decât raportul de mai sus")
            + _calendly_cta("Alege un format — cafea, apel, Zoom")
            + _paragraphs("Dă reply acestui email sau alege un slot și revin eu cu propuneri de întâlnire.")
            + _paragraphs("Andrei")
            + PROMOTIONAL_SHELL_CLOSE
        ),
        text_body=(
            "${first_name},\n\n"
            "Nu mi-ai cerut niciun update. Dar ți-l dau oricum.\n\n"
            "Andrei Văcaru. Raport 2022-2025. Nesolicitat, dar sincer.\n"
            "✓ A supraviețuit tranziției la freelancing fără episoade dramatice majore.\n"
            "✓ A obținut o certificare în Process Communication Model.\n"
            "✓ A construit Influencing Skills for Trusted Stakeholder Partnerships.\n"
            "✓ A construit Născut pentru a Învinge.\n"
            "✓ A adăugat în 2025 certificarea în Rapid Transformation Therapy by Marisa Peer.\n"
            "✓ A livrat peste 1200 de sesiuni.\n"
            "✗ A neglijat să se reconecteze cu oameni cu care a lucrat bine.\n\n"
            "Nu am nimic de vândut. Am chef de o conversație cu cineva care știe deja cum lucrez.\n"
            "Video: ${landing_page_url}\n"
            "Alege un format — cafea, apel, Zoom: ${calendly_url}\n"
            "Sau dă reply acestui mail și revin eu cu propuneri de întâlnire.\n\n"
            "Andrei\n\n"
            "Dezabonare: ${unsubscribe_url}"
        ),
    ),
    CatalogEmailTemplate(
        key="promo_past_reactivation",
        version=4,
        subject="Departamentul de Reconectări Nesolicitate",
        audience="campaign:past_customer",
        required_context=PROMOTIONAL_REQUIRED_CONTEXT | frozenset({"company_name"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Relația profesională poate fi reactivată</h1>"
            + f"<p {GREETING_STYLE}>Salut, ${{first_name}}.</p>"
            + _paragraphs(
                "Îți scriu pentru a te informa că relația profesională cu Andrei Vacaru a fost marcată ca inactivă în sistem.",
                "Conform datelor disponibile, ultima interacțiune cu ${company_name} a avut loc în urmă cu mai mult timp decât ar fi trebuit.",
                "Motivul identificat: acel fenomen comun denumit viață ocupată, timp puțin.",
                "Ai la dispoziție două opțiuni:",
            )
            + _bullets(
                "Opțiunea A: Ignoră emailul. Relația se arhivează automat. Andrei supraviețuiește. Tu la fel. Toată lumea merge mai departe.",
                "Opțiunea B: Reactivează contul printr-o cafea, un apel sau 30 de minute de Zoom în care nimeni nu vinde nimic și toată lumea pleacă cu ceva util.",
            )
            + _paragraphs(
                "<strong>Datele cont:</strong>",
                "Titular: Andrei Văcaru.",
                "Status: freelancer din 2022, certificat PCM, certificat Rapid Transformation Therapy by Marisa Peer (2025), 1200+ sesiuni livrate, două programe noi super faine și perfecte pentru echipa ta, construite de la zero.",
                "Motive de reactivare recomandate: curiozitate, chef de o discuție bună.",
            )
            + _calendly_cta("Reactivează contul — alege un slot")
            + _paragraphs("Dă reply sau alege un slot și revin eu cu un mail pentru stabilirea unei întâlniri.")
            + _video_cta("Vezi ce s-a întâmplat cu contul în ultimii 3 ani — 2 minute")
            + _paragraphs("Andrei Vacaru")
            + PROMOTIONAL_SHELL_CLOSE
        ),
        text_body=(
            "Salut, ${first_name}.\n\n"
            "Relația profesională cu Andrei Vacaru poate fi reactivată printr-o cafea, un apel sau 30 de minute de Zoom.\n"
            "Alege un slot: ${calendly_url}\n"
            "Vezi contextul aici: ${landing_page_url}\n\n"
            "Dezabonare: ${unsubscribe_url}"
        ),
    ),
    CatalogEmailTemplate(
        key="promo_current_programs",
        version=4,
        subject="Acesta nu e un email de vânzare. (Dar dacă era, era bun.)",
        audience="campaign:past_customer",
        required_context=PROMOTIONAL_REQUIRED_CONTEXT,
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Am terminat ceva și vreau să îți arăt</h1>"
            + f"<p {GREETING_STYLE}>Salut, ${{first_name}}.</p>"
            + _paragraphs(
                'Știu ce crezi: "Andrei vrea ceva."',
                "Nu. Andrei a terminat ceva și vrea să îți arate.",
                "În ultimele luni am construit două programe noi care m-au ținut treaz noaptea - nu de stres, ci de entuziasm, ceea ce e mult mai periculos.",
                "Programul 1: Influencing Skills - cum să convingi oameni fără să te simți că ești un politician în campanie electorală. Cu PCM, cu Cialdini, cu stakeholder maps și conversații dificile.",
                "Programul 2: Născut pentru a Învinge - mind & well-being pentru oameni care nu vor corporate yoga. Scenarii de viață, subconștient, stări alterate, RTT (Rapid Transformation Therapy by Marisa Peer, proaspăt certificat în 2025). Genul de training după care oamenii sună acasă și zic că au înțeles ceva despre ei înșiși.",
                "A, încă un lucru: am dezvoltat un companion digital dotat cu inteligență artificială care este de-a dreptul fabulos pentru că va ajuta la testarea cunoștințelor, va face role-play cu participanții și va măsura evoluția lor în timp.",
                "Am făcut și un video scurt. E mai bun decât emailul ăsta.",
            )
            + _video_cta("Uită-te. 2 minute. Promit că nu cântă nimeni.")
            + _paragraphs("Dacă îți vine să vorbim - nu despre contracte, ci despre idei - iată calendarul meu:")
            + _calendly_cta("Alege un slot. Promit o cafea bună.")
            + _paragraphs("Sau dă reply și revin eu cu niște propuneri de întâlnire.", "Zi faină să ai!", "Andrei")
            + PROMOTIONAL_SHELL_CLOSE
        ),
        text_body=(
            "Salut, ${first_name}.\n\n"
            "Știu ce crezi: Andrei vrea ceva. Nu. Andrei a terminat ceva și vrea să îți arate.\n"
            "Am construit Influencing Skills, Născut pentru a Învinge și un companion digital cu inteligență artificială.\n"
            "Video: ${landing_page_url}\n"
            "Alege un slot: ${calendly_url}\n"
            "Sau dă reply și revin eu cu niște propuneri de întâlnire.\n\n"
            "Zi faină să ai!\nAndrei\n\n"
            "Dezabonare: ${unsubscribe_url}"
        ),
    ),
    CatalogEmailTemplate(
        key="promo_potential_intro",
        version=4,
        subject="Asta e un spam, dar e un spam bun. Nu am avut cum să fac altfel prima interacțiune.",
        audience="campaign:potential_customer",
        required_context=PROMOTIONAL_REQUIRED_CONTEXT,
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>O întrebare despre influență, comunicare și presiune</h1>"
            + f"<p {GREETING_STYLE}>Salut, ${{first_name}}.</p>"
            + _paragraphs(
                "Serios. Dacă totul merge perfect: stakeholderii sunt încântați, conversațiile dificile se rezolvă singure și toată lumea pleacă din ședințe motivată - închide acum. Nu am nimic pentru tine.",
                "Dacă continui să citești, bun.",
                "Înseamnă că recunoști acel moment specific: ședința în care ai știut exact ce trebuia spus și tot nu a ieșit cum trebuia. Prezentarea pregătită perfect care nu a convins pe nimeni. Colegul sau stakeholderul față de care simți că vorbești o limbă diferită deși amândoi vorbiți română.",
                "Eu lucrez cu exact spațiul ăla.",
                "Mă numesc Andrei Văcaru. 13 ani jurnalist TV. 10 ani trainer. 1200+ sesiuni. 15000+ oameni. Certificat PCM și din 2025 certificat în Rapid Transformation Therapy by Marisa Peer - care înseamnă că știu nu doar ce face un om, ci de ce continuă să o facă deși știe că nu îl ajută.",
                "Nu am un pitch. Am o întrebare: dacă ai putea schimba un singur lucru în felul în care oamenii tăi influențează, comunică sau gestionează presiunea, ce ar fi?",
                "Poți răspunde la emailul ăsta și stabilim o întâlnire de 30 sau 60 de minute. Sau, dacă preferi o conversație online:",
            )
            + _calendly_cta("Alege un slot. Îți răspund la întrebare live. Și promit și o cafea bună.")
            + _paragraphs("Fără obligații, fără vânzare. În cel mai rău caz, o discuție bună.")
            + _video_cta("Sau uită-te mai întâi la 2 minute de video - ca să știi cu cine vorbești")
            + _paragraphs("Zi faină să ai!", "Andrei Văcaru")
            + PROMOTIONAL_SHELL_CLOSE
        ),
        text_body=(
            "Salut, ${first_name}.\n\n"
            "Serios. Dacă totul merge perfect, poți închide acum. Nu am nimic pentru tine.\n"
            "Mă numesc Andrei Văcaru: 13 ani jurnalist TV, 10 ani trainer, 1200+ sesiuni, 15000+ oameni, certificat PCM și RTT.\n"
            "Dacă ai putea schimba un singur lucru în felul în care oamenii tăi comunică sau gestionează presiunea, ce ar fi?\n"
            "Alege un slot: ${calendly_url}\n"
            "Video: ${landing_page_url}\n\n"
            "Fără obligații, fără vânzare. În cel mai rău caz, o discuție bună.\n"
            "Zi faină să ai!\nAndrei Văcaru\n\n"
            "Dezabonare: ${unsubscribe_url}"
        ),
    ),
)


EVALUATION_TEMPLATES: tuple[CatalogEmailTemplate, ...] = (
    CatalogEmailTemplate(
        key="evaluation_leadership_invite",
        version=3,
        subject="Primul pas pe drumul nostru: o radiografie sinceră a echipei de direcție",
        audience="transactional:leadership",
        required_context=frozenset({"participant_name", "company_name", "action_url", "due_date", "sender_name"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Primul pas pe drumul nostru: o radiografie sinceră a echipei de direcție</h1>"
            + f"<p {GREETING_STYLE}>Dragi colegi,</p>"
            + _paragraphs(
                "Știți deja că pornim împreună la un drum care merită cu adevărat parcurs - unul care țintește dezvoltarea, creșterea și evoluția noastră ca echipă de direcție. Credem că o companie puternică se construiește, înainte de toate, prin oamenii care o conduc - adică prin noi.",
                "Ca orice demers serios, și acesta începe logic: cu o radiografie onestă, o imagine cât mai clară a punctului din care plecăm. Fără un punct de plecare bine măsurat, nu vom putea aprecia, mai târziu, cât de departe am ajuns.",
                "De aceea, vă invit să facem împreună primul pas. Vă rog să completați câteva chestionare scurte - ne vor da exact informațiile de care avem nevoie ca să:",
            )
            + _bullets(
                "înțelegem nivelul de la care pornim pe comportamentele și competențele importante pentru noi;",
                "vedem cum ne percepem reciproc în interiorul echipei de direcție;",
                "devenim mai conștienți de tiparele proprii, inclusiv de felul în care reacționăm sub presiune;",
                "înțelegem mai bine cum funcționează echipele pe care le conducem.",
            )
            + _paragraphs(
                "Un lucru esențial: totul este confidențial. Rezultatele sunt analizate doar agregat, la nivel de concluzii - nu de răspunsuri individuale. Singura persoană cu acces la răspunsuri este coach-ul extern care ne însoțește în acest proces, iar acestea rămân strict între el și fiecare dintre noi. Scopul nu este să evaluăm pe cineva, ci să construim o bază sănătoasă, de la care plecăm cu toții.",
                "Cu cât suntem mai sinceri acum, cu atât tot ce urmează va fi mai relevant și mai util pentru fiecare dintre noi. Onestitatea de azi e investiția cu cel mai bun randament din tot acest proces.",
                "Cum completați: dați click pe linkul de mai jos și parcurgeți chestionarele. Durează fiecare câteva minute bine investite. Vă rog să le finalizați până la ${due_date}.",
            )
            + _cta("Deschide chestionarele")
            + _paragraphs("Mă bucur că pornim la drum împreună. Hai să-l începem așa cum ne dorim să-l și continuăm: cu curaj și cu sinceritate.", "Cu respect,", "${sender_name}")
            + EMAIL_SHELL_CLOSE
        ),
        text_body=(
            "Dragi colegi,\n\n"
            "Pornim împreună la un drum care țintește dezvoltarea, creșterea și evoluția noastră ca echipă de direcție.\n"
            "Vă invit să completați câteva chestionare scurte. Ne ajută să înțelegem nivelul de la care pornim, cum ne percepem reciproc, tiparele proprii sub presiune și felul în care funcționează echipele pe care le conducem.\n\n"
            "Totul este confidențial, iar rezultatele sunt analizate agregat.\n"
            "Vă rog să le finalizați până la ${due_date}: ${action_url}\n\n"
            "Cu respect,\n${sender_name}"
        ),
    ),
    CatalogEmailTemplate(
        key="evaluation_leadership_reminder",
        version=3,
        subject="Reminder: mai sunt câteva zile pentru chestionare",
        audience="transactional:leadership",
        required_context=frozenset({"participant_name", "company_name", "action_url", "due_date", "sender_name"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Reminder pentru chestionare</h1>"
            + f"<p {GREETING_STYLE}>Dragi colegi,</p>"
            + _paragraphs(
                "O scurtă revenire - mai avem puțin până la ${due_date}, termenul pentru completarea chestionarelor cu care pornim pe acest drum.",
                "Dacă le-ați completat deja, vă mulțumesc - ați făcut deja primul pas. Dacă nu încă, știu bine că timpul vostru e prețios și agendele, pline. Tocmai de aceea vă cer doar câteva minute: rămâne una dintre cele mai bune investiții pe care le putem face acum în noi și în echipele noastre.",
                "Iar practic, lucrurile sunt simple: radiografia noastră de început este completă și corectă doar dacă suntem toți în ea. Lipsa unui singur răspuns ne schimbă imaginea de ansamblu.",
            )
            + _cta("Continuă chestionarele")
            + _paragraphs("Hai să închidem împreună acest prim pas.", "Cu respect, ${sender_name}")
            + EMAIL_SHELL_CLOSE
        ),
        text_body=(
            "Dragi colegi,\n\n"
            "O scurtă revenire: mai avem puțin până la ${due_date}, termenul pentru completarea chestionarelor.\n"
            "Radiografia noastră de început este completă și corectă doar dacă suntem toți în ea.\n"
            "Deschide chestionarele aici: ${action_url}\n\n"
            "Cu respect,\n${sender_name}"
        ),
    ),
    CatalogEmailTemplate(
        key="evaluation_team_invite",
        version=3,
        subject="Avem nevoie de părerea ta",
        audience="transactional:team",
        required_context=frozenset({"participant_name", "company_name", "action_url", "due_date", "sender_name"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Avem nevoie de părerea ta</h1>"
            + f"<p {GREETING_STYLE}>Bună ziua,</p>"
            + _paragraphs(
                "Noi, echipa de direcție, am pornit un proces prin care ne dorim să menținem aceleași standarde înalte pe care le cerem fiecăruia dintre voi - și credem că asta trebuie să înceapă cu noi înșine. Ca să facem asta cu adevărat, avem nevoie și de părerea ta.",
                "Te invităm să completezi două chestionare scurte care ne ajută să înțelegem două lucruri:",
            )
            + _bullets(
                "cât de bine reușim noi, echipa de direcție, să fim cu adevărat alături de tine și de colegii tăi - să vă sprijinim creșterea, să vă ajutăm să rezolvați mai ușor și mai repede provocările de zi cu zi și să facem asta într-un climat de lucru sănătos;",
                "cum se vede, din interior, echipa din care faci parte.",
            )
            + _paragraphs(
                "Răspunsurile tale sunt 100% anonime și confidențiale. Nu vom putea ști niciodată cine ce a răspuns - vedem doar concluziile agregate, imaginea de ansamblu, nu răspunsul tău individual. Tocmai de aceea te rugăm să fii cât mai sincer: feedbackul tău onest este singurul care ne ajută cu adevărat.",
                "Schimbarea reală într-o companie nu vine doar de sus în jos. Vine atunci când cei care conduc înțeleg, din perspectiva ta, ce funcționează bine și ce avem de îmbunătățit. Părerea ta contează exact în acest punct.",
                "Cum completezi: dă click pe linkul de mai jos și parcurge chestionarele. Durează aproximativ câteva minute. Te rugăm să le finalizezi până la ${due_date}.",
            )
            + _cta("Deschide chestionarele")
            + _paragraphs("Îți mulțumim că ne ajuți să fim o echipă de conducere mai bună - pentru tine și pentru toți colegii tăi.", "Cu mulțumiri,", "${sender_name}")
            + EMAIL_SHELL_CLOSE
        ),
        text_body=(
            "Bună ziua,\n\n"
            "Echipa de direcție a pornit un proces prin care își dorește să mențină aceleași standarde înalte pe care le cere fiecăruia dintre voi.\n"
            "Te invităm să completezi două chestionare scurte despre felul în care echipa de direcție este alături de tine și despre cum se vede, din interior, echipa din care faci parte.\n\n"
            "Răspunsurile tale sunt 100% anonime și confidențiale.\n"
            "Te rugăm să le finalizezi până la ${due_date}: ${action_url}\n\n"
            "Cu mulțumiri,\n${sender_name}"
        ),
    ),
    CatalogEmailTemplate(
        key="evaluation_team_reminder",
        version=3,
        subject="Mai e puțin timp — părerea ta încă lipsește",
        audience="transactional:team",
        required_context=frozenset({"participant_name", "company_name", "action_url", "due_date", "sender_name"}),
        html_body=(
            EMAIL_SHELL_OPEN
            + f"<h1 {HEADING_STYLE}>Mai e puțin timp</h1>"
            + f"<p {GREETING_STYLE}>Bună ziua,</p>"
            + _paragraphs(
                "Revin scurt: mai sunt câteva zile până la ${due_date}, ultima zi în care poți completa cele două chestionare.",
                "Dacă le-ai completat deja, îți mulțumim din suflet. Dacă nu, te rugăm să-ți iei cele câteva minute necesare - fiecare răspuns în plus face imaginea mai corectă, iar a ta încă lipsește.",
                "Și, ca să fie clar din nou: totul rămâne 100% anonim. Nu vom ști niciodată cine ce a răspuns, vedem doar concluziile la nivel de ansamblu. Tocmai de asta poți fi complet sincer.",
            )
            + _cta("Completează chestionarele")
            + _paragraphs("Mulțumim, ${sender_name}")
            + EMAIL_SHELL_CLOSE
        ),
        text_body=(
            "Bună ziua,\n\n"
            "Revin scurt: mai sunt câteva zile până la ${due_date}, ultima zi în care poți completa cele două chestionare.\n"
            "Fiecare răspuns în plus face imaginea mai corectă, iar a ta încă lipsește. Totul rămâne 100% anonim.\n"
            "Completează aici: ${action_url}\n\n"
            "Mulțumim,\n${sender_name}"
        ),
    ),
)


TRANSACTIONAL_TEMPLATES: dict[TransactionalTemplateKey, TransactionalTemplate] = {
    TransactionalTemplateKey.account_setup: TransactionalTemplate(
        key=TransactionalTemplateKey.account_setup,
        version=3,
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
        version=3,
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
