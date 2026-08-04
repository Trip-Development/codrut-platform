import Link from "next/link";
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  CheckCircle2Icon,
  CircleDashedIcon,
} from "lucide-react";

import { getTrainerSession } from "@/api/auth-server";
import { getServerApiRequestOptions } from "@/api/server-request";
import { getTrainerDashboardSummary, type TrainerCompanyRow } from "@/api/trainer";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { cn } from "@/utils/cn";

export default async function TrainerDashboardPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [trainer, summary] = await Promise.all([
    getTrainerSession(),
    getTrainerDashboardSummary(requestOptions),
  ]);
  const dataUnavailable = summary.stats.length === 0 && summary.activeCompanies.length === 0;

  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title="Acasă"
      description=""
      navItems={trainerNavItems}
      activeHref="/trainer"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <div className="flex flex-col gap-5">
        {dataUnavailable ? (
          <InlineFeedback tone="danger">
            Datele operaționale nu au putut fi încărcate. Reîncarcă pagina pentru a încerca din nou.
          </InlineFeedback>
        ) : null}
        <OperationsOverview companies={summary.activeCompanies} />
        <CompanyOperationsTable companies={summary.activeCompanies} />
      </div>
    </AppShell>
  );
}

function OperationsOverview({ companies }: { companies: TrainerCompanyRow[] }) {
  const totalAssignments = companies.reduce((total, company) => total + company.total, 0);
  const completedAssignments = companies.reduce((total, company) => total + company.completed, 0);
  const pendingAssignments = Math.max(0, totalAssignments - completedAssignments);
  const completionRate = totalAssignments > 0
    ? Math.round((completedAssignments / totalAssignments) * 100)
    : 0;
  const queue = companies
    .filter((company) => company.blockers.length > 0 || company.completed < company.total)
    .sort((first, second) => second.blockers.length - first.blockers.length)
    .slice(0, 5);

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="overflow-hidden rounded-lg border bg-surface" aria-labelledby="trainer-queue-title">
        <div className="flex min-h-14 items-center justify-between gap-4 border-b px-5 py-3">
          <h2 id="trainer-queue-title" className="text-lg font-semibold text-foreground">De rezolvat</h2>
          <span className="text-sm font-semibold tabular-nums text-muted-foreground">{queue.length}</span>
        </div>

        {companies.length === 0 ? (
          <div className="px-5 py-8">
            <p className="font-semibold text-foreground">Adaugă prima companie</p>
            <Link
              href="/trainer/companies?modal=create-company"
              className={serverLinkButtonClassName({ className: "mt-4" })}
            >
              Companie nouă
              <ArrowRightIcon data-icon="inline-end" aria-hidden="true" strokeWidth={1.8} />
            </Link>
          </div>
        ) : queue.length === 0 ? (
          <div className="flex items-center gap-3 px-5 py-8 text-sm font-semibold text-success-ink">
            <CheckCircle2Icon aria-hidden="true" className="size-5" strokeWidth={1.8} />
            Nicio intervenție urgentă
          </div>
        ) : (
          <div className="divide-y divide-border">
            {queue.map((company) => <QueueRow key={company.id} company={company} />)}
          </div>
        )}
      </section>

      <aside className="overflow-hidden rounded-lg border bg-surface" aria-labelledby="coverage-title">
        <div className="px-5 py-5">
          <h2 id="coverage-title" className="text-lg font-semibold text-foreground">Acoperire</h2>
          <div className="mt-5 flex items-end justify-between gap-4">
            <p className="text-4xl font-semibold tabular-nums text-foreground">{completionRate}%</p>
            <p className="pb-1 text-xs font-semibold text-muted-foreground">
              {completedAssignments}/{totalAssignments} completate
            </p>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${completionRate}%` }} />
          </div>
        </div>
        <dl className="divide-y divide-border border-t">
          <CoverageRow label="Companii în lucru" value={companies.length} />
          <CoverageRow label="Completări de urmărit" value={pendingAssignments} tone={pendingAssignments > 0 ? "attention" : "default"} />
          <CoverageRow label="Companii cu blocaje" value={companies.filter((company) => company.blockers.length > 0).length} tone="attention" />
        </dl>
      </aside>
    </div>
  );
}

function QueueRow({ company }: { company: TrainerCompanyRow }) {
  const pendingCount = Math.max(0, company.total - company.completed);
  const blockers = company.blockers.length > 0
    ? company.blockers.join(" · ")
    : pendingCount === 1
      ? "1 completare de urmărit"
      : `${pendingCount} completări de urmărit`;

  return (
    <article className="grid gap-3 px-5 py-4 md:grid-cols-[minmax(0,1fr)_minmax(14rem,20rem)_auto] md:items-center">
      <div className="flex min-w-0 items-start gap-3">
        <AlertTriangleIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-warning-ink" strokeWidth={1.8} />
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-foreground">{company.company}</h3>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{blockers}</p>
        </div>
      </div>
      <p className="text-sm font-medium leading-6 text-foreground">{company.nextAction}</p>
      <Link
        href={company.href}
        aria-label={`Deschide ${company.company}`}
        className={serverLinkButtonClassName({ variant: "ghost", size: "icon-sm" })}
      >
        <ArrowRightIcon aria-hidden="true" strokeWidth={1.8} />
      </Link>
    </article>
  );
}

function CoverageRow({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number;
  tone?: "default" | "attention";
}) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-3.5">
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className={cn("font-semibold tabular-nums", tone === "attention" && value > 0 ? "text-primary" : "text-foreground")}>{value}</dd>
    </div>
  );
}

function CompanyOperationsTable({ companies }: { companies: TrainerCompanyRow[] }) {
  return (
    <section className="overflow-hidden rounded-lg border bg-surface" aria-labelledby="company-operations-title">
      <div className="flex min-h-14 items-center justify-between gap-4 border-b px-5 py-3">
        <h2 id="company-operations-title" className="text-lg font-semibold text-foreground">Companii în lucru</h2>
        <Link href="/trainer/companies" className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline">
          Toate companiile
          <ArrowRightIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
        </Link>
      </div>

      {companies.length === 0 ? (
        <p className="px-5 py-8 text-sm font-semibold text-muted-foreground">Nicio companie activă</p>
      ) : (
        <div className="md:overflow-x-auto md:[scrollbar-width:thin]">
          <table className="block w-full text-left text-sm md:table md:min-w-[68rem] xl:min-w-0 xl:table-fixed">
            <colgroup>
              <col className="w-[20%]" />
              <col className="w-[12%]" />
              <col className="w-[18%]" />
              <col className="w-[24%]" />
              <col className="w-[26%]" />
            </colgroup>
            <thead className="hidden bg-muted/60 text-xs font-semibold text-muted-foreground md:table-header-group">
              <tr>
                <th scope="col" className="px-4 py-3">Companie</th>
                <th scope="col" className="px-4 py-3">Etapă</th>
                <th scope="col" className="min-w-40 px-4 py-3">Completare</th>
                <th scope="col" className="min-w-56 px-4 py-3">Blocaje</th>
                <th scope="col" className="min-w-64 px-4 py-3">Următorul pas</th>
              </tr>
            </thead>
            <tbody className="block divide-y divide-border md:table-row-group">
              {companies.map((company) => <CompanyRow key={company.id} company={company} />)}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function CompanyRow({ company }: { company: TrainerCompanyRow }) {
  const completion = company.total > 0 ? Math.round((company.completed / company.total) * 100) : 0;

  return (
    <tr className="grid grid-cols-2 gap-x-4 gap-y-3 px-4 py-4 transition-colors hover:bg-muted/35 md:table-row md:px-0 md:py-0">
      <td className="col-span-2 row-start-1 min-w-0 md:px-4 md:py-4">
        <Link href={company.href} className="font-semibold text-foreground hover:text-primary">{company.company}</Link>
        <span className="mt-1 block text-xs font-medium text-muted-foreground">
          {company.invited} {company.invited === 1 ? "invitație" : "invitații"}
        </span>
      </td>
      <td className="col-start-1 row-start-2 md:px-4 md:py-4">
        <span className="inline-flex items-center gap-2 text-xs font-semibold text-muted-foreground">
          <span className={cn("size-1.5 rounded-full", stageDotClass(company.stage))} aria-hidden="true" />
          {companyStageLabel(company.stage)}
        </span>
      </td>
      <td className="col-span-2 row-start-3 md:px-4 md:py-4">
        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Completare</span>
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="font-semibold tabular-nums text-foreground">{company.completed}/{company.total}</span>
          <span className="tabular-nums text-muted-foreground">{completion}%</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary" style={{ width: `${completion}%` }} />
        </div>
      </td>
      <td className="col-span-2 row-start-4 md:px-4 md:py-4">
        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Blocaje</span>
        {company.blockers.length > 0 ? (
          <div className="flex items-start gap-2 text-sm text-foreground">
            <CircleDashedIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-warning-ink" strokeWidth={1.8} />
            <span className="line-clamp-2">{company.blockers.join(" · ")}</span>
          </div>
        ) : (
          <span className="inline-flex items-center gap-2 text-sm font-medium text-success-ink">
            <CheckCircle2Icon aria-hidden="true" className="size-4" strokeWidth={1.8} />
            Fără blocaje
          </span>
        )}
      </td>
      <td className="col-span-2 row-start-5 border-t pt-3 md:border-0 md:px-4 md:py-4">
        <Link href={company.href} className="inline-flex items-center gap-1.5 font-semibold text-foreground hover:text-primary">
          {company.nextAction}
          <ArrowRightIcon aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={1.8} />
        </Link>
      </td>
    </tr>
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

function stageDotClass(stage: TrainerCompanyRow["stage"]): string {
  switch (stage) {
    case "setup":
      return "bg-muted-foreground";
    case "invites":
      return "bg-ochre";
    case "completion":
      return "bg-success";
    case "reporting":
      return "bg-primary";
  }
}
