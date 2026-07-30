import type { Metadata } from "next";

import { LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "Confidențialitate | Cody" };

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Politica de confidențialitate"
      updatedAt="30 iulie 2026"
      introduction={<p>Cody prelucrează datele necesare administrării programelor de training, accesului participanților și raportării către persoanele autorizate.</p>}
      sections={[
        {
          title: "Date prelucrate",
          content: <p>Putem prelucra numele, datele de contact profesionale, compania, proiectele, rolurile, invitațiile, răspunsurile la chestionare, rezultatele calculate și istoricul tehnic necesar securității.</p>,
        },
        {
          title: "Scop și acces",
          content: <><p>Datele sunt folosite pentru furnizarea platformei, trimiterea invitațiilor, completarea evaluărilor, generarea rapoartelor și protejarea conturilor.</p><p>Accesul este limitat în funcție de rol, companie și proiect. Răspunsurile individuale nu sunt afișate în afara regulilor de vizibilitate configurate pentru evaluare.</p></>,
        },
        {
          title: "Păstrare și furnizori",
          content: <><p>Datele sunt păstrate cât timp sunt necesare proiectului, obligațiilor contractuale și securității. Furnizorii tehnici primesc doar accesul necesar operării serviciului și sunt supuși obligațiilor de confidențialitate.</p><p>Când un contact de campanie este arhivat, acesta nu mai apare în listele sau campaniile active și nu mai poate fi folosit pentru trimiteri. Contactul poate fi restaurat din Arhivă. Ștergerea automată a datelor directe nu este încă activă; va fi pornită prin următoarea actualizare de confidențialitate. Până atunci, contactul rămâne păstrat în siguranță în Arhivă.</p><p>După activarea procesului și ștergerea datelor directe vor putea rămâne numai marcaje codificate, create cu o cheie secretă, pornind de la adresa de email, linkul de dezabonare sau confirmările furnizorului de email. Ele ne vor ajuta să respectăm dezabonarea, să nu retrimitem către o adresă respinsă și să procesăm confirmări întârziate fără a readuce datele șterse. Aceste marcaje vor rămâne date pseudonimizate protejate, nu date anonime.</p><p>Fiecare marcaj păstrat va avea o dată de revizuire în cel mult 12 luni. Marcajele folosite doar pentru confirmări întârziate vor fi șterse la această revizuire. Cele necesare pentru o respingere permanentă sau o dezabonare vor fi revizuite cel puțin anual și păstrate numai cât timp sunt necesare pentru a împiedica o nouă trimitere nedorită.</p></>,
        },
        {
          title: "Drepturile tale",
          content: <p>Pentru acces, corectare, ștergere, restricționare, portabilitate, opoziție sau o întrebare despre datele păstrate, inclusiv marcajele folosite pentru a preveni retrimiterea, scrie la <a className="font-semibold text-primary hover:underline" href="mailto:andrei@andreivacaru.ro">andrei@andreivacaru.ro</a>. Unele cereri pot fi limitate de obligații contractuale sau legale; îți vom explica motivul dacă se aplică o astfel de limită.</p>,
        },
      ]}
    />
  );
}
