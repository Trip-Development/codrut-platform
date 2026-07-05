import { getApiBaseUrl, isDemoFallbackEnabled, isSeededDemoFallbackEnabled } from "./runtime";
import type { ApiRequestOptions } from "./companies";

export type EmailSurfaceStub = {
  id: string;
  name: string;
  lane: "transactional" | "campaign";
};

export type EmailTemplate = {
  id: string;
  baseKey: string;
  version: number;
  name: string;
  subject: string;
  body: string;
  textBody?: string;
  lane: "transactional" | "campaign";
  audience?: string | null;
  placeholders: string[];
};

const CATALOG_SHELL_OPEN =
  '<div style="font-family:Inter,Arial,sans-serif;max-width:620px;margin:0 auto;padding:28px;color:#2b211f;"><div style="border:1px solid #eadfdb;border-radius:18px;padding:28px;background:#fffdfb;"><p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#890505;letter-spacing:.08em;text-transform:uppercase;">Andrei Văcaru</p>';
const CATALOG_SHELL_CLOSE = "</div></div>";
const PROMO_SHELL_CLOSE =
  '</div><div style="margin-top:24px;padding-top:24px;border-top:1px solid #eadfdb;font-size:12px;line-height:1.5;color:#8c7e7b;text-align:center;"><p style="margin:0 0 8px;">Ai primit acest email deoarece ești abonat la actualizările noastre sau ești un client.</p><p style="margin:0 0 8px;"><a href="{unsubscribe_url}" style="color:#6d5f5b;text-decoration:underline;">Dezabonare</a></p><p style="margin:0;">Str. Exemplu Nr. 10, București, România</p></div></div>';
const CAMPAIGN_PLACEHOLDERS = ["{first_name}", "{landing_page_url}", "{thumbnail_url}", "{calendly_url}", "{unsubscribe_url}"];
const EVALUATION_PLACEHOLDERS = ["{participant_name}", "{company_name}", "{action_url}", "{due_date}", "{sender_name}"];

function catalogParagraphs(...items: string[]) {
  return items.map((item) => `<p style="margin:0 0 18px;font-size:15px;line-height:1.65;">${item}</p>`).join("");
}

function catalogBullets(...items: string[]) {
  const rows = items
    .map((item) => {
      const hasMarker = item.startsWith("✓") || item.startsWith("✗");
      const marker = hasMarker ? item.slice(0, 1) : "•";
      const body = hasMarker ? item.slice(1).trim() : item;
      return `<tr><td style="width:24px;padding:0 8px 8px 0;vertical-align:top;color:#890505;font-weight:700;">${marker}</td><td style="padding:0 0 8px;vertical-align:top;">${body}</td></tr>`;
    })
    .join("");
  return `<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;margin:0 0 18px;font-size:15px;line-height:1.65;border-collapse:collapse;">${rows}</table>`;
}

function catalogButton(label: string, href: string = "{action_url}") {
  return `<p style="margin:24px 0;"><a href="${href}" style="display:inline-block;background:#890505;color:#ffffff;text-decoration:none;border-radius:12px;padding:13px 18px;font-weight:700;">${label}</a></p><p style="margin:0;font-size:13px;line-height:1.6;color:#6d5f5b;">Link platformă: <a href="${href}" style="color:#890505;text-decoration:underline;">${href}</a></p>`;
}

function calendlyButton(label: string) {
  return `<p style="margin:24px 0;"><a href="{calendly_url}" data-codrut-cta="calendly" style="display:inline-block;background:#890505;color:#ffffff;text-decoration:none;border-radius:12px;padding:13px 18px;font-weight:700;">${label}</a></p>`;
}

function videoCard(alt: string) {
  return `<p style="margin:24px 0;"><a href="{landing_page_url}" style="display:block;text-decoration:none;color:inherit;"><span style="display:block;position:relative;max-width:420px;border-radius:14px;overflow:hidden;background:#2b211f;"><img src="{thumbnail_url}" alt="${alt}" style="display:block;width:100%;max-width:420px;height:auto;border:0;border-radius:14px;" /><span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:64px;height:64px;border-radius:999px;background:rgba(255,255,255,.92);box-shadow:0 14px 35px rgba(0,0,0,.22);text-align:center;line-height:64px;color:#890505;font-size:28px;font-weight:700;">&#9654;</span></span></a></p>`;
}

