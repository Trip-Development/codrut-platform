import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";

import type {
  AssessmentCycle,
  CompanyReportAggregate,
  IcareCohortSummary,
  LeadershipMemberSummary,
  ReportAverage,
  ReportDistribution,
  ReportHierarchyIssue,
} from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import {
  CycleComparisonBars,
  CycleDistributionPies,
  type CycleComparisonRow,
  type CycleDistributionSeries,
} from "@/components/reports/CycleComparisonBars";
import { cycleAccent } from "@/components/reports/cycle-accents";
import { HistoricalIcareNotice } from "@/components/reports/HistoricalIcareNotice";
import { IcarePerspectiveGrid } from "@/components/reports/IcarePerspectiveGrid";
import { DonutChart, ParticipantFrequencyPie, ScaledBar } from "@/components/reports/native-charts";
import { ReportSection as SharedReportSection } from "@/components/reports/ReportSection";
import { reportScaleEmptyCopy, resolveReportScoreScale } from "@/components/reports/score-scale";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { cn } from "@/utils/cn";
import { getProjectReportHistoryData } from "../project-data";
import { CycleComparisonControls } from "./CycleComparisonControls";
import { ReportPrintButton } from "./ReportPrintButton";
import { buildProjectReportQuery } from "./report-cycle";

const ICARE_LABELS: Record<IcareCohortSummary["cohort"], string> = {
  direct_team: "Cum vede echipa leadershipul",
  leadership_peers: "Cum se văd colegii din leadership",
  self: "Cum se evaluează liderii",
};

const DRIVER_COLORS: Record<string, string> = {
  be_perfect: "var(--chart-1)",
  perfect: "var(--chart-1)",
  be_strong: "var(--chart-2)",
  strong: "var(--chart-2)",
  please_people: "var(--chart-3)",
  hurry_up: "var(--chart-4)",
  try_hard: "var(--chart-5)",
};
const DISTRIBUTION_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

function tieBreakLabel(count: number): string {
  return count === 1 ? "o departajare" : `${count} departajări`;
}

