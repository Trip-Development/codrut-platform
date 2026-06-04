import Link from "next/link";

import { BrandMark } from "@/components/brand/brand-mark";

const routeGroups = [
  {
    title: "Trainer routes",
    routes: [
      ["/trainer", "Delivery dashboard"],
      ["/trainer/projects", "Projects"],
      ["/trainer/projects/demo-project", "Project detail"],
      ["/trainer/projects/demo-project/participants/demo-participant", "Participant report"],
      ["/trainer/org-chart", "Org chart"],
      ["/trainer/participants", "Participants"],
      ["/trainer/questionnaires", "Questionnaires"],
      ["/trainer/email", "Email"],
      ["/trainer/reports", "Reports"],
      ["/trainer/login", "Trainer login"],
    ],
  },
  {
    title: "Participant and invite routes",
    routes: [
      ["/invite/demo-token", "Valid secure invite"],
      ["/invite/expired-demo", "Expired secure invite"],
      ["/participant", "Task workspace"],
      ["/participant/dashboard", "Dashboard"],
      ["/participant/questionnaires", "Questionnaires"],
      ["/participant/chat", "Chat"],
      ["/participant/onboarding", "Onboarding"],
      ["/participant/final-evaluation", "Final evaluation"],
      ["/participant/account", "Account"],
    ],
  },
  {
    title: "Recovered compatibility routes",
    routes: [
      ["/admin", "Old admin"],
      ["/admin/projects/demo-project", "Old project detail"],
      ["/admin/projects/demo-project/participant/demo-participant", "Old participant report"],
      ["/dashboard", "Old participant dashboard"],
      ["/chat", "Old chat"],
      ["/onboarding", "Old onboarding"],
      ["/test-out", "Old final evaluation"],
    ],
  },
  {
    title: "Auth routes",
    routes: [
      ["/login", "Login"],
      ["/register", "Register"],
      ["/reset-password", "Reset password"],
      ["/update-password", "Update password"],
    ],
  },
];

export default function DevRoutesPage() {
  return (
    <main className="app-min-height bg-background px-4 py-10 text-foreground md:px-6">
      <section className="mx-auto max-w-6xl">
        <Link href="/" className="inline-flex">
          <BrandMark subtitle="Prototype route index" />
        </Link>
        <div className="mt-10 max-w-3xl">
          <p className="text-sm font-bold uppercase tracking-[0.16em] text-burgundy">Dev access</p>
          <h1 className="mt-2 font-display text-4xl font-semibold text-foreground md:text-5xl">
            Prototype routes
          </h1>
          <p className="mt-3 text-base leading-7 text-foreground/65">
            Internal route index for fast review while the public landing remains business-facing.
          </p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {routeGroups.map((group) => (
            <section key={group.title} className="rounded-3xl border border-[var(--border)] bg-surface p-5 shadow-sm">
              <h2 className="text-base font-bold text-foreground">{group.title}</h2>
              <div className="mt-4 grid gap-2">
                {group.routes.map(([href, label]) => (
                  <Link
                    key={href}
                    href={href}
                    className="tap-soft rounded-2xl border border-[var(--border)] bg-surface-muted px-3 py-2 text-sm font-semibold text-foreground/75 hover:border-burgundy/50 hover:text-burgundy"
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
