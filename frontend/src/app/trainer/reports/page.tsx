import Link from "next/link";

import { getTrainerSession } from "@/api/auth-server";
import { getCompanyList } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerReportsPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [trainer, companies] = await Promise.all([
    getTrainerSession(),
    getCompanyList(requestOptions),
  ]);
  const reportingCompanies = companies
    .filter((company) => !company.dataUnavailable)
    .sort((a, b) => b.completedCount - a.completedCount || a.name.localeCompare(b.name, "ro"));

  return (
    <AppShell
      audience="trainer"
      eyebrow="Rapoarte"
      title="Rapoarte pe companie"
      description="Rapoartele sunt organizate în spațiul fiecărei companii, ca să nu amesteci clienții, participanții și progresul."
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
      userLabel={trainer.user.name}
      session={trainer}
    >
      {reportingCompanies.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-[var(--border)] bg-surface/70 p-8 text-center">
          <p className="text-base font-semibold text-foreground">Nu există rapoarte disponibile încă.</p>
          <p className="mt-2 text-sm text-foreground/58">
            Deschide o companie, importă lista de participanți și trimite invitațiile înainte de raportare.
          </p>
          <Link
            href="/trainer/companies"
            className="tap-soft mt-5 inline-flex min-h-10 items-center justify-center rounded-xl bg-burgundy px-4 py-2.5 text-sm font-bold text-white hover:bg-burgundy-700"
          >
            Deschide companiile
          </Link>
        </section>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {reportingCompanies.map((company) => {
            const completion =
              company.assignmentCount > 0
                ? Math.round((company.completedCount / company.assignmentCount) * 100)
                : 0;

            return (
              <article
                key={company.id}
                className="group flex min-h-60 flex-col rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-burgundy/24 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-burgundy/75">Companie</p>
                    <h2 className="mt-1 truncate text-lg font-semibold text-foreground">{company.name}</h2>
                  </div>
                  <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55 group-hover:bg-burgundy/10 group-hover:text-burgundy">
                    {stageLabel(company.stage)}
                  </span>
                </div>

                <dl className="mt-5 grid grid-cols-3 divide-x divide-[var(--border)] rounded-xl bg-surface-muted/55 py-3 text-center">
                  <ReportStat label="Participanți" value={company.participantCount} />
                  <ReportStat label="Asignări" value={company.assignmentCount} />
                  <ReportStat label="Finalizate" value={company.completedCount} />
                </dl>

                <div className="mt-auto pt-5">
                  <div className="flex items-center justify-between text-sm font-semibold text-foreground/62">
                    <span>Completare</span>
                    <span>{completion}%</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-muted">
                    <div className="h-full rounded-full bg-burgundy" style={{ width: `${completion}%` }} />
                  </div>
                  <Link
                    href={`/trainer/companies/${company.id}/reports`}
                    className="tap-soft mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl bg-foreground px-4 py-2.5 text-sm font-semibold text-background hover:bg-burgundy hover:text-white hover:shadow-sm"
                  >
                    Deschide rapoartele companiei
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}

function ReportStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="px-3">
      <p className="text-xs font-semibold text-foreground/45">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function stageLabel(stage: "setup" | "invites" | "completion" | "reporting"): string {
  switch (stage) {
    case "setup":
      return "Configurare";
    case "invites":
      return "Invitații";
    case "completion":
      return "În lucru";
    case "reporting":
      return "Raportare";
  }
}
