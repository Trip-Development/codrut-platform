import type { ReactNode } from "react";

import Link from "next/link";
import {
  ArrowRightIcon,
} from "lucide-react";

import {
  getCompanyReportComparison,
  getIcareAnswerReview,
  type IcareAnswerReviewRow,
  type ReportDistribution,
  type ReportHierarchyIssue,
} from "@/api/companies";
import { inviteQuestionnaireLabel } from "@/api/invites";
import { getServerApiRequestOptions } from "@/api/server-request";
import {
  type ReportAverage,
} from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { EmptyState } from "@/components/presentation/empty-state";
import { DonutChart, ScaledBar } from "@/components/reports/native-charts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/utils/cn";
import { formatRomanianDate } from "@/utils/date-format";
import { getProjectAssessmentCyclesData, getProjectReportWorkspaceData } from "../project-data";
import { CycleComparisonControls } from "./CycleComparisonControls";
import { ReportPrintButton } from "./ReportPrintButton";
import { buildProjectReportQuery, loadOptionalComparison } from "./report-cycle";

const ASSIGNMENT_STATUS_LABELS: Record<string, string> = {
  assigned: "Asignat",
  invited: "Invitat",
  scored: "Scorat",
  started: "Început",
  submitted: "Trimis",
  validated: "Validat",
  cancelled: "Anulat",
};

