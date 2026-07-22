import type { Metadata } from "next";

import { LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "Cookies | Cody" };

export default function CookiesPage() {
  return (
    <LegalPage
      title="Politica privind cookies"
      updatedAt="16 iulie 2026"
      introduction={<p>Cody nu folosește în prezent cookies de publicitate sau analiză. Sunt folosite numai mecanismele necesare autentificării și securității.</p>}
      sections={[
        {
          title: "Cookies necesare",
          content: <><p><strong className="text-foreground">codrut_session</strong> menține sesiunea autentificată și nu este accesibil din JavaScript.</p><p><strong className="text-foreground">codrut_csrf</strong> protejează operațiunile autentificate împotriva cererilor trimise din alte site-uri.</p><p>Aceste cookies pot fi păstrate până la 90 de zile și sunt șterse la deconectare.</p></>,
        },
        {
          title: "Preferințe locale",
          content: <p>Tema și starea meniului lateral sunt păstrate local în browser. Aceste preferințe nu sunt folosite pentru urmărire și nu sunt trimise unor terți.</p>,
        },
        {
          title: "Schimbări viitoare",
          content: <p>Dacă vor fi introduse instrumente de analiză sau alte tehnologii neesențiale, această pagină și mecanismul de alegere vor fi actualizate înainte de activarea lor.</p>,
        },
      ]}
    />
  );
}