const SEEDED_TEMPLATES: EmailTemplate[] = [
  {
    id: "promo_past_report_2022_2025@9",
    baseKey: "promo_past_report_2022_2025",
    version: 9,
    name: "Promo clienți vechi - raport 2022-2025",
    subject: "Raportul de activitate pe care nu l-a cerut nimeni",
    lane: "campaign",
    audience: "campaign:past_customer",
    placeholders: CAMPAIGN_PLACEHOLDERS,
    body:
      CATALOG_SHELL_OPEN +
      '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">Raportul de activitate pe care nu l-a cerut nimeni</h1>' +
      '<p style="margin:0 0 14px;font-size:15px;line-height:1.65;">{first_name},</p>' +
      catalogParagraphs(
        "Nu mi-ai cerut niciun update. Dar ți-l dau oricum, pentru că am 3 ani de freelancing și tu ești unul dintre oamenii pe care îmi doresc să îi revăd.",
        "Andrei Văcaru. Raport 2022–2025. Nesolicitat dar sincer.",
      ) +
      catalogBullets(
        "✓ A supraviețuit tranziției la freelancing fără episoade dramatice majore",
        "✓ A obținut o certificare în Process Communication Model - pentru a duce comunicarea și înțelegerea personalității umane la următorul nivel",
        "✓ A construit Influencing Skills for Trusted Stakeholder Partnerships - un program de 3 zile despre cum influențezi oameni fără să devii un personaj pe care nu ți-ar plăcea să îl întâlnești la o negociere",
        "✓ A construit Născut pentru a Învinge - un program despre mintea subconștientă, starea de bine și de ce sabotăm exact ce ne dorim",
        "✓ A adăugat în 2025 certificarea în Rapid Transformation Therapy by Marisa Peer - pentru ca rezultatele să fie cât mai rapide",
        "✓ A livrat peste 1200 de sesiuni fără să adoarmă nimeni în sală (cel puțin nimeni pe care l-a văzut)",
        "✗ A neglijat să se reconecteze cu oameni cu care a lucrat bine",
      ) +
      catalogParagraphs(
        "Ultimul punct e motivul pentru care ești pe lista mea de primit emailul ăsta.",
        "Nu am nimic de vândut. Am chef de o conversație cu cineva care știe deja cum lucrez.",
      ) +
      videoCard("Video — 2 minute, mai interesante decât raportul de mai sus") +
      catalogParagraphs("Aici ai calendarul meu:") +
      calendlyButton("Alege un slot în Calendly") +
      catalogParagraphs("Sau dă reply acestui email și revin eu cu propuneri de întâlnire.", "Andrei") +
      PROMO_SHELL_CLOSE,
    textBody:
      "{first_name},\n\n" +
      "Nu mi-ai cerut niciun update. Dar ți-l dau oricum, pentru că am 3 ani de freelancing și tu ești unul dintre oamenii pe care îmi doresc să îi revăd.\n\n" +
      "Andrei Văcaru. Raport 2022–2025. Nesolicitat dar sincer.\n" +
      "✓ A supraviețuit tranziției la freelancing fără episoade dramatice majore\n" +
      "✓ A obținut o certificare în Process Communication Model - pentru a duce comunicarea și înțelegerea personalității umane la următorul nivel\n" +
      "✓ A construit Influencing Skills for Trusted Stakeholder Partnerships - un program de 3 zile despre cum influențezi oameni fără să devii un personaj pe care nu ți-ar plăcea să îl întâlnești la o negociere\n" +
      "✓ A construit Născut pentru a Învinge - un program despre mintea subconștientă, starea de bine și de ce sabotăm exact ce ne dorim\n" +
      "✓ A adăugat în 2025 certificarea în Rapid Transformation Therapy by Marisa Peer - pentru ca rezultatele să fie cât mai rapide\n" +
      "✓ A livrat peste 1200 de sesiuni fără să adoarmă nimeni în sală (cel puțin nimeni pe care l-a văzut)\n" +
      "✗ A neglijat să se reconecteze cu oameni cu care a lucrat bine\n\n" +
      "Ultimul punct e motivul pentru care ești pe lista mea de primit emailul ăsta.\n" +
      "Nu am nimic de vândut. Am chef de o conversație cu cineva care știe deja cum lucrez.\n" +
      "Video: {landing_page_url}\n" +
      "Alege un slot în Calendly: {calendly_url}\n" +
      "Sau dă reply acestui email și revin eu cu propuneri de întâlnire.\n\n" +
      "Andrei\n\n" +
      "Dezabonare: {unsubscribe_url}",
  },
  {
    id: "promo_past_reactivation@9",
    baseKey: "promo_past_reactivation",
    version: 9,
    name: "Promo clienți vechi - reactivare",
    subject: "Departamentul de Reconectări Nesolicitate",
    lane: "campaign",
    audience: "campaign:past_customer",
    placeholders: [...CAMPAIGN_PLACEHOLDERS, "{company_name}"],
    body:
      CATALOG_SHELL_OPEN +
      '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">Relația profesională poate fi reactivată</h1>' +
      '<p style="margin:0 0 14px;font-size:15px;line-height:1.65;">Salut, {first_name}.</p>' +
      catalogParagraphs(
        "Îți scriu pentru a te informa că relația profesională cu Andrei Văcaru a fost marcată ca inactivă în sistem.",
        "Conform datelor disponibile, ultima interacțiune cu {company_name} a avut loc în urmă cu mai mult timp decât ar fi trebuit.",
        "Motivul identificat: acel fenomen comun denumit viață ocupată, timp puțin.",
        "Ai la dispoziție două opțiuni:",
      ) +
      catalogBullets(
        "Opțiunea A: Ignoră emailul. Relația se arhivează automat. Andrei supraviețuiește. Tu la fel. Toată lumea merge mai departe.",
        "Opțiunea B: Reactivează contul printr-o cafea, un apel sau 30 de minute de Zoom în care nimeni nu vinde nimic și toată lumea pleacă cu ceva util.",
      ) +
      catalogParagraphs(
        "<strong>Datele cont:</strong>",
        "Titular: Andrei Văcaru.",
        "Status: freelancer din 2022, certificat PCM, certificat Rapid Transformation Therapy by Marisa Peer (2025), 1200+ sesiuni livrate, două programe noi super faine și perfecte pentru echipa ta, construite de la zero.",
        "Motive de reactivare recomandate: curiozitate, chef de o discuție bună.",
      ) +
      calendlyButton("Alege un slot în Calendly") +
      catalogParagraphs("Dă reply sau alege un slot și revin eu cu un email pentru stabilirea unei întâlniri.") +
      videoCard("Vezi ce s-a întâmplat cu contul în ultimii 3 ani — 2 minute") +
      catalogParagraphs("Andrei Văcaru") +
      PROMO_SHELL_CLOSE,
    textBody:
      "Salut, {first_name}.\n\n" +
      "Îți scriu pentru a te informa că relația profesională cu Andrei Văcaru a fost marcată ca inactivă în sistem.\n" +
      "Conform datelor disponibile, ultima interacțiune cu {company_name} a avut loc în urmă cu mai mult timp decât ar fi trebuit.\n" +
      "Motivul identificat: acel fenomen comun denumit viață ocupată, timp puțin.\n\n" +
      "Ai la dispoziție două opțiuni:\n" +
      "• Opțiunea A: Ignoră emailul. Relația se arhivează automat. Andrei supraviețuiește. Tu la fel. Toată lumea merge mai departe.\n" +
      "• Opțiunea B: Reactivează contul printr-o cafea, un apel sau 30 de minute de Zoom în care nimeni nu vinde nimic și toată lumea pleacă cu ceva util.\n\n" +
      "Datele cont:\n" +
      "Titular: Andrei Văcaru.\n" +
      "Status: freelancer din 2022, certificat PCM, certificat Rapid Transformation Therapy by Marisa Peer (2025), 1200+ sesiuni livrate, două programe noi super faine și perfecte pentru echipa ta, construite de la zero.\n" +
      "Motive de reactivare recomandate: curiozitate, chef de o discuție bună.\n\n" +
      "Alege un slot în Calendly: {calendly_url}\n" +
      "Dă reply sau alege un slot și revin eu cu un email pentru stabilirea unei întâlniri.\n" +
      "Video: {landing_page_url}\n\n" +
      "Andrei Văcaru\n\n" +
      "Dezabonare: {unsubscribe_url}",
  },
  {
    id: "promo_current_programs@9",
    baseKey: "promo_current_programs",
    version: 9,
    name: "Promo clienți existenți - programe noi",
    subject: "Acesta nu e un email de vânzare. (Dar dacă era, era bun.)",
    lane: "campaign",
    audience: "campaign:past_customer",
    placeholders: CAMPAIGN_PLACEHOLDERS,
    body:
      CATALOG_SHELL_OPEN +
      '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">Am terminat ceva și vreau să îți arăt</h1>' +
      '<p style="margin:0 0 14px;font-size:15px;line-height:1.65;">Salut, {first_name}.</p>' +
      catalogParagraphs(
        'Știu ce crezi: "Andrei vrea ceva."',
        "Nu. Andrei a terminat ceva și vrea să îți arate.",
        "În ultimele luni am construit două programe noi care m-au ținut treaz noaptea — nu de stres, ci de entuziasm, ceea ce e mult mai periculos.",
        "Programul 1: Influencing Skills — cum să convingi oameni fără să te simți că ești un politician în campanie electorală. Cu PCM, cu Cialdini, cu stakeholder maps și conversații dificile.",
        "Programul 2: Născut pentru a Învinge — mind & well-being pentru oameni care nu vor corporate yoga. Scenarii de viață, subconștient, stări alterate, RTT (Rapid Transformation Therapy by Marisa Peer, proaspăt certificat în 2025). Genul de training după care oamenii sună acasă și zic că au înțeles ceva despre ei înșiși.",
        "A, încă un lucru: am dezvoltat un companion digital dotat cu inteligență artificială care este de-a dreptul fabulos pentru că va ajuta la testarea cunoștințelor, va face role-play cu participanții și va măsura evoluția lor în timp.",
        "Am făcut și un video scurt. E mai bun decât emailul ăsta.",
      ) +
      videoCard("Uită-te. 2 minute. Promit că nu cântă nimeni.") +
      catalogParagraphs("Dacă îți vine să vorbim — nu despre contracte, ci despre idei — iată calendarul meu:") +
      calendlyButton("Alege un slot în Calendly") +
      catalogParagraphs("Sau dă reply și revin eu cu niște propuneri de întâlnire.", "Zi faină să ai!", "Andrei") +
      PROMO_SHELL_CLOSE,
    textBody:
      "Salut, {first_name}.\n\n" +
      'Știu ce crezi: "Andrei vrea ceva."\n' +
      "Nu. Andrei a terminat ceva și vrea să îți arate.\n\n" +
      "În ultimele luni am construit două programe noi care m-au ținut treaz noaptea — nu de stres, ci de entuziasm, ceea ce e mult mai periculos.\n" +
      "Programul 1: Influencing Skills — cum să convingi oameni fără să te simți că ești un politician în campanie electorală. Cu PCM, cu Cialdini, cu stakeholder maps și conversații dificile.\n" +
      "Programul 2: Născut pentru a Învinge — mind & well-being pentru oameni care nu vor corporate yoga. Scenarii de viață, subconștient, stări alterate, RTT (Rapid Transformation Therapy by Marisa Peer, proaspăt certificat în 2025). Genul de training după care oamenii sună acasă și zic că au înțeles ceva despre ei înșiși.\n" +
      "A, încă un lucru: am dezvoltat un companion digital dotat cu inteligență artificială care este de-a dreptul fabulos pentru că va ajuta la testarea cunoștințelor, va face role-play cu participanții și va măsura evoluția lor în timp.\n\n" +
      "Am făcut și un video scurt. E mai bun decât emailul ăsta.\n" +
      "Video: {landing_page_url}\n" +
      "Dacă îți vine să vorbim — nu despre contracte, ci despre idei — iată calendarul meu:\n" +
      "Alege un slot în Calendly: {calendly_url}\n" +
      "Sau dă reply și revin eu cu niște propuneri de întâlnire.\n\n" +
      "Zi faină să ai!\nAndrei\n\n" +
      "Dezabonare: {unsubscribe_url}",
  },
  {
    id: "promo_potential_intro@9",
    baseKey: "promo_potential_intro",
    version: 9,
    name: "Promo prospect - prima interacțiune",
    subject: "Asta e un spam, dar e un spam bun. Nu am avut cum să fac altfel prima interacțiune.",
    lane: "campaign",
    audience: "campaign:potential_customer",
    placeholders: CAMPAIGN_PLACEHOLDERS,
    body:
      CATALOG_SHELL_OPEN +
      '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">O întrebare despre influență, comunicare și presiune</h1>' +
      '<p style="margin:0 0 14px;font-size:15px;line-height:1.65;">Salut, {first_name}.</p>' +
      catalogParagraphs(
        "Serios. Dacă totul merge perfect: stakeholderii sunt încântați, conversațiile dificile se rezolvă singure și toată lumea pleacă din ședințe motivată - închide acum. Nu am nimic pentru tine.",
        "Dacă continui să citești, bun.",
        "Înseamnă că recunoști acel moment specific: ședința în care ai știut exact ce trebuia spus și tot nu a ieșit cum trebuia. Prezentarea pregătită perfect care nu a convins pe nimeni. Colegul sau stakeholderul față de care simți că vorbești o limbă diferită deși amândoi vorbiți română.",
        "Eu lucrez cu exact spațiul ăla.",
        "Mă numesc Andrei Văcaru. 13 ani jurnalist TV. 10 ani trainer. 1200+ sesiuni. 15000+ oameni. Certificat PCM și din 2025 certificat în Rapid Transformation Therapy by Marisa Peer — care înseamnă că știu nu doar ce face un om, ci de ce continuă să o facă deși știe că nu îl ajută.",
        "Nu am un pitch. Am o întrebare: dacă ai putea schimba un singur lucru în felul în care oamenii tăi influențează, comunică sau gestionează presiunea, ce ar fi?",
        "Poți răspunde la emailul ăsta și stabilim o întâlnire de 30 sau 60 de minute. Sau, dacă preferi o conversație online:",
      ) +
      calendlyButton("Alege un slot în Calendly") +
      catalogParagraphs("Fără obligații, fără vânzare. În cel mai rău caz, o discuție bună.") +
      videoCard("Sau uită-te mai întâi la 2 minute de video - ca să știi cu cine vorbești") +
      catalogParagraphs("Zi faină să ai!", "Andrei Văcaru") +
      PROMO_SHELL_CLOSE,
    textBody:
      "Salut, {first_name}.\n\n" +
      "Serios. Dacă totul merge perfect: stakeholderii sunt încântați, conversațiile dificile se rezolvă singure și toată lumea pleacă din ședințe motivată - închide acum. Nu am nimic pentru tine.\n" +
      "Dacă continui să citești, bun.\n\n" +
      "Înseamnă că recunoști acel moment specific: ședința în care ai știut exact ce trebuia spus și tot nu a ieșit cum trebuia. Prezentarea pregătită perfect care nu a convins pe nimeni. Colegul sau stakeholderul față de care simți că vorbești o limbă diferită deși amândoi vorbiți română.\n" +
      "Eu lucrez cu exact spațiul ăla.\n\n" +
      "Mă numesc Andrei Văcaru. 13 ani jurnalist TV. 10 ani trainer. 1200+ sesiuni. 15000+ oameni. Certificat PCM și din 2025 certificat în Rapid Transformation Therapy by Marisa Peer — care înseamnă că știu nu doar ce face un om, ci de ce continuă să o facă deși știe că nu îl ajută.\n\n" +
      "Nu am un pitch. Am o întrebare:\n" +
      "Dacă ai putea schimba un singur lucru în felul în care oamenii tăi influențează, comunică sau gestionează presiunea — ce ar fi?\n\n" +
      "Poți răspunde la emailul ăsta și stabilim o întâlnire de 30 sau 60 de minute. Sau, dacă preferi o conversație online:\n" +
      "Alege un slot în Calendly: {calendly_url}\n" +
      "Fără obligații, fără vânzare. În cel mai rău caz, o discuție bună.\n" +
      "Video: {landing_page_url}\n\n" +
      "Zi faină să ai!\nAndrei Văcaru\n\n" +
      "Dezabonare: {unsubscribe_url}",
  },
  {
    id: "evaluation_leadership_invite@7",
    baseKey: "evaluation_leadership_invite",
    version: 7,
    name: "Evaluare leadership - invitație",
    subject: "Primul pas pe drumul nostru: o radiografie sinceră a echipei de direcție",
    lane: "transactional",
    audience: "transactional:leadership",
    placeholders: EVALUATION_PLACEHOLDERS,
    body:
      CATALOG_SHELL_OPEN +
      '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">Primul pas pe drumul nostru: o radiografie sinceră a echipei de direcție</h1>' +
      '<p style="margin:0 0 14px;font-size:15px;line-height:1.65;">Dragi colegi,</p>' +
      catalogParagraphs(
        "Știți deja că pornim împreună la un drum care merită cu adevărat parcurs — unul care țintește dezvoltarea, creșterea și evoluția noastră ca echipă de direcție. Credem că o companie puternică se construiește, înainte de toate, prin oamenii care o conduc — adică prin noi.",
        "Ca orice demers serios, și acesta începe logic: cu o radiografie onestă, o imagine cât mai clară a punctului din care plecăm. Fără un punct de plecare bine măsurat, nu vom putea aprecia, mai târziu, cât de departe am ajuns.",
        "De aceea, vă invit să facem împreună primul pas. Vă rog să completați câteva chestionare scurte — ne vor da exact informațiile de care avem nevoie ca să:",
      ) +
      catalogBullets(
        "înțelegem nivelul de la care pornim pe comportamentele și competențele importante pentru noi;",
        "vedem cum ne percepem reciproc în interiorul echipei de direcție;",
        "devenim mai conștienți de tiparele proprii, inclusiv de felul în care reacționăm sub presiune;",
        "înțelegem mai bine cum funcționează echipele pe care le conducem.",
      ) +
      catalogParagraphs(
        "Un lucru esențial: totul este confidențial. Rezultatele sunt analizate doar agregat, la nivel de concluzii — nu de răspunsuri individuale. Singura persoană cu acces la răspunsuri este coach-ul extern care ne însoțește în acest proces, iar acestea rămân strict între el și fiecare dintre noi. Scopul nu este să evaluăm pe cineva, ci să construim o bază sănătoasă, de la care plecăm cu toții.",
        "Cu cât suntem mai sinceri acum, cu atât tot ce urmează va fi mai relevant și mai util pentru fiecare dintre noi. Onestitatea de azi e investiția cu cel mai bun randament din tot acest proces.",
        "Cum completați: dați click pe linkul de mai jos și parcurgeți chestionarele. Durează fiecare aproximativ câteva minute bine investite. Vă rog să le finalizați până la {due_date}.",
      ) +
      catalogButton("Deschide chestionarele") +
      catalogParagraphs("Mă bucur că pornim la drum împreună. Hai să-l începem așa cum ne dorim să-l și continuăm: cu curaj și cu sinceritate.", "Cu respect,", "{sender_name}") +
      CATALOG_SHELL_CLOSE,
    textBody:
      "Dragi colegi,\n\n" +
      "Știți deja că pornim împreună la un drum care merită cu adevărat parcurs — unul care țintește dezvoltarea, creșterea și evoluția noastră ca echipă de direcție. Credem că o companie puternică se construiește, înainte de toate, prin oamenii care o conduc — adică prin noi.\n\n" +
      "Ca orice demers serios, și acesta începe logic: cu o radiografie onestă, o imagine cât mai clară a punctului din care plecăm. Fără un punct de plecare bine măsurat, nu vom putea aprecia, mai târziu, cât de departe am ajuns.\n\n" +
      "De aceea, vă invit să facem împreună primul pas. Vă rog să completați câteva chestionare scurte — ne vor da exact informațiile de care avem nevoie ca să:\n" +
      "• înțelegem nivelul de la care pornim pe comportamentele și competențele importante pentru noi;\n" +
      "• vedem cum ne percepem reciproc în interiorul echipei de direcție;\n" +
      "• devenim mai conștienți de tiparele proprii, inclusiv de felul în care reacționăm sub presiune;\n" +
      "• înțelegem mai bine cum funcționează echipele pe care le conducem.\n\n" +
      "Un lucru esențial: totul este confidențial. Rezultatele sunt analizate doar agregat, la nivel de concluzii — nu de răspunsuri individuale. Singura persoană cu acces la răspunsuri este coach-ul extern care ne însoțește în acest proces, iar acestea rămân strict între el și fiecare dintre noi. Scopul nu este să evaluăm pe cineva, ci să construim o bază sănătoasă, de la care plecăm cu toții.\n\n" +
      "Cu cât suntem mai sinceri acum, cu atât tot ce urmează va fi mai relevant și mai util pentru fiecare dintre noi. Onestitatea de azi e investiția cu cel mai bun randament din tot acest proces.\n\n" +
      "Cum completați: dați click pe linkul de mai jos și parcurgeți chestionarele. Durează fiecare aproximativ câteva minute bine investite. Vă rog să le finalizați până la {due_date}.\n" +
      "Link platformă: {action_url}\n\n" +
      "Mă bucur că pornim la drum împreună. Hai să-l începem așa cum ne dorim să-l și continuăm: cu curaj și cu sinceritate.\n\n" +
      "Cu respect,\n{sender_name}",
  },
  {
    id: "evaluation_leadership_reminder@7",
    baseKey: "evaluation_leadership_reminder",
    version: 7,
    name: "Evaluare leadership - reminder",
    subject: "Reminder: mai sunt câteva zile pentru chestionare",
    lane: "transactional",
    audience: "transactional:leadership",
    placeholders: EVALUATION_PLACEHOLDERS,
    body: CATALOG_SHELL_OPEN + '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">Reminder pentru chestionare</h1>' + '<p style="margin:0 0 14px;font-size:15px;line-height:1.65;">Dragi colegi,</p>' + catalogParagraphs("O scurtă revenire — mai avem puțin până la {due_date}, termenul pentru completarea chestionarelor cu care pornim pe acest drum.", "Dacă le-ați completat deja, vă mulțumesc — ați făcut deja primul pas. Dacă nu încă, știu bine că timpul vostru e prețios și agendele, pline. Tocmai de aceea vă cer doar câteva minute: rămâne una dintre cele mai bune investiții pe care le putem face acum în noi și în echipele noastre.", "Iar practic, lucrurile sunt simple: radiografia noastră de început este completă și corectă doar dacă suntem toți în ea. Lipsa unui singur răspuns ne schimbă imaginea de ansamblu.") + catalogButton("Continuă chestionarele") + catalogParagraphs("Hai să închidem împreună acest prim pas.", "Cu respect, {sender_name}") + CATALOG_SHELL_CLOSE,
    textBody:
      "Dragi colegi,\n\n" +
      "O scurtă revenire — mai avem puțin până la {due_date}, termenul pentru completarea chestionarelor cu care pornim pe acest drum.\n\n" +
      "Dacă le-ați completat deja, vă mulțumesc — ați făcut deja primul pas. Dacă nu încă, știu bine că timpul vostru e prețios și agendele, pline. Tocmai de aceea vă cer doar câteva minute: rămâne una dintre cele mai bune investiții pe care le putem face acum în noi și în echipele noastre.\n\n" +
      "Iar practic, lucrurile sunt simple: radiografia noastră de început este completă și corectă doar dacă suntem toți în ea. Lipsa unui singur răspuns ne schimbă imaginea de ansamblu.\n\n" +
      "Link platformă: {action_url}\n\n" +
      "Hai să închidem împreună acest prim pas.\n\n" +
      "Cu respect,\n{sender_name}",
  },
  {
    id: "evaluation_team_invite@7",
    baseKey: "evaluation_team_invite",
    version: 7,
    name: "Evaluare echipe - invitație",
    subject: "Avem nevoie de părerea ta",
    lane: "transactional",
    audience: "transactional:team",
    placeholders: EVALUATION_PLACEHOLDERS,
    body: CATALOG_SHELL_OPEN + '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">Avem nevoie de părerea ta</h1>' + '<p style="margin:0 0 14px;font-size:15px;line-height:1.65;">Bună ziua,</p>' + catalogParagraphs("Noi, echipa de direcție, am pornit un proces prin care ne dorim să menținem aceleași standarde înalte pe care le cerem fiecăruia dintre voi — și credem că asta trebuie să înceapă cu noi înșine. Ca să facem asta cu adevărat, avem nevoie și de părerea ta.", "Te invităm să completezi două chestionare scurte care ne ajută să înțelegem două lucruri:") + catalogBullets("cât de bine reușim noi, echipa de direcție, să fim cu adevărat alături de tine și de colegii tăi — să vă sprijinim creșterea, să vă ajutăm să rezolvați mai ușor și mai repede provocările de zi cu zi și să facem asta într-un climat de lucru sănătos;", "cum se vede, din interior, echipa din care faci parte.") + catalogParagraphs("Răspunsurile tale sunt 100% anonime și confidențiale. Nu vom putea ști niciodată cine ce a răspuns — vedem doar concluziile agregate, imaginea de ansamblu, nu răspunsul tău individual. Tocmai de aceea te rugăm să fii cât mai sincer: feedbackul tău onest este singurul care ne ajută cu adevărat.", "Schimbarea reală într-o companie nu vine doar de sus în jos. Vine atunci când cei care conduc înțeleg, din perspectiva ta, ce funcționează bine și ce avem de îmbunătățit. Părerea ta contează exact în acest punct.", "Cum completezi: dă click pe linkul de mai jos și parcurge chestionarele. Durează aproximativ câteva minute. Te rugăm să le finalizezi până la {due_date}.") + catalogButton("Deschide chestionarele") + catalogParagraphs("Îți mulțumim că ne ajuți să fim o echipă de conducere mai bună — pentru tine și pentru toți colegii tăi.", "Cu mulțumiri,", "{sender_name}") + CATALOG_SHELL_CLOSE,
    textBody:
      "Bună ziua,\n\n" +
      "Noi, echipa de direcție, am pornit un proces prin care ne dorim să menținem aceleași standarde înalte pe care le cerem fiecăruia dintre voi — și credem că asta trebuie să înceapă cu noi înșine. Ca să facem asta cu adevărat, avem nevoie și de părerea ta.\n\n" +
      "Te invităm să completezi două chestionare scurte care ne ajută să înțelegem două lucruri:\n" +
      "• cât de bine reușim noi, echipa de direcție, să fim cu adevărat alături de tine și de colegii tăi — să vă sprijinim creșterea, să vă ajutăm să rezolvați mai ușor și mai repede provocările de zi cu zi și să facem asta într-un climat de lucru sănătos;\n" +
      "• cum se vede, din interior, echipa din care faci parte.\n\n" +
      "Răspunsurile tale sunt 100% anonime și confidențiale. Nu vom putea ști niciodată cine ce a răspuns — vedem doar concluziile agregate, imaginea de ansamblu, nu răspunsul tău individual. Tocmai de aceea te rugăm să fii cât mai sincer: feedbackul tău onest este singurul care ne ajută cu adevărat.\n\n" +
      "Schimbarea reală într-o companie nu vine doar de sus în jos. Vine atunci când cei care conduc înțeleg, din perspectiva ta, ce funcționează bine și ce avem de îmbunătățit. Părerea ta contează exact în acest punct.\n\n" +
      "Cum completezi: dă click pe linkul de mai jos și parcurge chestionarele. Durează aproximativ câteva minute. Te rugăm să le finalizezi până la {due_date}.\n" +
      "Link platformă: {action_url}\n\n" +
      "Îți mulțumim că ne ajuți să fim o echipă de conducere mai bună — pentru tine și pentru toți colegii tăi.\n\n" +
      "Cu mulțumiri,\n{sender_name}",
  },
  {
    id: "evaluation_team_reminder@7",
    baseKey: "evaluation_team_reminder",
    version: 7,
    name: "Evaluare echipe - reminder",
    subject: "Mai e puțin timp — părerea ta încă lipsește",
    lane: "transactional",
    audience: "transactional:team",
    placeholders: EVALUATION_PLACEHOLDERS,
    body: CATALOG_SHELL_OPEN + '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">Mai e puțin timp</h1>' + '<p style="margin:0 0 14px;font-size:15px;line-height:1.65;">Bună ziua,</p>' + catalogParagraphs("Revin scurt: mai sunt câteva zile până la {due_date}, ultima zi în care poți completa cele două chestionare.", "Dacă le-ai completat deja, îți mulțumim din suflet. Dacă nu, te rugăm să-ți iei cele câteva minute necesare — fiecare răspuns în plus face imaginea mai corectă, iar a ta încă lipsește.", "Și, ca să fie clar din nou: totul rămâne 100% anonim. Nu vom ști niciodată cine ce a răspuns, vedem doar concluziile la nivel de ansamblu. Tocmai de asta poți fi complet sincer.") + catalogButton("Completează chestionarele") + catalogParagraphs("Mulțumim,", "{sender_name}") + CATALOG_SHELL_CLOSE,
    textBody:
      "Bună ziua,\n\n" +
      "Revin scurt: mai sunt câteva zile până la {due_date}, ultima zi în care poți completa cele două chestionare.\n" +
      "Dacă le-ai completat deja, îți mulțumim din suflet. Dacă nu, te rugăm să-ți iei cele câteva minute necesare — fiecare răspuns în plus face imaginea mai corectă, iar a ta încă lipsește.\n\n" +
      "Și, ca să fie clar din nou: totul rămâne 100% anonim. Nu vom ști niciodată cine ce a răspuns, vedem doar concluziile la nivel de ansamblu. Tocmai de asta poți fi complet sincer.\n\n" +
      "Link platformă: {action_url}\n\n" +
      "Mulțumim,\n{sender_name}",
  },
];