export default async function ProjectReportsPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ baseline?: string; cycle?: string }>;
}) {
  const [{ projectId }, query, requestOptions] = await Promise.all([
    params,
    searchParams,
    getServerApiRequestOptions(),
  ]);
  const cycleData = await getProjectAssessmentCyclesData(projectId, requestOptions);
  const cycles = [...cycleData.assessmentCycles].sort((left, right) => left.sequence - right.sequence);
  const comparisonCycle = cycles.find((cycle) => cycle.id === query.cycle)
    ?? cycles.at(-1)
    ?? null;
  const comparisonIndex = comparisonCycle
    ? cycles.findIndex((cycle) => cycle.id === comparisonCycle.id)
    : -1;
  const requestedBaseline = cycles.find((cycle) => cycle.id === query.baseline);
  const baselineCycle = requestedBaseline && comparisonCycle
    && requestedBaseline.sequence < comparisonCycle.sequence
    ? requestedBaseline
    : comparisonIndex > 0
      ? cycles[comparisonIndex - 1]
      : null;
  const scope = { assessmentCycleId: comparisonCycle?.id };
  const { project, participants, assignments, aggregate } = await getProjectReportWorkspaceData(
    projectId,
    requestOptions,
    scope,
  );
  const icareReview = await getIcareAnswerReview(project.company_id, requestOptions, {
    projectId: project.id,
    assessmentCycleId: comparisonCycle?.id,
  });
  const comparisonResult = await loadOptionalComparison(
    baselineCycle && comparisonCycle
      ? () => getCompanyReportComparison(
          project.company_id,
          project.id,
          baselineCycle.id,
          comparisonCycle.id,
          requestOptions,
        )
      : null,
  );
  const comparison = comparisonResult.comparison;
  const baselineAggregate = comparison?.baseline ?? null;
  const totalAssigned = aggregate.total_assigned;
  const totalCompleted = aggregate.total_completed;
  const completionRate = aggregate.completion_rate;
  const pending = Math.max(totalAssigned - totalCompleted, 0);
  const lencioniAverages = aggregate.lencioni_averages;
  const lencioniLegend = Array.from(
    new Map(
      lencioniAverages
        .filter((item) => item.range_label && item.interpretation)
        .map((item) => [
          item.range_label as string,
          { range: item.range_label as string, label: item.interpretation as string },
        ]),
    ).values(),
  );
  const driverAverages = aggregate.driver_averages;
  const boss360Averages = aggregate.boss_360_averages;
  const lencioniCount = aggregate.lencioni_count;
  const driverCount = aggregate.driver_count;
  const boss360Count = aggregate.boss_360_count;
  const pcmBaseDistribution = aggregate.pcm_base_distribution.map((item) => ({ ...item, color: item.color ?? undefined }));
  const pcmPhaseDistribution = aggregate.pcm_phase_distribution.map((item) => ({ ...item, color: item.color ?? undefined }));
  const commonDriverResults = driverAverages.filter((item) => item.avg > 50);
  const reportQuery = buildProjectReportQuery({
    cycle: comparisonCycle?.id,
    baseline: baselineCycle?.id,
  });
  const reportsPath = `/trainer/projects/${projectId}/reports`;

  if (aggregate.hierarchy_ambiguous) {
    return (
      <EmptyState
        title="Structura echipelor are nume ambigue."
        description={aggregate.hierarchy_ambiguity_message ?? "Există nume duplicate folosite în relațiile de raportare. Corectează rosterul înainte de rezultate."}
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {baselineCycle && comparisonCycle ? (
        <CycleComparisonControls
          cycles={cycles}
          baselineCycleId={baselineCycle.id}
          comparisonCycleId={comparisonCycle.id}
        />
      ) : null}
      {comparisonResult.failed ? (
        <Alert className="status-warning px-4 py-3">
          <AlertTitle>Comparația nu s-a încărcat.</AlertTitle>
          <AlertDescription>
            Rezultatele evaluării selectate sunt disponibile. <Link href={`${reportsPath}${reportQuery}`}>Reîncearcă comparația.</Link>
          </AlertDescription>
        </Alert>
      ) : null}
      <section className="flex flex-col gap-5 border-b border-border pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <dl className="flex flex-wrap gap-x-9 gap-y-3" aria-label="Sumar rezultate">
            <ReportSummary label="Completare" value={`${completionRate}%`} />
            <ReportSummary label="Asignări" value={totalAssigned} />
            <ReportSummary label="Răspunsuri" value={totalCompleted} />
            <ReportSummary label="În așteptare" value={pending} warning={pending > 0} />
            <ReportSummary label="Participanți" value={participants.length} />
            <ReportSummary label="Rezultate scorate" value={lencioniCount + driverCount + boss360Count} />
          </dl>
        </div>
        <ReportPrintButton />
      </section>

      {aggregate.hierarchy_issues.length > 0 ? <HierarchyDiagnosticsPanel issues={aggregate.hierarchy_issues} /> : null}

      <section className="grid gap-5 xl:grid-cols-3">
        <ReportPanel
          title="Lencioni"
          count={lencioniCount}
          items={lencioniAverages}
          baselineItems={baselineAggregate?.lencioni_averages}
          baselineLabel={baselineCycle?.name}
          comparisonLabel={comparisonCycle?.name}
          max={10}
          valueLabel="0-10"
          legend={lencioniLegend}
          actionHref={`${reportsPath}/lencioni${reportQuery}`}
          actionLabel="Detalii"
        />
        <ReportPanel
          title="Feedback 360 iCARE"
          count={boss360Count}
          items={boss360Averages}
          baselineItems={baselineAggregate?.boss_360_averages}
          baselineLabel={baselineCycle?.name}
          comparisonLabel={comparisonCycle?.name}
          suffix="%"
          max={100}
        />
        <ReportPanel
          title="Driveri de distres"
          count={driverCount}
          items={driverAverages}
          baselineItems={baselineAggregate?.driver_averages}
          baselineLabel={baselineCycle?.name}
          comparisonLabel={comparisonCycle?.name}
          suffix="%"
          max={100}
          actionHref={`${reportsPath}/drivers${reportQuery}`}
          actionLabel="Detalii"
        />
      </section>

      <IcareAnswerReviewPanel rows={icareReview.rows} />

      {baselineAggregate && baselineCycle && comparisonCycle ? (
        <PcmCycleComparison
          baselineLabel={baselineCycle.name}
          comparisonLabel={comparisonCycle.name}
          baselineBase={baselineAggregate.pcm_base_distribution}
          comparisonBase={pcmBaseDistribution}
          baselinePhase={baselineAggregate.pcm_phase_distribution}
          comparisonPhase={pcmPhaseDistribution}
        />
      ) : null}

      {(pcmBaseDistribution.length > 0 ||
        pcmPhaseDistribution.length > 0 ||
        commonDriverResults.length > 0) ? (
        <section className="grid gap-5 lg:grid-cols-3">
          {pcmBaseDistribution.length > 0 ? (
            <ChartPanel title="PCM bază">
              <DonutChart title="Distribuție PCM bază" data={pcmBaseDistribution} />
            </ChartPanel>
          ) : null}
          {pcmPhaseDistribution.length > 0 ? (
            <ChartPanel title="PCM fază">
              <DonutChart title="Distribuție PCM fază" data={pcmPhaseDistribution} />
            </ChartPanel>
          ) : null}
          {commonDriverResults.length > 0 ? (
            <ChartPanel title="Driveri comuni">
              <DonutChart
                title="Driveri de distres peste prag"
                data={commonDriverResults.map((item) => ({ id: item.id, label: item.label, value: item.avg }))}
                emptyLabel="Niciun driver peste 50%."
              />
            </ChartPanel>
          ) : null}
        </section>
      ) : null}

      <section className={reportSurfaceClassName({ gapless: true })}>
        <div className={reportHeaderClassName({ className: "py-4" })}>
          <div>
            <h2 className="text-xl font-medium leading-snug text-foreground">Status răspunsuri</h2>
          </div>
        </div>
        <Separator />
        <div className="px-0">
          <div className="overflow-x-auto">
            <table className="min-w-[56rem] w-full border-collapse text-left text-sm">
              <thead className="bg-muted/45 text-xs font-semibold text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Chestionar</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Trimis</th>
                  <th className="px-4 py-3">Scorat</th>
                </tr>
              </thead>
              <tbody>
                {assignments.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-5 py-8 text-center text-sm font-medium text-muted-foreground">
                      Nu există încă asignări în proiect.
                    </td>
                  </tr>
                ) : (
                  assignments.map((assignment) => (
                    <tr key={assignment.id} className="border-t hover:bg-muted/35">
                      <td className="px-4 py-3 font-semibold text-foreground">
                        {inviteQuestionnaireLabel(assignment.questionnaire_key)}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {ASSIGNMENT_STATUS_LABELS[assignment.status] ?? assignment.status}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{formatDate(assignment.submitted_at)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{formatDate(assignment.scored_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}

function ReportSummary({
  label,
  value,
  warning = false,
}: {
  label: string;
  value: string | number;
  warning?: boolean;
}) {
  return (
    <div className="min-w-20">
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className={cn("mt-1 text-2xl font-semibold tabular-nums text-foreground", warning && "text-warning-ink")}>{value}</dd>
    </div>
  );
}

function HierarchyDiagnosticsPanel({ issues }: { issues: ReportHierarchyIssue[] }) {
  const visibleIssues = issues.slice(0, 4);
  const hiddenCount = Math.max(issues.length - visibleIssues.length, 0);

  return (
    <Alert className="status-warning px-5 py-4">
      <AlertTitle className="text-base font-semibold">
        Unele relații de raportare nu au fost mapate în echipe.
      </AlertTitle>
      <AlertDescription className="text-foreground/80">
        <ul className="mt-2 grid gap-2 text-sm leading-6 md:grid-cols-2">
          {visibleIssues.map((issue, index) => (
            <li key={`${issue.code}-${issue.participant_id ?? index}`}>{issue.message}</li>
          ))}
        </ul>
        {hiddenCount > 0 ? (
          <p className="mt-2 text-sm font-semibold">Încă {hiddenCount} diagnostice sunt disponibile în datele raportului.</p>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

function ReportPanel({
  title,
  count,
  items,
  baselineItems,
  baselineLabel,
  comparisonLabel,
  suffix = "",
  max,
  valueLabel,
  legend,
  description,
  actionHref,
  actionLabel,
}: {
  title: string;
  count: number;
  items: ReportAverage[];
  baselineItems?: ReportAverage[];
  baselineLabel?: string;
  comparisonLabel?: string;
  suffix?: string;
  max: number;
  valueLabel?: string;
  legend?: Array<{ range: string; label: string }>;
  description?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  const content = (
    <>
      <div className={reportHeaderClassName({ className: "py-4 has-[.report-panel-action]:grid-cols-[1fr_auto]" })}>
        <div>
          <h2 className={reportTitleClassName()}>{title}</h2>
          {actionHref && actionLabel ? (
            <span className="mt-2 inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-full border border-border px-2 py-0.5 text-xs font-semibold whitespace-nowrap text-foreground transition-[background-color,border-color,color] group-hover:bg-primary group-hover:text-primary-foreground">
              {actionLabel}
              <ArrowRightIcon aria-hidden="true" className="size-3" strokeWidth={1.8} />
            </span>
          ) : null}
        </div>
        <div className="report-panel-action col-start-2 row-span-2 row-start-1 self-start justify-self-end">
          <span className={responseBadgeClassName}>{formatResponseCount(count)}</span>
        </div>
      </div>
      <Separator />
      <div className={cn(reportContentClassName(), "py-4")}>
        {description ? <p className="text-xs leading-5 text-muted-foreground">{description}</p> : null}
        {items.length === 0 && (!baselineItems || baselineItems.length === 0) ? (
          <p className="py-10 text-center text-sm text-muted-foreground">Rezultatele apar după completare și scorare.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {legend ? (
              <div className="rounded-md border bg-muted/45 p-3 text-xs leading-5 text-muted-foreground">
                {legend.map((item) => (
                  <p key={item.range}>
                    <strong className="text-foreground">{item.range}:</strong> {item.label}
                  </p>
                ))}
              </div>
            ) : null}
            {mergeReportAverages(items, baselineItems).map(({ current, baseline }) => {
              const item = current ?? baseline;
              if (!item) return null;
              return (
              <div key={item.id}>
                <div className="flex justify-between text-xs font-semibold text-muted-foreground">
                  <span>{item.label}</span>
                  <span>
                    {current ? `${current.avg}${suffix}${valueLabel ? ` / ${valueLabel}` : ""}` : "În așteptare"}
                  </span>
                </div>
                {item.interpretation ? (
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    {item.range_label ? `${item.range_label}: ` : ""}
                    {item.interpretation}
                  </p>
                ) : null}
                {baselineItems ? (
                  <div className="mt-2 grid gap-1.5">
                    <ComparisonBar
                      label={baselineLabel ?? "Referință"}
                      value={baseline?.avg}
                      max={max}
                      tone="baseline"
                      suffix={suffix}
                    />
                    <ComparisonBar
                      label={comparisonLabel ?? "Comparație"}
                      value={current?.avg}
                      max={max}
                      tone="comparison"
                      suffix={suffix}
                    />
                  </div>
                ) : (
                  <ScaledBar value={item.avg} max={max} />
                )}
              </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );

  if (actionHref) {
    return (
      <Link href={actionHref} className={reportSurfaceClassName({ className: "group gap-0 py-0 transition hover:border-primary/35" })}>
        {content}
      </Link>
    );
  }

  return (
    <section className={reportSurfaceClassName({ gapless: true })}>
      {content}
    </section>
  );
}

function mergeReportAverages(
  currentItems: ReportAverage[],
  baselineItems: ReportAverage[] = [],
): Array<{ current?: ReportAverage; baseline?: ReportAverage }> {
  const ids = [...new Set([...baselineItems.map((item) => item.id), ...currentItems.map((item) => item.id)])];
  const currentById = new Map(currentItems.map((item) => [item.id, item]));
  const baselineById = new Map(baselineItems.map((item) => [item.id, item]));
  return ids.map((id) => ({ current: currentById.get(id), baseline: baselineById.get(id) }));
}

function ComparisonBar({
  label,
  value,
  max,
  tone,
  suffix,
}: {
  label: string;
  value?: number;
  max: number;
  tone: "baseline" | "comparison";
  suffix: string;
}) {
  const width = value === undefined ? 0 : Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
      <span className="truncate">{label}</span>
      <span className="tabular-nums">{value === undefined ? "În așteptare" : `${value}${suffix}`}</span>
      <div className="col-span-2 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <div
          className={cn("h-full rounded-full", tone === "baseline" ? "bg-zinc-500" : "bg-burgundy")}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function PcmCycleComparison({
  baselineLabel,
  comparisonLabel,
  baselineBase,
  comparisonBase,
  baselinePhase,
  comparisonPhase,
}: {
  baselineLabel: string;
  comparisonLabel: string;
  baselineBase: ReportDistribution[];
  comparisonBase: ReportDistribution[];
  baselinePhase: ReportDistribution[];
  comparisonPhase: ReportDistribution[];
}) {
  return (
    <section className={reportSurfaceClassName({ gapless: true })}>
      <div className={reportHeaderClassName({ className: "py-4" })}>
        <h2 className={reportTitleClassName()}>Evoluție PCM</h2>
      </div>
      <Separator />
      <div className="grid gap-6 px-4 py-5 lg:grid-cols-2">
        <PcmDistributionComparison
          title="Bază PCM"
          baselineLabel={baselineLabel}
          comparisonLabel={comparisonLabel}
          baseline={baselineBase}
          comparison={comparisonBase}
        />
        <PcmDistributionComparison
          title="Fază PCM"
          baselineLabel={baselineLabel}
          comparisonLabel={comparisonLabel}
          baseline={baselinePhase}
          comparison={comparisonPhase}
        />
      </div>
    </section>
  );
}

function PcmDistributionComparison({
  title,
  baselineLabel,
  comparisonLabel,
  baseline,
  comparison,
}: {
  title: string;
  baselineLabel: string;
  comparisonLabel: string;
  baseline: ReportDistribution[];
  comparison: ReportDistribution[];
}) {
  const rows = mergeDistributions(baseline, comparison);
  const max = Math.max(1, ...rows.flatMap((row) => [row.baseline?.value ?? 0, row.comparison?.value ?? 0]));

  return (
    <div>
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">În așteptarea rezultatelor.</p>
      ) : (
        <div className="mt-3 grid gap-4">
          {rows.map((row) => (
            <div key={row.id}>
              <p className="mb-2 text-xs font-semibold text-foreground">{row.label}</p>
              <div className="grid gap-1.5">
                <ComparisonBar
                  label={baselineLabel}
                  value={row.baseline?.value}
                  max={max}
                  tone="baseline"
                  suffix=""
                />
                <ComparisonBar
                  label={comparisonLabel}
                  value={row.comparison?.value}
                  max={max}
                  tone="comparison"
                  suffix=""
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function mergeDistributions(
  baseline: ReportDistribution[],
  comparison: ReportDistribution[],
): Array<{ id: string; label: string; baseline?: ReportDistribution; comparison?: ReportDistribution }> {
  const ids = [...new Set([...baseline.map((item) => item.id), ...comparison.map((item) => item.id)])];
  const baselineById = new Map(baseline.map((item) => [item.id, item]));
  const comparisonById = new Map(comparison.map((item) => [item.id, item]));
  return ids.map((id) => {
    const baselineItem = baselineById.get(id);
    const comparisonItem = comparisonById.get(id);
    return {
      id,
      label: comparisonItem?.label ?? baselineItem?.label ?? id,
      baseline: baselineItem,
      comparison: comparisonItem,
    };
  });
}

function ChartPanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={reportSurfaceClassName()}>
      <div className={reportHeaderClassName()}>
        <h2 className={reportTitleClassName()}>{title}</h2>
      </div>
      <div className={reportContentClassName()}>{children}</div>
    </section>
  );
}

function IcareAnswerReviewPanel({ rows }: { rows: IcareAnswerReviewRow[] }) {
  const csvHref = buildIcareReviewCsvHref(rows);
  return (
    <section id="icare-review" className="overflow-hidden border-y border-border bg-surface">
      <div className="flex flex-col gap-3 border-b border-[var(--border)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Răspunsuri individuale iCARE</h2>
        </div>
        <a
          href={csvHref}
          download="icare-raspunsuri-individuale.csv"
          className="inline-flex items-center justify-center rounded-md border border-burgundy/25 px-4 py-2 text-sm font-semibold text-burgundy transition hover:bg-burgundy hover:text-white"
        >
          Export CSV
        </a>
      </div>
      <div className="max-h-[520px] overflow-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="sticky top-0 bg-surface-muted text-xs font-semibold text-foreground/50">
            <tr>
              <th className="px-5 py-3">Participant</th>
              <th className="px-5 py-3">Țintă</th>
              <th className="px-5 py-3">Comportament specific</th>
              <th className="px-5 py-3">Răspuns</th>
              <th className="px-5 py-3">Ce măsurăm</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-foreground/62">
                  Nu există încă răspunsuri iCARE trimise pentru acest proiect.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={`${row.assignment_id}-${row.measurement_id}-${row.statement_id}`}>
                  <td className="px-5 py-4 font-semibold text-foreground">{row.respondent_name}</td>
                  <td className="px-5 py-4 text-foreground/68">{row.target_name ?? "-"}</td>
                  <td className="px-5 py-4 text-foreground/72">{row.statement_label}</td>
                  <td className="px-5 py-4">
                    <p className="font-bold text-foreground">{row.answer_label}</p>
                    {row.answer_description ? (
                      <p className="mt-1 max-w-xl text-xs leading-5 text-foreground/56">{row.answer_description}</p>
                    ) : null}
                  </td>
                  <td className="px-5 py-4 text-foreground/68">
                    <p className="font-semibold text-foreground">{row.measurement_label}</p>
                    <p className="mt-1 text-xs text-foreground/52">{row.section_label}</p>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatDate(value: string | null | undefined): string {
  return formatRomanianDate(value);
}

function formatResponseCount(count: number): string {
  return count === 1 ? "1 răspuns" : `${count} răspunsuri`;
}

function buildIcareReviewCsvHref(rows: IcareAnswerReviewRow[]): string {
  const header = [
    "participant",
    "target",
    "comportament_specific",
    "raspuns",
    "descriere_raspuns",
    "ce_masuram",
    "sectiune",
    "submitted_at",
  ];
  const csv = [
    header,
    ...rows.map((row) => [
      row.respondent_name,
      row.target_name ?? "",
      row.statement_label,
      row.answer_label,
      row.answer_description ?? "",
      row.measurement_label,
      row.section_label,
      row.submitted_at ?? "",
    ]),
  ]
    .map((line) => line.map(csvEscape).join(","))
    .join("\n");
  return `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
}

function csvEscape(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function reportSurfaceClassName({
  className,
  gapless = false,
  size = "default",
}: {
  className?: string;
  gapless?: boolean;
  size?: "default" | "sm";
} = {}): string {
  return cn(
    "flex flex-col gap-(--card-spacing) overflow-hidden rounded-lg border bg-surface py-(--card-spacing) text-sm text-card-foreground [--card-spacing:--spacing(4)]",
    size === "sm" && "[--card-spacing:--spacing(3)]",
    gapless && "gap-0 py-0",
    className,
  );
}

function reportHeaderClassName({ className }: { className?: string } = {}): string {
  return cn(
    "grid auto-rows-min items-start gap-1 rounded-t-lg px-(--card-spacing)",
    className,
  );
}

function reportContentClassName({ className }: { className?: string } = {}): string {
  return cn("px-(--card-spacing)", className);
}

function reportTitleClassName({ className }: { className?: string } = {}): string {
  return cn("font-heading text-base leading-snug font-medium text-foreground", className);
}

const responseBadgeClassName =
  "inline-flex h-5 w-fit shrink-0 items-center justify-center overflow-hidden rounded-full border border-transparent bg-secondary px-2 py-0.5 text-xs font-semibold whitespace-nowrap text-secondary-foreground";
