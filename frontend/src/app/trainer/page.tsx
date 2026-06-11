import Link from "next/link";

import { audienceAccessNote } from "@/api/auth";
import { getTrainerSession } from "@/api/auth-server";
import { getServerApiRequestOptions } from "@/api/server-request";
import { getTrainerDashboardSummary, type TrainerAction, type TrainerCompanyRow } from "@/api/trainer";
import { StatCard } from "@/components/presentation/stat-card";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerDashboardPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [trainer, summary] = await Promise.all([
    getTrainerSession(),
    getTrainerDashboardSummary(requestOptions),
  ]);

  return (
    <AppShell
      audience="trainer"
      eyebrow="Trainer"
      title="Panou pentru rollout și monitorizare"
      description="Suprafață de lucru pentru companii, participanți, organigramă, chestionare, invitații email și progres operațional."
      navItems={trainerNavItems}
      activeHref="/trainer"
      userLabel={trainer.user.name}
      session={trainer}
      accessNote={audienceAccessNote("trainer")}
    >
      <TrainerWorkspaceBar />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summary.stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <DeliveryTable companies={summary.activeCompanies} />
        <aside className="space-y-4">
          <VisibilityPanel
            trainerRawAccess={summary.visibility.trainerRawAccess}
            managerView={summary.visibility.managerView}
            note={summary.visibility.note}
          />
          <NextActions actions={summary.actions} />
        </aside>
      </div>
    </AppShell>
  );
}

function TrainerWorkspaceBar() {
  const shortcuts = [
    {
      label: "Companii",
      step: "01",
      detail: "Adaugă clientul și gestionează workspace-ul complet.",
      href: "/trainer/companies",
    },
    {
      label: "Chestionare",
      step: "02",
      detail: "Editează întrebări, scale și versiuni.",
      href: "/trainer/questionnaires",
    },
    {
      label: "Șabloane email",
      step: "03",
      detail: "Ajustează textele reutilizabile. Trimiterea se face din companie.",
      href: "/trainer/email",
    },
    {
      label: "Rapoarte",
      step: "04",
      detail: "Vezi rezultate agregate și scoruri.",
      href: "/trainer/reports",
    },
  ];

  return (
    <section className="mb-5 rounded-2xl border border-[var(--border)] bg-surface p-4 shadow-sm">
      <div className="grid gap-5 xl:grid-cols-[minmax(18rem,1fr)_minmax(32rem,44rem)] xl:items-center">
        <div className="min-w-0 max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Flux companie</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Pornește din workspace-ul clientului</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/62">
            Alege compania, apoi lucrează pe proiecte, roster, echipe, invitații și rapoarte în același context. Paginile globale rămân pentru configurări reutilizabile.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          {shortcuts.map((shortcut) => (
            <Link
              key={shortcut.href}
              href={shortcut.href}
              className="tap-soft group flex min-h-24 flex-col justify-between rounded-xl border border-[var(--border)] bg-background px-3 py-3 transition hover:border-burgundy/45 hover:bg-surface-muted hover:shadow-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-bold leading-5 text-foreground group-hover:text-burgundy">{shortcut.label}</p>
                <span className="rounded-full bg-surface-muted px-2 py-0.5 text-[11px] font-bold text-foreground/45 group-hover:bg-burgundy-50 group-hover:text-burgundy dark:group-hover:bg-burgundy/10">
                  {shortcut.step}
                </span>
              </div>
              <p className="mt-1 hidden text-xs leading-5 text-foreground/52 sm:block">{shortcut.detail}</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

function DeliveryTable({ companies }: { companies: TrainerCompanyRow[] }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
      <div className="border-b border-[var(--border)] px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Livrare</p>
        <h2 className="mt-1 text-xl font-semibold text-foreground">Companii active</h2>
        <p className="mt-2 text-sm leading-6 text-foreground/62">
          Primul ecran pentru trainer: unde este blocajul, cine trebuie urmărit și ce merge mai departe.
        </p>
      </div>
      <div className="divide-y divide-[var(--border)]">
        {companies.length === 0 ? (
          <p className="px-5 py-6 text-sm font-semibold text-foreground/58">
            Nu există companii active încă. Adaugă prima companie ca să pornești rosterul și invitațiile.
          </p>
        ) : (
          companies.map((company) => (
            <CompanyRow key={company.id} company={company} />
          ))
        )}
      </div>
    </section>
  );
}

function CompanyRow({ company }: { company: TrainerCompanyRow }) {
  const completion = company.total > 0 ? Math.round((company.completed / company.total) * 100) : 0;

  return (
    <article className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_13rem] lg:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-foreground">{company.company}</h3>
          <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55">
            {companyStageLabel(company.stage)}
          </span>
        </div>
        <p className="mt-2 text-sm leading-6 text-foreground/62">{company.nextAction}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {company.blockers.length > 0 ? (
            company.blockers.map((blocker) => (
              <span key={blocker} className="rounded-full bg-burgundy-50 dark:bg-burgundy/10 px-2.5 py-1 text-xs font-semibold text-burgundy">
                {blocker}
              </span>
            ))
          ) : (
            <span className="rounded-full bg-success/35 px-2.5 py-1 text-xs font-semibold text-success-ink">
              Fără blocaje
            </span>
          )}
        </div>
      </div>
      <div>
        <div className="flex items-center justify-between text-sm font-semibold text-foreground/62">
          <span>{company.completed}/{company.total}</span>
          <span>{completion}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-muted">
          <div className="h-full rounded-full bg-burgundy" style={{ width: `${completion}%` }} />
        </div>
        <Link
          href={`/trainer/companies/${company.id}`}
          className="tap-soft mt-3 inline-flex w-full justify-center rounded-xl bg-foreground px-4 py-2.5 text-sm font-semibold text-background hover:bg-burgundy hover:text-white"
        >
          Deschide compania
        </Link>
      </div>
    </article>
  );
}

function companyStageLabel(stage: TrainerCompanyRow["stage"]): string {
  const labels: Record<TrainerCompanyRow["stage"], string> = {
    setup: "Configurare",
    invites: "Invitații",
    completion: "Completare",
    reporting: "Raportare",
  };
  return labels[stage];
}

function VisibilityPanel({
  trainerRawAccess,
  managerView,
  note,
}: {
  trainerRawAccess: boolean;
  managerView: "aggregate_only" | "locked";
  note: string;
}) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Vizibilitate raportare</p>
      <div className="mt-4 grid gap-2">
        <StatusLine label="Trainer detaliu" value={trainerRawAccess ? "Activ" : "Oprit"} />
        <StatusLine label="Manager evaluat" value={managerView === "aggregate_only" ? "Doar agregat" : "Blocat"} />
      </div>
      <p className="mt-4 text-sm leading-6 text-foreground/62">{note}</p>
    </section>
  );
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-surface-muted px-3 py-2 text-sm">
      <span className="font-semibold text-foreground/60">{label}</span>
      <span className="font-semibold text-foreground">{value}</span>
    </div>
  );
}

function NextActions({ actions }: { actions: TrainerAction[] }) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Următoarele acțiuni</p>
      <div className="mt-4 space-y-3">
        {actions.map((action) => (
          <Link
            key={action.label}
            href={action.href}
            className="tap-soft block rounded-xl border border-[var(--border)] bg-background px-3 py-3 hover:border-burgundy/45"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-foreground">{action.label}</p>
              <span className="rounded-full bg-surface-muted px-2 py-1 text-xs font-semibold text-foreground/50">
                {action.urgency}
              </span>
            </div>
            <p className="mt-1 text-xs leading-5 text-foreground/56">{action.detail}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
