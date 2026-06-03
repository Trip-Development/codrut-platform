import Link from "next/link";

const routeGroups = [
  {
    title: "Trainer new routes",
    routes: [
      ["/trainer", "Trainer dashboard"],
      ["/trainer/projects", "Projects"],
      ["/trainer/projects/demo-project", "Project detail"],
      ["/trainer/projects/demo-project/participants/demo-participant", "Participant report"],
      ["/trainer/org-chart", "Org chart"],
      ["/trainer/participants", "Participants"],
      ["/trainer/questionnaires", "Questionnaires"],
      ["/trainer/email", "Email"],
      ["/trainer/reports", "Reports"],
    ],
  },
  {
    title: "Participant new routes",
    routes: [
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
    title: "Old prototype routes",
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

export default function HomePage() {
  return (
    <main className="app-min-height bg-vines-pattern bg-background px-4 py-10 text-foreground md:px-6">
      <section className="mx-auto flex min-h-[calc(100dvh-5rem)] max-w-5xl flex-col justify-center">
        <div className="max-w-2xl">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-burgundy text-2xl font-bold text-white shadow-sm">
              C
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-burgundy">
                Codrut Platform
              </p>
              <p className="text-sm text-foreground/55">Training, assessment, and rollout management</p>
            </div>
          </div>

          <h1 className="font-display text-4xl font-semibold tracking-tight md:text-6xl">
            Shell-ul Codrut este pregatit pentru migrare.
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-foreground/70">
            Interfata veche se muta intai ca experienta vizuala completa. Datele reale vor intra
            treptat prin API-ul FastAPI, fara Supabase sau rutare veche de prototip.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/trainer"
              className="tap-soft rounded-xl bg-burgundy px-5 py-3 text-center text-sm font-bold text-white shadow-sm hover:bg-burgundy-700"
            >
              Trainer dashboard
            </Link>
            <Link
              href="/participant"
              className="tap-soft rounded-xl border border-burgundy bg-surface px-5 py-3 text-center text-sm font-bold text-burgundy hover:bg-burgundy-50"
            >
              Participant workspace
            </Link>
          </div>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-2">
          {routeGroups.map((group) => (
            <section key={group.title} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
              <h2 className="text-base font-bold text-foreground">{group.title}</h2>
              <div className="mt-4 grid gap-2">
                {group.routes.map(([href, label]) => (
                  <Link
                    key={href}
                    href={href}
                    className="tap-soft rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-2 text-sm font-semibold text-foreground/75 hover:border-burgundy/50 hover:text-burgundy"
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
