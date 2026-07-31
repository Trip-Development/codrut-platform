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
import { HistoricalIcareNotice } from "@/components/reports/HistoricalIcareNotice";
import { IcarePerspectiveGrid } from "@/components/reports/IcarePerspectiveGrid";
import { ScaledBar } from "@/components/reports/native-charts";
import { reportScaleEmptyCopy, resolveReportScoreScale } from "@/components/reports/score-scale";
import { Card } from "@/components/ui/card";
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
  const lencioniScale = resolveReportScoreScale(
    report.lencioni_scale,
    { min: 0, max: 10, suffix: "" },
  );
  const driverScale = resolveReportScoreScale(
    report.driver_scale,
    { min: 0, max: 100, suffix: "%" },
  );

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

      <Card asChild className="px-5 [--card-spacing:--spacing(5)] md:px-6">
        <section aria-labelledby="pcm-profile-title" className="grid gap-5 md:grid-cols-[minmax(12rem,0.7fr)_minmax(0,1.3fr)] md:items-center">
          <div>
            <p className="text-sm font-semibold text-burgundy">Profil personal</p>
            <h2 id="pcm-profile-title" className="mt-1 text-2xl font-semibold tracking-tight text-foreground">PCM</h2>
          </div>
          <div className="flex flex-wrap gap-x-12 gap-y-5">
            <PcmValue label="Bază" value={report.pcm_base} />
            <PcmValue label="Fază" value={report.pcm_phase} />
          </div>
        </section>
      </Card>

      <ResultSection id="lencioni" title="Lencioni" description="Rezultatul echipei coordonate de această persoană.">
        {report.lencioni_team_ambiguous ? (
          <Card className="px-5 [--card-spacing:--spacing(5)]">
            <p className="font-semibold text-foreground">Echipa istorică nu poate fi stabilită sigur</p>
            <p className="mt-2 text-sm text-muted-foreground">
              {report.lencioni_team_ambiguity_message ??
                "Rezultatele rămân separate până când putem confirma echipa corectă pentru acest ciclu."}
            </p>
          </Card>
        ) : (
          <Card className="px-5 [--card-spacing:--spacing(5)]">
            <AverageList
              count={report.lencioni_count}
              items={report.lencioni_averages}
              min={lencioniScale.min}
              max={lencioniScale.max}
              suffix={lencioniScale.suffix}
              empty={reportScaleEmptyCopy(
                report.lencioni_scale,
                "Nu există încă un rezultat Lencioni pentru această echipă.",
              )}
            />
          </Card>
        )}
      </ResultSection>

      <ResultSection id="icare" title="iCARE" description="Cele trei perspective sunt păstrate separat.">
        <HistoricalIcareNotice
          count={report.icare_unclassified_response_count}
          reason={report.icare_unclassified_reason}
        />
        <IcarePerspectiveGrid
          ariaLabel="Perspective iCARE pentru această persoană"
          perspectives={(["direct_team", "leadership_peers", "self"] as const).map((cohort) => {
            const summary = report.icare_cohorts.find((item) => item.cohort === cohort);
            const scale = icareScale(summary);
            return {
              id: cohort,
              label: ICARE_LABELS[cohort],
              responseCount: summary?.response_count ?? 0,
              content: (
                <Card key={cohort} asChild className="gap-0 px-5 [--card-spacing:--spacing(5)]">
                  <article>
                    <h3 className="font-semibold text-foreground">{ICARE_LABELS[cohort]}</h3>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {summary?.response_count ?? 0} {(summary?.response_count ?? 0) === 1 ? "răspuns" : "răspunsuri"}
                    </p>
                    <div className="mt-4">
                      <AverageList
                        count={summary?.response_count ?? 0}
                        items={summary?.averages ?? []}
                        min={scale.min}
                        max={scale.max}
                        suffix={scale.suffix}
                        showCount={false}
                        empty={icareEmptyCopy(summary)}
                        note={icareMinimumScoreCopy(summary)}
                      />
                    </div>
                  </article>
                </Card>
              ),
            };
          })}
        />
      </ResultSection>

      <ResultSection id="ta-drivers" title="TA Drivers" description="Rezultatul individual, fără comparații sau detalii de echipă.">
        <Card className="px-5 [--card-spacing:--spacing(5)]">
          <AverageList
            count={report.driver_count}
            items={report.driver_averages}
            min={driverScale.min}
            max={driverScale.max}
            suffix={driverScale.suffix}
            dangerAbove={50}
            showFeedback
            empty={reportScaleEmptyCopy(
              report.driver_scale,
              "Nu există încă un rezultat TA pentru această persoană.",
            )}
          />
        </Card>
      </ResultSection>
    </div>
  );
}