function getSeededTemplates(): EmailTemplate[] {
  return SEEDED_TEMPLATES.map((template) => ({
    ...template,
    placeholders: [...template.placeholders],
  }));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function backendToFrontendTemplate(b: any): EmailTemplate {
  const placeholders = (b.variables || []).map((v: string) => `{${v}}`);
  const subject = (b.subject || "").replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");
  const body = (b.html_body || "").replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");
  const textBody = (b.text_body || "").replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");

  return {
    id: b.id || `${b.key}@${b.version}`,
    baseKey: b.key,
    version: b.version,
    name: templateDisplayName(b.key),
    subject,
    body,
    textBody,
    lane: String(b.audience || "").startsWith("campaign") ? "campaign" : "transactional",
    audience: b.audience ?? null,
    placeholders,
  };
}

function templateDisplayName(key: string): string {
  const names: Record<string, string> = {
    account_setup: "Invitație înrolare",
    assignment_bundle: "Sarcini de completat",
    promo_past_report_2022_2025: "Promo clienți vechi - raport 2022-2025",
    promo_past_reactivation: "Promo clienți vechi - reactivare",
    promo_current_programs: "Promo clienți existenți - programe noi",
    promo_potential_intro: "Promo prospect - prima interacțiune",
    evaluation_leadership_invite: "Evaluare leadership - invitație",
    evaluation_leadership_reminder: "Evaluare leadership - reminder",
    evaluation_team_invite: "Evaluare echipe - invitație",
    evaluation_team_reminder: "Evaluare echipe - reminder",
  };
  return names[key] ?? key;
}

export function htmlToPlainText(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(
      /<a\b([^>]*?)href=(["'])(.*?)\2([^>]*)>([\s\S]*?)<\/a>/gi,
      (_match, _before: string, _quote: string, href: string, _after: string, label: string) => (
        label.includes(href) ? label : `${label} ${href}`
      ),
    )
    .replace(/<img\b[^>]*\balt=(["'])(.*?)\1[^>]*>/gi, "$2")
    .replace(/<\/td>\s*<td[^>]*>/gi, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|h[1-6]|li|tr|table|ul|ol)>/gi, "\n")
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#9654;/g, "▶")
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trim())
    .filter(Boolean)
    .join("\n");
}

function extractEmailVariables(...values: Array<string | undefined>): string[] {
  const variables = new Set<string>();
  const pattern = /(?:\$\{|\{)([a-zA-Z_][a-zA-Z0-9_]*)(?:\}|\})/g;
  for (const value of values) {
    if (!value) continue;
    for (const match of value.matchAll(pattern)) {
      variables.add(match[1]);
    }
  }
  return Array.from(variables);
}

function frontendToBackendTemplate(f: EmailTemplate) {
  const subject = (f.subject || "").replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}");
  const html_body = (f.body || "").replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}");
  const text_body = f.textBody?.trim()
    ? f.textBody.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}")
    : htmlToPlainText(html_body);
  const variables = extractEmailVariables(
    ...(f.placeholders || []),
    subject,
    html_body,
    text_body,
  );

  return {
    key: f.baseKey,
    subject,
    html_body,
    text_body,
    variables,
    audience: f.audience ?? f.lane,
    active: true,
  };
}

export async function listEmailTemplatesOnServer(includeRetired: boolean = false): Promise<EmailTemplate[]> {
  if (typeof window !== "undefined" && !process.env.VITEST && isDemoFallbackEnabled()) {
    return getSeededTemplates();
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/templates?include_retired=${includeRetired}`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isSeededDemoFallbackEnabled()) {
        return getSeededTemplates();
      }
      throw new Error(`Server returned status ${response.status}`);
    }
    const data = await response.json();
    return data.map(backendToFrontendTemplate);
  } catch (e) {
    if (isSeededDemoFallbackEnabled()) {
      return getSeededTemplates();
    }
    throw e;
  }
}

export async function getEmailTemplateOnServer(key: string, version?: number): Promise<EmailTemplate | null> {
  try {
    const url = version
      ? `${getApiBaseUrl()}/communications/templates/${key}?version=${version}`
      : `${getApiBaseUrl()}/communications/templates/${key}`;
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) return null;
    const data = await response.json();
    return backendToFrontendTemplate(data);
  } catch (e) {
    console.error("Error fetching email template", e);
    return null;
  }
}

export async function createEmailTemplateOnServer(template: EmailTemplate): Promise<EmailTemplate> {
  if (typeof window !== "undefined" && !process.env.VITEST && isDemoFallbackEnabled()) {
    return {
      ...template,
      placeholders: [...template.placeholders],
    };
  }

  const payload = frontendToBackendTemplate(template);
  const response = await fetch(`${getApiBaseUrl()}/communications/templates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (isDemoFallbackEnabled()) {
      return {
        ...template,
        placeholders: [...template.placeholders],
      };
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut crea șablonul pe server.");
  }
  const data = await response.json();
  return backendToFrontendTemplate(data);
}

export async function updateEmailTemplateOnServer(template: EmailTemplate): Promise<EmailTemplate> {
  if (typeof window !== "undefined" && !process.env.VITEST && isDemoFallbackEnabled()) {
    return {
      ...template,
      placeholders: [...template.placeholders],
    };
  }

  const payload = frontendToBackendTemplate(template);
  const response = await fetch(`${getApiBaseUrl()}/communications/templates/${template.baseKey}?version=${template.version}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (isDemoFallbackEnabled()) {
      return {
        ...template,
        placeholders: [...template.placeholders],
      };
    }
    if (response.status === 401) {
      throw new Error("Nu sunteți autentificat. Vă rugăm să vă reconectați.");
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut actualiza șablonul pe server.");
  }
  const data = await response.json();
  return backendToFrontendTemplate(data);
}

export async function activateEmailTemplateOnServer(key: string, version: number): Promise<EmailTemplate> {
  const response = await fetch(`${getApiBaseUrl()}/communications/templates/${key}/versions/${version}/activate`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    if (response.status === 401) {
      if (isDemoFallbackEnabled()) {
        return {
          id: `${key}@${version}`,
          baseKey: key,
          version,
          name: key,
          subject: "",
          body: "",
          lane: "transactional",
          placeholders: [],
        };
      }
      throw new Error("Nu sunteți autentificat. Vă rugăm să vă reconectați.");
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut activa versiunea șablonului.");
  }
  const data = await response.json();
  return backendToFrontendTemplate(data);
}

export async function deleteEmailTemplateOnServer(key: string, version?: number): Promise<EmailTemplate | null> {
  const url = version
    ? `${getApiBaseUrl()}/communications/templates/${key}?version=${version}`
    : `${getApiBaseUrl()}/communications/templates/${key}`;
  const response = await fetch(url, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    if (response.status === 401) {
      if (isDemoFallbackEnabled()) return null;
      throw new Error("Nu sunteți autentificat. Vă rugăm să vă reconectați.");
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut pensiona șablonul.");
  }
  const text = await response.text();
  if (!text) return null;
  const data = JSON.parse(text);
  return backendToFrontendTemplate(data);
}

export type EmailDeliveryMetric = {
  label: string;
  value: string;
  detail: string;
};

export type AssessmentDeliveryRow = {
  id: string;
  company_id: string;
  participant: string;
  email: string;
  audience: "leadership_account" | "secure_link";
  project: string;
  tasks: string;
  delivery: "draft" | "sent" | "delivered" | "opened" | "failed";
  reminder: "today" | "tomorrow" | "paused" | "none";
  completion: "not_started" | "in_progress" | "completed";
  nextAction: string;
};

export type EmailOpsSummary = {
  metrics: EmailDeliveryMetric[];
  assessmentRows: AssessmentDeliveryRow[];
  rules: string[];
  campaign: CampaignOpsSummary;
};

export type CampaignRecipientRow = {
  id: string;
  company: string;
  firstName?: string;
  lastName?: string;
  email: string;
  clientType: "tip_1" | "tip_2" | "tip_3" | "tip_4";
  status: "ready" | "needs_contact_name" | "suppressed" | "unsubscribed" | "sent";
  openRate?: string;
  clickRate?: string;
  viewRate?: string;
  openCount?: number;
  clickCount?: number;
  viewCount?: number;
  replyCount?: number;
  calendlyClickCount?: number;
  emailVariant?: string | null;
  outcome?: "intalnire" | "ofertare" | "contract";
};

export type CampaignOpsSummary = {
  videoHost: {
    provider: string;
    status: "ready" | "needs_upload";
    note: string;
  };
  template: {
    subject: string;
    personalization: string;
    ctaPrimary: string;
    ctaSecondary: string;
  };
  recipients: CampaignRecipientRow[];
  weeklyReport: {
    cadence: string;
    metrics: string[];
    notification: string;
  };
};

export async function listEmailSurfaceStubs(): Promise<EmailSurfaceStub[]> {
  return [
    { id: "assessment-invites", name: "Invitații assessment", lane: "transactional" },
    { id: "assessment-reminders", name: "Remindere assessment", lane: "transactional" },
    { id: "video-campaigns", name: "Campanii cu link video", lane: "campaign" },
  ];
}

export async function getEmailOpsSummary(options: ApiRequestOptions = {}): Promise<EmailOpsSummary> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/ops-summary`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (!response.ok) {
      throw new Error(`Server returned status ${response.status}`);
    }
    return await response.json();
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return {
      metrics: [],
      assessmentRows: [],
      rules: [],
      campaign: {
        videoHost: {
          provider: "Vimeo sau pagină Codruț",
          status: "ready",
          note: "Emailul trimite thumbnail și CTA către linkul video. Pagina Codruț este opțională pentru tracking sau CTA-uri dedicate.",
        },
        template: {
          subject: "O idee practică pentru echipa ta, ${first_name}",
          personalization: "Prenumele se completează automat când există nume în bază.",
          ctaPrimary: "Programează o discuție",
          ctaSecondary: "Vreau să fiu contactat",
        },
        recipients: [
          {
            id: "campaign-atlas-ceo",
            company: "Atlas Mobility",
            firstName: "Radu",
            lastName: "Munteanu",
            email: "radu.munteanu@atlas-mobility.ro",
            clientType: "tip_1",
            status: "sent",
            openCount: 3,
            clickCount: 2,
            viewCount: 1,
            replyCount: 1,
            calendlyClickCount: 1,
            emailVariant: "variant_a",
            outcome: "intalnire",
          },
          {
            id: "campaign-meridian-director",
            company: "Clinica Meridian",
            firstName: "Diana",
            lastName: "Ene",
            email: "diana.ene@clinica-meridian.ro",
            clientType: "tip_1",
            status: "ready",
            openCount: 1,
            clickCount: 1,
            viewCount: 1,
            replyCount: 0,
            calendlyClickCount: 0,
            emailVariant: "variant_b",
          },
          {
            id: "campaign-nova-retail",
            company: "Nova Retail Group",
            firstName: "Cristina",
            lastName: "Olaru",
            email: "cristina.olaru@nova-retail.ro",
            clientType: "tip_2",
            status: "needs_contact_name",
            openCount: 0,
            clickCount: 0,
            viewCount: 0,
            replyCount: 0,
            calendlyClickCount: 0,
            emailVariant: "variant_a",
          },
          {
            id: "campaign-suppressed",
            company: "Fabrica Nord",
            email: "office@fabricanord.ro",
            clientType: "tip_2",
            status: "suppressed",
            openCount: 0,
            clickCount: 0,
            viewCount: 0,
            replyCount: 0,
            calendlyClickCount: 0,
            emailVariant: "variant_c",
          },
        ],
        weeklyReport: {
          cadence: "Săptămânal",
          metrics: ["deschideri", "clickuri", "vizualizări video", "reply-uri", "clickuri Calendly", "variantă email"],
          notification: "Andrei primește email/Telegram cu link către raport.",
        },
      },
    };
  }
}

export type CampaignRecipientCreate = {
  email?: string;
  contact_name?: string;
  organization_name?: string;
  segment: "past_customer" | "potential_customer";
  status?: "active" | "suppressed";
  source?: string;
};

export type CampaignRecipientBulkCreateResponse = {
  status: "success";
  count: number;
  created?: number;
  updated?: number;
};

export type CampaignRecipientUpdate = Omit<Partial<CampaignRecipientCreate>, "status"> & {
  status?: "active" | "suppressed" | "unsubscribed";
};

export async function bulkCreateCampaignRecipientsOnServer(
  recipients: CampaignRecipientCreate[],
): Promise<CampaignRecipientBulkCreateResponse> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/recipients/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipients }),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return { status: "success", count: recipients.length, created: recipients.length, updated: 0 };
      }
      throw new Error(`Failed to upload recipients: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return { status: "success", count: recipients.length, created: recipients.length, updated: 0 };
    }
    throw err;
  }
}

export async function updateCampaignRecipientOnServer(
  recipientId: string,
  recipient: CampaignRecipientUpdate,
) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/recipients/${recipientId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(recipient),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return { id: recipientId, ...recipient };
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut actualiza contactul (${response.status}).`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) return { id: recipientId, ...recipient };
    throw err;
  }
}

