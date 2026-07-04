import Link from "next/link";
import { notFound } from "next/navigation";

import { isSeededDemoFallbackEnabled } from "@/api/runtime";
import { BrandMark } from "@/components/brand/brand-mark";

const routeGroups = [
  {
    title: "Rute trainer",
    routes: [
      ["/trainer", "Acasă livrare"],
      ["/trainer/companies", "Companii"],
      ["/trainer/projects", "Proiecte"],
      ["/trainer/questionnaires", "Chestionare"],
      ["/trainer/email", "Email"],
      ["/trainer/login", "Autentificare trainer"],
    ],
  },
  {
    title: "Rute participant și invitații",
    routes: [
      ["/invite/demo-token", "Invitație securizată validă"],
      ["/invite/expired-demo", "Invitație securizată expirată"],
      ["/participant", "Workspace sarcini"],
      ["/participant/dashboard", "Acasă participant"],
      ["/participant/questionnaires", "Chestionare"],
      ["/participant/chat", "Chat"],
      ["/participant/onboarding", "Onboarding"],
      ["/participant/final-evaluation", "Finalizare participant"],
      ["/participant/account", "Cont"],
    ],
  },

  {
    title: "Rute autentificare",
    routes: [
      ["/login", "Login"],
      ["/register", "Înregistrare"],
      ["/reset-password", "Resetare parolă"],
      ["/update-password", "Actualizare parolă"],
    ],
  },
];

export default function DevRoutesPage() {
  if (!isSeededDemoFallbackEnabled()) {
    notFound();
  }

  return (
    <main className="app-min-height bg-background px-4 py-10 text-foreground md:px-6">
      <section className="mx-auto max-w-6xl">
        <Link href="/" className="inline-flex">
          <BrandMark subtitle="Index rute prototip" />
        </Link>
        <div className="mt-10 max-w-3xl">
          <p className="text-sm font-bold uppercase tracking-[0.16em] text-burgundy">Acces dev</p>
          <h1 className="mt-2 font-display text-4xl font-semibold text-foreground md:text-5xl">
            Rute prototip
          </h1>
          <p className="mt-3 text-base leading-7 text-foreground/65">
            Index intern pentru verificare rapidă, în timp ce landing page-ul public rămâne orientat către business.
          </p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {routeGroups.map((group) => (
            <section key={group.title} className="surface-panel p-5">
              <h2 className="text-base font-bold text-foreground">{group.title}</h2>
              <div className="mt-4 grid gap-2">
                {group.routes.map(([href, label]) => (
                  <Link
                    key={href}
                    href={href}
                    className="tap-soft rounded-full border border-[var(--border)] bg-surface-muted px-3 py-2 text-sm font-semibold text-foreground/75 hover:border-burgundy/50 hover:text-burgundy"
                  >
                    {label}
                    <span className="mt-1 block font-mono text-xs font-normal text-foreground/45">{href}</span>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      </section>
    </main>
  );
}
