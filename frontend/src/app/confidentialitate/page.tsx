import type { Metadata } from "next";

import { LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "Confidențialitate | Cody" };

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Politica de confidențialitate"
      updatedAt="16 iulie 2026"
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
          content: <p>Datele sunt păstrate cât timp sunt necesare proiectului, obligațiilor contractuale și securității. Furnizorii tehnici primesc doar accesul necesar operării serviciului și sunt supuși obligațiilor de confidențialitate.</p>,
        },
        {
          title: "Drepturile tale",
          content: <p>Pentru acces, corectare, ștergere, restricționare, portabilitate sau o întrebare despre prelucrare, scrie la <a className="font-semibold text-primary hover:underline" href="mailto:andrei@andreivacaru.ro">andrei@andreivacaru.ro</a>. Unele cereri pot fi limitate de obligații contractuale sau legale.</p>,
        },
      ]}
    />
  );
}