function PcmValue({ label, value }: { label: string; value?: string | null }) {
  const profile = getPcmProfile(value);
  return (
    <div>
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <p className="mt-1.5 flex items-center gap-2 text-xl font-semibold text-foreground">
        <span
          aria-hidden="true"
          className="size-3 rounded-full ring-2 ring-border"
          style={{ backgroundColor: profile?.color ?? "var(--muted-foreground)" }}
        />
        {value ? formatPcmLabel(value) : "În așteptare"}
      </p>
    </div>
  );
}

function ResultSection({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="grid gap-6 border-b border-border pb-10" aria-labelledby={`member-result-${id}`}>
      <div>
        <h2 id={`member-result-${id}`} className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="grid gap-5">{children}</div>
    </section>
  );
}

function icareScale(summary?: IcareCohortSummary): { min: number; max: number; suffix: string } {
  if (summary?.score_unit === "percent") {
    return { min: summary.scale_min ?? 0, max: summary.scale_max ?? 100, suffix: "%" };
  }
  if (summary?.score_unit === "grade_1_to_5") {
    const max = summary.scale_max ?? 5;
    return { min: summary.scale_min ?? 1, max, suffix: ` din ${max}` };
  }
  return { min: summary?.scale_min ?? 0, max: summary?.scale_max ?? 100, suffix: "" };
}

function icareEmptyCopy(summary?: IcareCohortSummary): string {
  if (summary?.unavailable_reason === "incompatible_score_scales" || summary?.score_scale_compatible === false) {
    return "Aceste răspunsuri folosesc scale diferite și nu pot fi afișate împreună. Selectează o singură evaluare.";
  }
  return "Nu există încă un rezultat iCARE scorabil pentru această perspectivă.";
}

function icareMinimumScoreCopy(summary?: IcareCohortSummary): string | null {
  if (!summary || summary.averages.length === 0) return null;
  const minimum = summary.scale_min ?? (summary.score_unit === "grade_1_to_5" ? 1 : 0);
  if (!summary.averages.some((item) => Math.abs(item.avg - minimum) < 0.05)) return null;
  if (summary.score_unit === "percent") {
    return "0% este scorul minim valid pe această scală, nu un rezultat lipsă.";
  }
  if (summary.score_unit === "grade_1_to_5") {
    return `${minimum} din ${summary.scale_max ?? 5} este scorul minim valid pe această scală, nu un rezultat lipsă.`;
  }
  return null;
}

function AverageList({
  count,
  items,
  min = 0,
  max,
  suffix = "",
  empty,
  showCount = true,
  dangerAbove,
  showFeedback = false,
  note,
}: {
  count: number;
  items: ReportAverage[];
  min?: number;
  max: number;
  suffix?: string;
  empty: string;
  showCount?: boolean;
  dangerAbove?: number;
  showFeedback?: boolean;
  note?: string | null;
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
                <span className="min-w-0 font-semibold text-foreground">{item.label}</span>
                <span className={isDanger ? "font-mono font-semibold tabular-nums text-destructive" : "font-mono font-semibold tabular-nums text-foreground"}>{item.avg}{suffix}</span>
              </div>
              <ScaledBar
                value={item.avg}
                min={min}
                max={max}
                colorClassName={isDanger ? "bg-destructive" : undefined}
              />
              {showFeedback && isDanger && item.feedback ? (
                <p className="mt-2 text-sm leading-6 text-destructive">{item.feedback}</p>
              ) : null}
            </div>
          );
        })}
        {note ? <p className="text-xs leading-5 text-muted-foreground">{note}</p> : null}
      </div>
    </div>
  );
}