export async function deleteCampaignRecipientOnServer(recipientId: string): Promise<void> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/recipients/${recipientId}`, {
      method: "DELETE",
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return;
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut șterge contactul (${response.status}).`);
    }
  } catch (err) {
    if (isDemoFallbackEnabled()) return;
    throw err;
  }
}

export type CampaignCreate = {
  name: string;
  segment: "past_customer" | "potential_customer";
  subject: string;
  html_body: string;
  text_body: string;
  video_url?: string;
  thumbnail_url?: string;
  landing_page_url?: string;
};

export type CampaignUpdate = Omit<Partial<CampaignCreate>, "video_url" | "thumbnail_url" | "landing_page_url"> & {
  status?: "draft" | "ready" | "paused" | "completed";
  video_url?: string | null;
  thumbnail_url?: string | null;
  landing_page_url?: string | null;
};

export type CampaignAssetUpload = {
  url: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
};

export async function uploadCampaignAssetOnServer(file: File): Promise<CampaignAssetUpload> {
  const response = await fetch(`${getApiBaseUrl()}/communications/campaign-assets`, {
    method: "POST",
    headers: {
      "Content-Type": file.type || "application/octet-stream",
      "X-File-Name": encodeURIComponent(file.name || "thumbnail"),
    },
    body: file,
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Thumbnailul nu a putut fi încărcat.");
  }
  return await response.json();
}

export type CampaignVideoDraft = {
  name: string;
  segment: "past_customer" | "potential_customer";
  subject: string;
  htmlBody?: string;
  textBody?: string;
  videoUrl?: string;
  thumbnailUrl?: string;
  landingUrl?: string;
};

function normalizeHttpUrl(value: string | undefined): string | null {
  if (!value?.trim()) return null;
  try {
    const url = new URL(value.trim());
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    return url.toString();
  } catch {
    return null;
  }
}

function escapeHtmlAttribute(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

export function buildVideoCampaignCreatePayload(draft: CampaignVideoDraft): CampaignCreate | null {
  const trimmedName = draft.name.trim();
  const hasVideoFields = Boolean(draft.videoUrl?.trim() || draft.thumbnailUrl?.trim());
  const videoUrl = normalizeHttpUrl(draft.videoUrl);
  const thumbnailUrl = normalizeHttpUrl(draft.thumbnailUrl);
  const landingUrl = normalizeHttpUrl(draft.landingUrl) ?? videoUrl;

  if (!trimmedName) return null;
  if (hasVideoFields && (!videoUrl || !thumbnailUrl || !landingUrl)) return null;

  const safeLandingUrl = landingUrl ? escapeHtmlAttribute(landingUrl) : "";
  const safeThumbnailUrl = thumbnailUrl ? escapeHtmlAttribute(thumbnailUrl) : "";
  const htmlBody = draft.htmlBody?.trim()
    ? draft.htmlBody
        .replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}")
        .replace(/\$\{landing_page_url\}/g, safeLandingUrl)
        .replace(/\$\{thumbnail_url\}/g, safeThumbnailUrl)
    : hasVideoFields
      ? [
        "<p>Bună, ${first_name}.</p>",
        "<p>Am pregătit un material video scurt pentru contextul echipei tale.</p>",
        [
          `<p><a href="${safeLandingUrl}" style="display:block;text-decoration:none;color:inherit;">`,
          `<span style="display:block;position:relative;max-width:420px;border-radius:14px;overflow:hidden;background:#2b211f;">`,
          `<img src="${safeThumbnailUrl}" alt="Previzualizare video" style="display:block;width:100%;max-width:420px;height:auto;border:0;border-radius:14px;" />`,
          `<span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:64px;height:64px;border-radius:999px;background:rgba(255,255,255,.9);box-shadow:0 14px 35px rgba(0,0,0,.22);text-align:center;line-height:64px;color:#890505;font-size:28px;font-weight:700;">&#9654;</span>`,
          "</span>",
          "</a></p>",
        ].join(""),
      ].join("")
      : "<p>Bună, ${first_name}.</p><p>Dacă vrei, alege un slot în Calendly și stabilim o conversație.</p>";
  const textBody = draft.textBody?.trim()
    ? draft.textBody.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}")
    : hasVideoFields
      ? `Bună, \${first_name}. Vezi video-ul aici: ${landingUrl}`
      : "Bună, ${first_name}. Dacă vrei, alege un slot în Calendly și stabilim o conversație.";

  return {
    name: trimmedName,
    segment: draft.segment,
    subject: draft.subject.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}"),
    html_body: htmlBody,
    text_body: textBody,
    video_url: videoUrl ?? undefined,
    thumbnail_url: thumbnailUrl ?? undefined,
    landing_page_url: landingUrl && landingUrl !== videoUrl ? landingUrl : undefined,
  };
}

