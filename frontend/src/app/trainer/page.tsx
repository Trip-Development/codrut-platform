import Link from "next/link";

import { getTrainerSession } from "@/api/auth-server";
import { getServerApiRequestOptions } from "@/api/server-request";
import { getTrainerDashboardSummary, type TrainerCompanyRow } from "@/api/trainer";
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
    >
      <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summary.stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      <DeliveryTable companies={summary.activeCompanies} />
    </AppShell>
  );
}



function DeliveryTable({ companies }: { companies: TrainerCompanyRow[] }) {
  return (
    <section className="surface-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-[var(--border)] bg-surface-muted px-5 py-4">
        <h2 className="text-lg font-bold text-foreground">Status Proiecte Active</h2>
        <Link href="/trainer/companies" className="text-sm font-semibold text-burgundy hover:underline">
          Vezi toate companiile &rarr;
        </Link>
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
          className="tap-soft mt-3 inline-flex w-full justify-center rounded-full bg-burgundy px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-burgundy/10 hover:bg-burgundy-700"
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
