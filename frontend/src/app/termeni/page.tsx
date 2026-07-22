import type { Metadata } from "next";

import { LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "Termeni | Cody" };

export default function TermsPage() {
  return (
    <LegalPage
      title="Termeni de utilizare"
      updatedAt="16 iulie 2026"
      introduction={<p>Folosirea Cody presupune respectarea rolului și a proiectelor pentru care ai primit acces.</p>}
      sections={[
        {
          title: "Cont și acces",
          content: <p>Păstrează datele de autentificare confidențiale și folosește numai contul sau invitația alocate. Accesul poate fi suspendat când există indicii de utilizare neautorizată sau când proiectul s-a încheiat.</p>,
        },
        {
          title: "Utilizare permisă",
          content: <p>Nu încerca să accesezi alte companii, proiecte, participanți sau rezultate și nu folosi platforma pentru conținut ilegal, abuziv ori care încalcă drepturile altor persoane.</p>,
        },
        {
          title: "Serviciu și rezultate",
          content: <p>Cody sprijină administrarea și interpretarea programelor de training. Rapoartele nu înlocuiesc evaluarea profesională, medicală, juridică sau psihologică.</p>,
        },
        {
          title: "Contact",
          content: <p>Pentru probleme de acces, securitate sau utilizare, scrie la <a className="font-semibold text-primary hover:underline" href="mailto:andrei@andreivacaru.ro">andrei@andreivacaru.ro</a>.</p>,
        },
      ]}
    />
  );
}