export default async function ProjectReportsPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ baseline?: string; compare?: string; cycle?: string }>;
}) {
  const [{ projectId }, query, requestOptions] = await Promise.all([
    params,
    searchParams,
    getServerApiRequestOptions(),
  ]);
  const { project, participants, assessmentCycles, cycleReports } = await getProjectReportHistoryData(
    projectId,
    requestOptions,
    query.cycle,
  );
  const availableCycles = [...assessmentCycles]
    .filter((cycle) => cycle.status !== "draft")
    .sort((left, right) => left.sequence - right.sequence);
  const selectedCycle = availableCycles.find((cycle) => cycle.id === query.cycle) ?? null;
  const defaultBaselineCycle = availableCycles[0] ?? null;
  const defaultCompareCycle = availableCycles.at(-1) ?? defaultBaselineCycle;
  const baselineCycle = availableCycles.find((cycle) => cycle.id === query.baseline)
    ?? defaultBaselineCycle;
  const compareCycleCandidate = availableCycles.find((cycle) => cycle.id === query.compare);
  const compareCycle = compareCycleCandidate && compareCycleCandidate.id !== baselineCycle?.id
    ? compareCycleCandidate
    : [...availableCycles].reverse().find((cycle) => cycle.id !== baselineCycle?.id) ?? defaultCompareCycle;
  const comparedCycles = selectedCycle
    ? [selectedCycle]
    : [baselineCycle, compareCycle].filter(
        (cycle, index, cycles): cycle is AssessmentCycle => Boolean(cycle)
          && cycles.findIndex((candidate) => candidate?.id === cycle?.id) === index,
      );
  const reportsByCycle = new Map(cycleReports.map((report) => [report.cycle?.id, report]));
  const comparedReports = comparedCycles.flatMap((cycle) => {
    const report = reportsByCycle.get(cycle.id);
    return report ? [report] : [];
  });

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">{project.name}</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-foreground">
            {selectedCycle ? selectedCycle.name : "Evoluția proiectului"}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            {selectedCycle
              ? "Rezultatele disponibile pentru evaluarea selectată"
              : comparedCycles.length === 2
                ? `${comparedCycles[0].name} comparată cu ${comparedCycles[1].name}`
              : "Rezultatele disponibile pentru proiect"}
          </p>
          {availableCycles.length > 0 ? (
            <ul className="mt-5 flex flex-wrap gap-x-5 gap-y-3" aria-label="Legendă cicluri de evaluare">
              {comparedCycles.map((cycle, index) => (
                <li key={cycle.id} className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                  <span aria-hidden="true" className={cn("size-2.5 rounded-full", cycleAccent(index).dot)} />
                  Ciclul {cycle.sequence}: {cycle.name}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <ReportPrintButton />
      </header>

      {availableCycles.length > 1 ? (
        <CycleComparisonControls
          cycles={availableCycles}
          cycleId={selectedCycle?.id ?? null}
          baselineId={baselineCycle?.id ?? availableCycles[0].id}
          compareId={compareCycle?.id ?? availableCycles.at(-1)?.id ?? availableCycles[0].id}
        />
      ) : null}

      {selectedCycle || cycleReports.length <= 1 ? (
        <div className="grid gap-14">
          {cycleReports.map(({ cycle, aggregate }) => (
            <ProjectCycleResults
              key={cycle?.id ?? "legacy"}
              cycle={cycle}
              aggregate={aggregate}
              participantCount={participants.length}
              projectId={projectId}
              accentIndex={Math.max(0, availableCycles.findIndex((item) => item.id === cycle?.id))}
            />
          ))}
        </div>
      ) : (
        <ProjectCyclesComparison
          reports={comparedReports}
          participantCount={participants.length}
          projectId={projectId}
        />
      )}
    </div>
  );
}

type ProjectCycleReport = {
  cycle: AssessmentCycle | null;
  aggregate: CompanyReportAggregate;
};

function ProjectCyclesComparison({
  reports,
  participantCount,
  projectId,
}: {
  reports: ProjectCycleReport[];
  participantCount: number;
  projectId: string;
}) {
  const reportsPath = `/trainer/projects/${projectId}/reports`;
  const latest = reports.at(-1)?.aggregate;
  const lencioniScale = sharedCycleScale(
    reports.map(({ aggregate }) => resolveReportScoreScale(
      aggregate.lencioni_scale,
      { min: 3, max: 9, suffix: "" },
    )),
    { min: 3, max: 9, suffix: "" },
  );
  const driverScale = sharedCycleScale(
    reports.map(({ aggregate }) => resolveReportScoreScale(
      aggregate.driver_scale,
      { min: 0, max: 100, suffix: "%" },
    )),
    { min: 0, max: 100, suffix: "%" },
  );
  const hierarchyIssues = reports.flatMap(({ aggregate }) => aggregate.hierarchy_issues);
  const hierarchyAmbiguous = reports.some(({ aggregate }) => aggregate.hierarchy_ambiguous);
  const unclassifiedCount = reports.reduce(
    (sum, { aggregate }) => sum + aggregate.icare_unclassified_response_count,
    0,
  );

  return (
    <article className="flex flex-col gap-10" aria-label="Comparație între evaluări">
      <ScoringAvailabilityAlert
        pending={reports.reduce((sum, { aggregate }) => sum + aggregate.reportable_pending_score_count, 0)}
        failed={reports.reduce((sum, { aggregate }) => sum + aggregate.reportable_failed_score_count, 0)}
        orphaned={reports.reduce((sum, { aggregate }) => sum + aggregate.reportable_orphaned_score_count, 0)}
      />

      <CycleComparisonBars
        title="Participare"
        rows={[{
          id: "completion",
          label: "Răspunsuri finalizate",
          values: reports.map(({ cycle, aggregate }, index) => ({
            cycleId: cycle?.id ?? `cycle-${index}`,
            cycleLabel: cycle?.name ?? "Evaluare",
            color: cycleAccent(index).color,
            value: aggregate.completion_rate,
            valueLabel: `${aggregate.total_completed}/${aggregate.total_assigned} · ${aggregate.completion_rate}%`,
          })),
        }]}
        max={100}
        deltaUnit="pp"
        higherIsBetter
      />

      <SharedReportSection
        id="comparison-pcm"
        title="PCM"
        description="Profilurile de bază și de fază ale participanților."
      >
        <div className="grid gap-5">
          <CycleDistributionPies
            title="Profil de bază"
            series={distributionPieSeries(reports, (aggregate) => aggregate.pcm_base_distribution)}
          />
          <CycleDistributionPies
            title="Profil de fază"
            series={distributionPieSeries(reports, (aggregate) => aggregate.pcm_phase_distribution)}
          />
        </div>
      </SharedReportSection>

      <SharedReportSection
        id="comparison-lencioni"
        title="Lencioni"
        description="Cele cinci dimensiuni care susțin funcționarea unei echipe."
      >
        <CycleComparisonBars
          title="Rezultatul întregului proiect"
          rows={averageComparisonRows(reports, (aggregate) => aggregate.lencioni_averages, lencioniScale.suffix)}
          min={lencioniScale.min}
          max={lencioniScale.max}
          deltaUnit="points"
          higherIsBetter
          empty={reportScaleEmptyCopy(
            latest?.lencioni_scale,
            "Nu există încă rezultate Lencioni comparabile pentru acest proiect.",
          )}
        />
        {!hierarchyAmbiguous ? (
          <Link
            href={`${reportsPath}/lencioni`}
            className="inline-flex w-fit items-center gap-2 text-sm font-semibold text-primary hover:underline"
          >
            Vezi rezultatele pe echipe
            <ArrowRightIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
          </Link>
        ) : (
          <HierarchyDiagnosticsPanel
            title="Rezultatele pe echipe sunt momentan indisponibile"
            description="Rezultatele proiectului rămân vizibile. Verifică relațiile din organigramă pentru detaliile pe echipe."
            issues={hierarchyIssues}
          />
        )}
      </SharedReportSection>

      <SharedReportSection
        id="comparison-icare"
        title="iCARE"
        description="Comportamentele de leadership observate din trei perspective."
      >
        <HistoricalIcareNotice count={unclassifiedCount} reason={unclassifiedCount > 0 ? "historical_cohort_unavailable" : null} />
        {hierarchyAmbiguous ? (
          <HierarchyDiagnosticsPanel
            title="Unele perspective bazate pe organigramă sunt momentan indisponibile"
            description="Corectează relațiile ambigue din organigramă. Autoevaluările disponibile rămân vizibile."
            issues={hierarchyIssues}
          />
        ) : null}
        <IcarePerspectiveGrid
          perspectives={(Object.keys(ICARE_LABELS) as IcareCohortSummary["cohort"][]).map((cohort) => {
            const summaries = reports.map(({ aggregate }) =>
              aggregate.icare_cohorts.find((item) => item.cohort === cohort));
            const scale = sharedCycleScale(summaries.map((summary) => icareScale(summary)));
            return {
              id: cohort,
              label: ICARE_LABELS[cohort],
              responseCount: summaries.reduce((sum, summary) => sum + (summary?.response_count ?? 0), 0),
              content: (
                <CycleComparisonBars
                  title={ICARE_LABELS[cohort]}
                  rows={icareComparisonRows(reports, cohort)}
                  min={scale.min}
                  max={scale.max}
                  deltaUnit={scale.suffix === "%" ? "pp" : "points"}
                  higherIsBetter
                  empty="Nu există încă rezultate comparabile pentru această perspectivă."
                />
              ),
            };
          })}
        />
      </SharedReportSection>

      <SharedReportSection
        id="comparison-ta-drivers"
        title="TA Drivers"
        description="Driverii comportamentali care se pot activa în situații de stres."
      >
        <CycleComparisonBars
          title="Media procentuală"
          rows={averageComparisonRows(reports, (aggregate) => aggregate.driver_averages, driverScale.suffix)}
          min={driverScale.min}
          max={driverScale.max}
          deltaUnit={driverScale.suffix === "%" ? "pp" : "points"}
          higherIsBetter={false}
          empty={reportScaleEmptyCopy(
            latest?.driver_scale,
            "Nu există încă rezultate TA comparabile pentru acest proiect.",
          )}
        />
        <div className="grid gap-5">
          <CycleDistributionPies
            title="Primul driver dominant"
            series={rankPieSeries(reports, "first_rank")}
          />
          <CycleDistributionPies
            title="Al doilea driver dominant"
            series={rankPieSeries(reports, "second_rank")}
          />
        </div>
      </SharedReportSection>

      <SharedReportSection
        id="comparison-leadership"
        title="Echipa de leadership"
        description="Lista curentă este afișată o singură dată; raportul individual păstrează selectorul de evaluare."
      >
        <LeadershipMembers members={latest?.leadership_members ?? []} reportsPath={reportsPath} query="" />
      </SharedReportSection>

      <footer className="border-t border-border pt-5 text-sm text-muted-foreground">
        {participantCount} {participantCount === 1 ? "participant" : "participanți"} în proiect
      </footer>
    </article>
  );
}

function sharedCycleScale(
  scales: Array<{ min: number; max: number; suffix: string }>,
  fallback = { min: 0, max: 100, suffix: "%" },
) {
  if (scales.length === 0) return fallback;
  return {
    min: Math.min(...scales.map((scale) => scale.min)),
    max: Math.max(...scales.map((scale) => scale.max)),
    suffix: new Set(scales.map((scale) => scale.suffix)).size === 1 ? scales[0]?.suffix ?? "" : "",
  };
}

function averageComparisonRows(
  reports: ProjectCycleReport[],
  select: (aggregate: CompanyReportAggregate) => ReportAverage[],
  suffix: string,
): CycleComparisonRow[] {
  const dimensions = new Map<string, string>();
  reports.forEach(({ aggregate }) => select(aggregate).forEach((item) => dimensions.set(item.id, item.label)));
  return [...dimensions].map(([id, label]) => ({
    id,
    label,
    values: reports.flatMap(({ cycle, aggregate }, index) => {
      const item = select(aggregate).find((candidate) => candidate.id === id);
      return item ? [{
        cycleId: cycle?.id ?? `cycle-${index}`,
        cycleLabel: cycle?.name ?? "Evaluare",
        color: cycleAccent(index).color,
        value: item.avg,
        valueLabel: `${item.avg}${suffix}`,
      }] : [];
    }),
  }));
}

function distributionPieSeries(
  reports: ProjectCycleReport[],
  select: (aggregate: CompanyReportAggregate) => ReportDistribution[],
): CycleDistributionSeries[] {
  const colors = distributionColors(reports.flatMap(({ aggregate }) => select(aggregate)));
  return reports.map(({ cycle, aggregate }, index) => ({
    cycleId: cycle?.id ?? `cycle-${index}`,
    cycleLabel: cycle?.name ?? "Evaluare",
    segments: select(aggregate).map((item) => ({
      ...item,
      color: item.color ?? colors.get(item.id) ?? DISTRIBUTION_COLORS[0],
    })),
  }));
}

function icareComparisonRows(
  reports: ProjectCycleReport[],
  cohort: IcareCohortSummary["cohort"],
): CycleComparisonRow[] {
  const dimensions = new Map<string, string>();
  reports.forEach(({ aggregate }) => {
    aggregate.icare_cohorts
      .find((summary) => summary.cohort === cohort)
      ?.averages.forEach((item) => dimensions.set(item.id, item.label));
  });
  return [...dimensions].map(([id, label]) => ({
    id: `${cohort}-${id}`,
    label,
    values: reports.flatMap(({ cycle, aggregate }, index) => {
      const summary = aggregate.icare_cohorts.find((item) => item.cohort === cohort);
      const item = summary?.averages.find((average) => average.id === id);
      if (!item) return [];
      const scale = icareScale(summary);
      return [{
        cycleId: cycle?.id ?? `cycle-${index}`,
        cycleLabel: cycle?.name ?? "Evaluare",
        color: cycleAccent(index).color,
        value: item.avg,
        valueLabel: `${item.avg}${scale.suffix}`,
      }];
    }),
  }));
}

function rankPieSeries(
  reports: ProjectCycleReport[],
  rank: "first_rank" | "second_rank",
): CycleDistributionSeries[] {
  const colors = new Map<string, string>();
  reports.flatMap(({ aggregate }) => aggregate.driver_rank_summary[rank]).forEach((item) => {
    if (!colors.has(item.id)) {
      colors.set(
        item.id,
        item.color ?? DRIVER_COLORS[item.id] ?? DISTRIBUTION_COLORS[colors.size % DISTRIBUTION_COLORS.length],
      );
    }
  });
  return reports.map(({ cycle, aggregate }, index) => ({
    cycleId: cycle?.id ?? `cycle-${index}`,
    cycleLabel: cycle?.name ?? "Evaluare",
    segments: aggregate.driver_rank_summary[rank].map((item, itemIndex) => ({
      ...item,
      color: colors.get(item.id) ?? DISTRIBUTION_COLORS[itemIndex % DISTRIBUTION_COLORS.length],
    })),
  }));
}

function distributionColors(items: ReportDistribution[]): Map<string, string> {
  const colors = new Map<string, string>();
  items.forEach((item) => {
    if (!colors.has(item.id)) {
      colors.set(item.id, item.color ?? DISTRIBUTION_COLORS[colors.size % DISTRIBUTION_COLORS.length]);
    }
  });
  return colors;
}

function ProjectCycleResults({
  cycle,
  aggregate,
  participantCount,
  projectId,
  accentIndex,
}: {
  cycle: AssessmentCycle | null;
  aggregate: CompanyReportAggregate;
  participantCount: number;
  projectId: string;
  accentIndex: number;
}) {
  const reportQuery = buildProjectReportQuery({
    cycle: cycle?.id,
  });
  const reportsPath = `/trainer/projects/${projectId}/reports`;
  const cycleKey = cycle?.id ?? "legacy";
  const accent = cycleAccent(accentIndex);
  const driverPieEmptyLabel = aggregate.driver_rank_summary.insufficient_driver_score_count > 0
    ? "Nu există rezultate TA care pot fi incluse în aceste grafice."
    : undefined;
  const lencioniScale = resolveReportScoreScale(
    aggregate.lencioni_scale,
    { min: 3, max: 9, suffix: "" },
  );
  const driverScale = resolveReportScoreScale(
    aggregate.driver_scale,
    { min: 0, max: 100, suffix: "%" },
  );

  return (
    <article
      className={cn("flex flex-col gap-10 border-l-2 pl-5 sm:pl-7", accent.rail)}
      aria-labelledby={`project-cycle-${cycleKey}`}
    >
      <header className="flex flex-col gap-2 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold text-muted-foreground">
            {cycle ? `Ciclul ${cycle.sequence}` : "Evaluare"}
          </p>
          <h2 id={`project-cycle-${cycleKey}`} className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
            {cycle?.name ?? "Rezultatele proiectului"}
          </h2>
        </div>
        <div className="text-left sm:text-right">
          {cycle ? (
            <p className="text-xs font-semibold text-muted-foreground">{cycleStatusLabel(cycle.status)}</p>
          ) : null}
          <p className="mt-1 text-sm font-semibold tabular-nums text-foreground">
            {aggregate.total_completed} din {aggregate.total_assigned} răspunsuri
          </p>
        </div>
      </header>

      <ScoringAvailabilityAlert
        pending={aggregate.reportable_pending_score_count}
        failed={aggregate.reportable_failed_score_count}
        orphaned={aggregate.reportable_orphaned_score_count}
      />

      <SharedReportSection
        id={`${cycleKey}-pcm`}
        title="PCM"
        description="Profilurile de bază și de fază ale participanților."
      >
        <div className="grid gap-5 lg:grid-cols-2">
          <ChartPanel title="Profil de bază">
            <DonutChart
              title="Distribuție PCM bază"
              data={aggregate.pcm_base_distribution.map((item) => ({
                ...item,
                color: item.color ?? undefined,
              }))}
              emptyLabel="Nu există încă profiluri PCM de bază completate."
            />
          </ChartPanel>
          <ChartPanel title="Profil de fază">
            <DonutChart
              title="Distribuție PCM fază"
              data={aggregate.pcm_phase_distribution.map((item) => ({
                ...item,
                color: item.color ?? undefined,
              }))}
              emptyLabel="Nu există încă profiluri PCM de fază completate."
            />
          </ChartPanel>
        </div>
      </SharedReportSection>

      <SharedReportSection
        id={`${cycleKey}-lencioni`}
        title="Lencioni"
        description="Cele cinci dimensiuni care susțin funcționarea unei echipe."
      >
        <AveragePanel
          title="Rezultatul întregului proiect"
          count={aggregate.lencioni_count}
          items={aggregate.lencioni_averages}
          min={lencioniScale.min}
          max={lencioniScale.max}
          suffix={lencioniScale.suffix}
          empty={reportScaleEmptyCopy(
            aggregate.lencioni_scale,
            "Nu există încă rezultate Lencioni scorate pentru acest proiect.",
          )}
        />
        {aggregate.hierarchy_ambiguous ? (
          <HierarchyDiagnosticsPanel
            title="Rezultatele pe echipe sunt momentan indisponibile"
            description="Rezultatul întregului proiect rămâne corect. Verifică relațiile din organigramă pentru a deschide defalcarea pe echipe."
            issues={aggregate.hierarchy_issues}
          />
        ) : (
          <Link
            href={`${reportsPath}/lencioni${reportQuery}`}
            className="inline-flex w-fit items-center gap-2 text-sm font-semibold text-primary hover:underline"
          >
            Vezi rezultatele pe echipe
            <ArrowRightIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
          </Link>
        )}
      </SharedReportSection>

      <SharedReportSection
        id={`${cycleKey}-icare`}
        title="iCARE"
        description="Comportamentele de leadership observate din trei perspective."
      >
        <HistoricalIcareNotice
          count={aggregate.icare_unclassified_response_count}
          reason={aggregate.icare_unclassified_reason}
        />
        {aggregate.hierarchy_ambiguous ? (
          <HierarchyDiagnosticsPanel
            title="Perspectivele bazate pe organigramă sunt momentan indisponibile"
            description={aggregate.hierarchy_ambiguity_message ?? "Corectează relațiile ambigue din organigramă. Autoevaluările rămân disponibile mai jos."}
            issues={aggregate.hierarchy_issues}
          />
        ) : null}
        <IcarePerspectiveGrid
          perspectives={(["direct_team", "leadership_peers", "self"] as const).map((cohort) => {
            const summary = aggregate.icare_cohorts.find((item) => item.cohort === cohort);
            if (aggregate.hierarchy_ambiguous && cohort !== "self") {
              return {
                id: cohort,
                label: ICARE_LABELS[cohort],
                responseCount: summary?.response_count ?? 0,
                content: (
                  <Card key={cohort} asChild className="px-5 text-muted-foreground [--card-spacing:--spacing(5)]">
                    <article>
                      <h3 className="font-semibold text-foreground">{ICARE_LABELS[cohort]}</h3>
                      <p>Perspectiva va apărea după corectarea relațiilor din organigramă.</p>
                    </article>
                  </Card>
                ),
              };
            }
            const scale = icareScale(summary);
            return {
              id: cohort,
              label: ICARE_LABELS[cohort],
              responseCount: summary?.response_count ?? 0,
              content: (
                <AveragePanel
                  title={ICARE_LABELS[cohort]}
                  count={summary?.response_count ?? 0}
                  items={summary?.averages ?? []}
                  min={scale.min}
                  max={scale.max}
                  suffix={scale.suffix}
                  empty={icareEmptyCopy(summary)}
                  note={icareMinimumScoreCopy(summary)}
                />
              ),
            };
          })}
        />
      </SharedReportSection>

      <SharedReportSection
        id={`${cycleKey}-ta-drivers`}
        title="TA Drivers"
        description="Driverii comportamentali care se pot activa în situații de stres."
      >
        <AveragePanel
          title="Media procentuală"
          count={aggregate.driver_count}
          items={aggregate.driver_averages}
          min={driverScale.min}
          max={driverScale.max}
          suffix={driverScale.suffix}
          empty={reportScaleEmptyCopy(
            aggregate.driver_scale,
            "Nu există încă rezultate TA scorate pentru acest proiect.",
          )}
        />
        <div>
          <h3 className="text-lg font-semibold text-foreground">Driverii întâlniți cel mai des</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
            Fiecare persoană apare o singură dată în fiecare grafic, după driverul cu scorul cel mai mare și apoi după următorul.
          </p>
        </div>
        <div className="grid gap-5 lg:grid-cols-2">
          <ChartPanel title="Primul driver dominant">
            <ParticipantFrequencyPie
              title="Primul driver dominant"
              data={aggregate.driver_rank_summary.first_rank.map((item) => ({
                ...item,
                color: item.color ?? undefined,
              }))}
              totalPeople={aggregate.driver_rank_summary.total_people}
              emptyLabel={driverPieEmptyLabel}
            />
          </ChartPanel>
          <ChartPanel title="Al doilea driver dominant">
            <ParticipantFrequencyPie
              title="Al doilea driver dominant"
              data={aggregate.driver_rank_summary.second_rank.map((item) => ({
                ...item,
                color: item.color ?? undefined,
              }))}
              totalPeople={aggregate.driver_rank_summary.total_people}
              emptyLabel={driverPieEmptyLabel}
            />
          </ChartPanel>
        </div>
        {(aggregate.driver_rank_summary.first_rank_tie_breaks > 0
          || aggregate.driver_rank_summary.second_rank_tie_breaks > 0) ? (
          <p className="text-sm leading-6 text-muted-foreground">
            La egalitate am păstrat ordinea din chestionar:{" "}
            {tieBreakLabel(aggregate.driver_rank_summary.first_rank_tie_breaks)} pentru primul driver și{" "}
            {tieBreakLabel(aggregate.driver_rank_summary.second_rank_tie_breaks)} pentru al doilea.
          </p>
        ) : null}
        {aggregate.driver_rank_summary.insufficient_driver_score_count > 0 ? (
          <p className="text-sm leading-6 text-muted-foreground">
            {aggregate.driver_rank_summary.insufficient_driver_score_count === 1
              ? "O persoană nu a putut fi inclusă, deoarece nu are un rezultat TA finalizat cu suficiente scoruri pentru a stabili primii doi driveri."
              : `${aggregate.driver_rank_summary.insufficient_driver_score_count} persoane nu au putut fi incluse, deoarece nu au un rezultat TA finalizat cu suficiente scoruri pentru a stabili primii doi driveri.`}
          </p>
        ) : null}
      </SharedReportSection>

      <SharedReportSection
        id={`${cycleKey}-leadership`}
        title="Echipa de leadership"
        description="Deschide raportul unei persoane pentru profilul și rezultatele sale complete."
      >
        <LeadershipMembers
          members={aggregate.leadership_members}
          reportsPath={reportsPath}
          query={reportQuery}
        />
      </SharedReportSection>

      <footer className="border-t border-border pt-5 text-sm text-muted-foreground">
        {participantCount} {participantCount === 1 ? "participant" : "participanți"} în proiect ·{" "}
        {aggregate.completion_rate}% completat
      </footer>
    </article>
  );
}

function cycleStatusLabel(status: AssessmentCycle["status"]): string {
  if (status === "active") return "În desfășurare";
  if (status === "closed") return "Finalizată";
  return "În pregătire";
}

function AveragePanel({
  title,
  count,
  items,
  min = 0,
  max,
  suffix = "",
  empty = "Rezultatele apar după completare și scorare.",
  note,
}: {
  title: string;
  count: number;
  items: ReportAverage[];
  min?: number;
  max: number;
  suffix?: string;
  empty?: string;
  note?: string | null;
}) {
  return (
    <Card asChild className="gap-0 px-5 [--card-spacing:--spacing(5)]">
      <article>
        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          <h3 className="min-w-0 text-lg font-semibold text-foreground">{title}</h3>
          <span className="shrink-0 text-xs font-semibold text-muted-foreground">
            {count} {count === 1 ? "răspuns" : "răspunsuri"}
          </span>
        </div>
        {items.length > 0 ? (
          <div className="mt-5 grid gap-4">
            {items.map((item) => (
              <div key={item.id}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="min-w-0 font-semibold text-foreground">{item.label}</span>
                  <span className="font-mono font-semibold tabular-nums text-foreground">{item.avg}{suffix}</span>
                </div>
                <ScaledBar value={item.avg} min={min} max={max} />
                {item.interpretation ? (
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{item.interpretation}</p>
                ) : null}
              </div>
            ))}
            {note ? <p className="text-xs leading-5 text-muted-foreground">{note}</p> : null}
          </div>
        ) : (
          <p className="mt-5 text-sm text-muted-foreground">{empty}</p>
        )}
      </article>
    </Card>
  );
}

function ChartPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card asChild className="gap-0 px-5 [--card-spacing:--spacing(5)]">
      <article>
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <div className="mt-5">{children}</div>
      </article>
    </Card>
  );
}

function LeadershipMembers({
  members,
  reportsPath,
  query,
}: {
  members: LeadershipMemberSummary[];
  reportsPath: string;
  query: string;
}) {
  if (members.length === 0) {
    return (
      <Card asChild className="px-5 text-muted-foreground [--card-spacing:--spacing(6)]">
        <p>Nu există încă membri de leadership în organigramă.</p>
      </Card>
    );
  }
  return (
    <Card className="gap-0 divide-y divide-border py-0">
      {members.map((member) => (
        <Link
          key={member.participant_profile_id}
          href={`${reportsPath}/leadership/${member.participant_profile_id}${query}`}
          className="group flex items-center justify-between gap-4 px-5 py-4 transition-colors hover:bg-muted/35 focus-visible:bg-muted/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/45"
        >
          <span>
            <span className="block font-semibold text-foreground group-hover:text-primary">{member.full_name}</span>
            <span className="mt-1 block text-sm text-muted-foreground">{member.position || "Membru leadership"}</span>
          </span>
          <ArrowRightIcon aria-hidden="true" className="size-4 text-muted-foreground group-hover:text-primary" strokeWidth={1.8} />
        </Link>
      ))}
    </Card>
  );
}

function HierarchyDiagnosticsPanel({
  title,
  description,
  issues,
}: {
  title: string;
  description: string;
  issues: ReportHierarchyIssue[];
}) {
  return (
    <Alert className="status-warning px-5 py-4">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        {description}
        {issues.length > 0 ? (
          <ul className="mt-2 list-disc pl-5">
            {issues.slice(0, 4).map((issue, index) => (
              <li key={`${issue.code}-${issue.participant_id ?? index}`}>{issue.message}</li>
            ))}
          </ul>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

function ScoringAvailabilityAlert({
  pending,
  failed,
  orphaned,
}: {
  pending: number;
  failed: number;
  orphaned: number;
}) {
  if (pending + failed + orphaned === 0) return null;
  const title = orphaned > 0
    ? "Unele rezultate nu pot fi asociate cu evaluarea"
    : failed > 0
      ? "Unele rezultate nu au putut fi pregătite"
      : "Unele rezultate sunt încă în curs de pregătire";
  return (
    <Alert className="status-warning px-5 py-4">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <ul className="list-disc pl-5">
          {pending > 0 ? (
            <li>{pending === 1 ? "Un răspuns trimis este încă în curs de procesare." : `${pending} răspunsuri trimise sunt încă în curs de procesare.`}</li>
          ) : null}
          {failed > 0 ? (
            <li>{failed === 1 ? "Un răspuns este păstrat, dar rezultatul nu a putut fi pregătit. Participantul nu trebuie să îl completeze din nou." : `${failed} răspunsuri sunt păstrate, dar rezultatele nu au putut fi pregătite. Participanții nu trebuie să le completeze din nou.`}</li>
          ) : null}
          {orphaned > 0 ? (
            <li>{orphaned === 1 ? "Un răspuns trimis este păstrat, dar nu are încă un rezultat asociat." : `${orphaned} răspunsuri trimise sunt păstrate, dar nu au încă rezultate asociate.`}</li>
          ) : null}
        </ul>
      </AlertDescription>
    </Alert>
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