export type EmailCampaign = CampaignCreate & {
  id: string;
  status: "draft" | "ready" | "paused" | "completed";
};

const SEEDED_CAMPAIGNS: EmailCampaign[] = [
  {
    id: "demo-campaign-reconnectare",
    name: "Reconectare clienți 2022-2025",
    segment: "past_customer",
    status: "ready",
    subject: "Raportul de activitate pe care nu l-a cerut nimeni",
    html_body: SEEDED_TEMPLATES.find((template) => template.baseKey === "promo_past_report_2022_2025")?.body ?? "",
    text_body: "Raportul de activitate pe care nu l-a cerut nimeni. Aici ai calendarul meu: ${calendly_url}",
    video_url: "https://vimeo.com/123456789",
    thumbnail_url: "https://codrut.andreivacaru.ro/api/campaign-assets/reconectare-demo.jpg",
    landing_page_url: "https://codrut.andreivacaru.ro/campanii/reconectare",
  },
  {
    id: "demo-campaign-prospecti",
    name: "Prospecți leadership operațional",
    segment: "potential_customer",
    status: "draft",
    subject: "Asta e un spam, dar e un spam bun.",
    html_body: SEEDED_TEMPLATES.find((template) => template.baseKey === "promo_potential_intro")?.body ?? "",
    text_body: "Salut, ${first_name}. Alege un slot: ${calendly_url}",
    video_url: "https://vimeo.com/987654321",
    thumbnail_url: "https://codrut.andreivacaru.ro/api/campaign-assets/prospect-demo.gif",
  },
];

