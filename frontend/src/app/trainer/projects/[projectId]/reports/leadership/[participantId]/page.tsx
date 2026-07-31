import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";
import { notFound } from "next/navigation";

import {
  getCompanyProjectById,
  getLeadershipMemberReport,
  type IcareCohortSummary,
  type ReportAverage,
} from "@/api/companies";
import { formatPcmLabel, getPcmProfile } from "@/api/pcm";
import { getServerApiRequestOptions } from "@/api/server-request";
import { ScaledBar } from "@/components/reports/native-charts";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { buildProjectReportQuery } from "../../report-cycle";

const ICARE_LABELS: Record<IcareCohortSummary["cohort"], string> = {
  direct_team: "Cum te vede echipa ta",
  leadership_peers: "Cum te văd colegii din leadership",
  self: "Cum te evaluezi",
};

export default async function LeadershipMemberReportPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string; participantId: string }>;
  searchParams: Promise<{ baseline?: string; cycle?: string }>;
}) {
  const [{ projectId, participantId }, query, requestOptions] = await Promise.all([
    params,
    searchParams,
    getServerApiRequestOptions(),
  ]);
  const project = await getCompanyProjectById(projectId, requestOptions);
  if (!project) notFound();

  const report = await getLeadershipMemberReport(
    project.company_id,
    project.id,
    participantId,
    requestOptions,
    { assessmentCycleId: query.cycle },
  );
  const overviewHref = `/trainer/projects/${project.id}/reports${buildProjectReportQuery({
    cycle: query.cycle,
  })}`;

  return (
    <div className="flex flex-col gap-10">
      <header className="border-b border-border pb-6">
        <Link href={overviewHref} className={serverLinkButtonClassName({ variant: "ghost", className: "mb-5 w-fit" })}>
          <ArrowLeftIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
          Înapoi la rezultatele proiectului
        </Link>
        <p className="text-sm font-semibold text-burgundy">Raport individual</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-foreground">{report.member.full_name}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {report.member.position || "Membru leadership"} · {project.name}
        </p>
      </header>

      <section aria-labelledby="pcm-profile-title" className="grid gap-5 rounded-lg bg-foreground px-6 py-6 text-background md:grid-cols-[minmax(12rem,0.7fr)_minmax(0,1.3fr)] md:items-center">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-background/55">Profil personal</p>
          <h2 id="pcm-profile-title" className="mt-2 text-2xl font-semibold">PCM</h2>
        </div>
        <div className="flex flex-wrap gap-x-12 gap-y-5">
          <PcmValue label="Bază" value={report.pcm_base} />
          <PcmValue label="Fază" value={report.pcm_phase} />
        </div>
      </section>

      <OrderedSection number="01" title="Lencioni" description="Rezultatul echipei coordonate de această persoană.">
        <AverageList
          count={report.lencioni_count}
          items={report.lencioni_averages}
          max={10}
          empty="Nu există încă un rezultat Lencioni pentru această echipă."
        />
      </OrderedSection>

      <OrderedSection number="02" title="iCARE" description="Cele trei perspective sunt păstrate separat.">
        <div className="grid gap-5 lg:grid-cols-3">
          {(["direct_team", "leadership_peers", "self"] as const).map((cohort) => {
            const summary = report.icare_cohorts.find((item) => item.cohort === cohort);
            return (
              <article key={cohort} className="border-y border-border px-5 py-5">
                <h3 className="font-semibold text-foreground">{ICARE_LABELS[cohort]}</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  {summary?.response_count ?? 0} {(summary?.response_count ?? 0) === 1 ? "răspuns" : "răspunsuri"}
                </p>
                <div className="mt-4">
                  <AverageList
                    count={summary?.response_count ?? 0}
                    items={summary?.averages ?? []}
                    max={100}
                    suffix="%"
                    showCount={false}
                    empty="Nu există încă rezultate pentru această perspectivă."
                  />
                </div>
              </article>
            );
          })}
        </div>
      </OrderedSection>

      <OrderedSection number="03" title="TA Drivers" description="Rezultatul individual, fără comparații sau detalii de echipă.">
        <AverageList
          count={report.driver_count}
          items={report.driver_averages}
          max={100}
          suffix="%"
          dangerAbove={50}
          showFeedback
          empty="Nu există încă un rezultat TA pentru această persoană."
        />
      </OrderedSection>
    </div>
  );
}

function PcmValue({ label, value }: { label: string; value?: string | null }) {
  const profile = getPcmProfile(value);
  return (
    <div>
      <p className="text-xs font-semibold text-background/55">{label}</p>
      <p className="mt-1.5 flex items-center gap-2 text-xl font-semibold">
        <span
          aria-hidden="true"
          className="size-3 rounded-full ring-2 ring-background/15"
          style={{ backgroundColor: profile?.color ?? "var(--muted-foreground)" }}
        />
        {value ? formatPcmLabel(value) : "În așteptare"}
      </p>
    </div>
  );
}

function OrderedSection({
  number,
  title,
  description,
  children,
}: {
  number: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="grid gap-6 border-b border-border pb-10" aria-labelledby={`member-result-${number}`}>
      <div className="grid gap-2 md:grid-cols-[3rem_minmax(0,1fr)]">
        <p className="font-mono text-sm font-semibold text-burgundy">{number}</p>
        <div>
          <h2 id={`member-result-${number}`} className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="md:pl-12">{children}</div>
    </section>
  );
}

function AverageList({
  count,
  items,
  max,
  suffix = "",
  empty,
  showCount = true,
  dangerAbove,
  showFeedback = false,
}: {
  count: number;
  items: ReportAverage[];
  max: number;
  suffix?: string;
  empty: string;
  showCount?: boolean;
  dangerAbove?: number;
  showFeedback?: boolean;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }
  return (
    <div>
      {showCount ? (
        <p className="mb-4 text-xs font-semibold text-muted-foreground">
          {count} {count === 1 ? "răspuns" : "răspunsuri"}
        </p>
      ) : null}
      <div className="grid gap-4">
        {items.map((item) => {
          const isDanger = dangerAbove !== undefined && item.avg > dangerAbove;
          return (
            <div key={item.id} data-tone={isDanger ? "danger" : "default"}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="font-semibold text-foreground">{item.label}</span>
                <span className={isDanger ? "font-mono font-semibold tabular-nums text-destructive" : "font-mono font-semibold tabular-nums text-foreground"}>{item.avg}{suffix}</span>
              </div>
              <ScaledBar
                value={item.avg}
                max={max}
                colorClassName={isDanger ? "bg-destructive" : undefined}
              />
              {showFeedback && isDanger && item.feedback ? (
                <p className="mt-2 text-sm leading-6 text-destructive">{item.feedback}</p>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
