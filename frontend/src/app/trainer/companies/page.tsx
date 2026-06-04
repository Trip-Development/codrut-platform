import Link from "next/link";

import { getCompanyList, type CompanyListItem } from "@/api/companies";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerCompaniesPage() {
  const companies = await getCompanyList();

  return (
    <AppShell
      audience="trainer"
      eyebrow="Companii"
      title="Companiile tale"
      description="Lista companiilor cu care lucrezi, statusul fiecarui proiect si progresul operational."
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
    >
      {companies.length === 0 ? (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-8 text-center shadow-sm">
          <p className="text-sm text-foreground/62">Nicio companie configurata inca.</p>
        </section>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {companies.map((company) => (
            <CompanyCard key={company.id} company={company} />
          ))}
        </div>
      )}
    </AppShell>
  );
}

function CompanyCard({ company }: { company: CompanyListItem }) {
  const completion =
    company.assignmentCount > 0
      ? Math.round((company.completedCount / company.assignmentCount) * 100)
      : 0;

  return (
    <article className="flex flex-col rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold text-foreground">{company.name}</h2>
        <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55">
          {company.stage}
        </span>
      </div>

      <p className="mt-3 text-sm text-foreground/62">
        {company.participantCount} participanti · {company.completedCount}/{company.assignmentCount} completate
      </p>

      <div className="mt-4">
        <div className="flex items-center justify-between text-sm font-semibold text-foreground/62">
          <span>
            {company.completedCount}/{company.assignmentCount}
          </span>
          <span>{completion}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-muted">
          <div className="h-full rounded-full bg-burgundy" style={{ width: `${completion}%` }} />
        </div>
      </div>

      <Link
        href={`/trainer/companies/${company.id}`}
        className="tap-soft mt-4 inline-flex w-full justify-center rounded-xl bg-foreground px-4 py-2.5 text-sm font-semibold text-background hover:bg-burgundy hover:text-white"
      >
        Deschide
      </Link>
    </article>
  );
}