function getSeededCampaigns(): EmailCampaign[] {
  return SEEDED_CAMPAIGNS.map((campaign) => ({ ...campaign }));
}

export type CampaignSendRecipientResult = {
  recipient_id: string;
  email: string;
  status: "accepted" | "failed" | "skipped" | "dry_run" | string;
  message_id?: string | null;
  error?: string | null;
};

export type CampaignSendResponse = {
  campaign_id: string;
  total: number;
  sent: number;
  failed: number;
  skipped: number;
  dry_run: boolean;
  results: CampaignSendRecipientResult[];
};

export async function createCampaignOnServer(campaign: CampaignCreate) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(campaign),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return { id: "campaign_" + Date.now(), ...campaign };
      }
      throw new Error(`Failed to create campaign: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return { id: "campaign_" + Date.now(), ...campaign };
    }
    throw err;
  }
}

export async function updateCampaignOnServer(campaignId: string, campaign: CampaignUpdate): Promise<EmailCampaign> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(campaign),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return { id: campaignId, name: "", segment: "potential_customer", subject: "", html_body: "", text_body: "", status: "ready", ...campaign } as EmailCampaign;
      }
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut actualiza campania (${response.status}).`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return { id: campaignId, name: "", segment: "potential_customer", subject: "", html_body: "", text_body: "", status: "ready", ...campaign } as EmailCampaign;
    }
    throw err;
  }
}

export async function listCampaignsOnServer(): Promise<EmailCampaign[]> {
  if (typeof window !== "undefined" && isDemoFallbackEnabled()) {
    return getSeededCampaigns();
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return getSeededCampaigns();
      throw new Error(`Failed to fetch campaigns: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) return getSeededCampaigns();
    throw err;
  }
}

export async function deleteCampaignOnServer(campaignId: string): Promise<void> {
  if (typeof window !== "undefined" && isDemoFallbackEnabled()) {
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}`, {
      method: "DELETE",
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return;
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut șterge campania (${response.status}).`);
    }
  } catch (err) {
    if (isDemoFallbackEnabled()) return;
    throw err;
  }
}

export async function sendCampaignOnServer(
  campaignId: string,
  options: { dryRun?: boolean; recipientIds?: string[]; mode?: "new" | "selected" | "all" } = {},
): Promise<CampaignSendResponse> {
  if (typeof window !== "undefined" && isDemoFallbackEnabled()) {
    return {
      campaign_id: campaignId,
      total: 0,
      sent: 0,
      failed: 0,
      skipped: 0,
      dry_run: Boolean(options.dryRun),
      results: [],
    };
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      credentials: "include",
      body: JSON.stringify({
        dry_run: Boolean(options.dryRun),
        recipient_ids: options.recipientIds,
        mode: options.mode ?? (options.recipientIds?.length ? "selected" : "new"),
      }),
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return {
          campaign_id: campaignId,
          total: 0,
          sent: 0,
          failed: 0,
          skipped: 0,
          dry_run: Boolean(options.dryRun),
          results: [],
        };
      }
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut trimite campania (${response.status}).`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return {
        campaign_id: campaignId,
        total: 0,
        sent: 0,
        failed: 0,
        skipped: 0,
        dry_run: Boolean(options.dryRun),
        results: [],
      };
    }
    throw err;
  }
}
