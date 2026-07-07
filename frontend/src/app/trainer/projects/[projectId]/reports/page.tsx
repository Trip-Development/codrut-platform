import type { ReactNode } from "react";

import Link from "next/link";

import { getCompanyReportAggregate, type ReportHierarchyIssue } from "@/api/companies";
import { inviteQuestionnaireLabel } from "@/api/invites";
import { getServerApiRequestOptions } from "@/api/server-request";
import {
  type ReportAverage,
} from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { EmptyState } from "@/components/presentation/empty-state";
import { DonutChart, ScaledBar } from "@/components/reports/native-charts";
import { getProjectReportData } from "../project-data";
import { MIN_REPORT_COHORT_SIZE } from "./report-detail-sections";

export default async function ProjectReportsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const { project, participants, assignments } = await getProjectReportData(projectId, requestOptions);
  const aggregate = await getCompanyReportAggregate(project.company_id, requestOptions, { projectId: project.id });
  const totalAssigned = aggregate.total_assigned;
  const totalCompleted = aggregate.total_completed;
  const completionRate = aggregate.completion_rate;
  const pending = Math.max(totalAssigned - totalCompleted, 0);
  const lencioniAverages = aggregate.lencioni_averages;
  const driverAverages = aggregate.driver_averages;
  const boss360Averages = aggregate.boss_360_averages;
  const lencioniCount = aggregate.lencioni_count;
  const driverCount = aggregate.driver_count;
  const boss360Count = aggregate.boss_360_count;
  const pcmBaseDistribution = aggregate.pcm_base_distribution.map((item) => ({ ...item, color: item.color ?? undefined }));
  const pcmPhaseDistribution = aggregate.pcm_phase_distribution.map((item) => ({ ...item, color: item.color ?? undefined }));
  const commonDriverResults = driverAverages.filter((item) => item.avg > 50);
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
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <ReportMetric label="Rata completare" value={`${completionRate}%`} />
        <ReportMetric label="Asignări" value={totalAssigned} />
        <ReportMetric label="Răspunsuri" value={totalCompleted} tone="success" />
        <ReportMetric label="În așteptare" value={pending} tone="warning" />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <OverviewCard title="Proiect" label={project.name} detail={`${participants.length} participanți în rosterul proiectului`} />
        <OverviewCard title="Rezultate scorate" label={`${lencioniCount + driverCount + boss360Count}`} detail="Lencioni, PCM, distress și 360 pentru trainer." />
        <OverviewCard title="Vizibilitate" label="Trainer" detail="Pagina este în zona trainer; rezultatele participant-facing rămân restricționate." />
      </section>

      {aggregate.hierarchy_issues.length > 0 ? <HierarchyDiagnosticsPanel issues={aggregate.hierarchy_issues} /> : null}

      <section className="grid gap-5 xl:grid-cols-3">
        <ReportPanel
          title="Lencioni"
          count={lencioniCount}
          items={lencioniAverages}
          max={10}
          valueLabel="0-10"
          legend={lencioniLegend}
          suppressed={isSmallCohort(lencioniCount)}
          actionHref={`${reportsPath}/lencioni`}
          actionLabel="Detalii"
        />
        <ReportPanel
          title="Feedback 360 iCARE"
          count={boss360Count}
          items={boss360Averages}
          suffix="%"
          max={100}
          suppressed={isSmallCohort(boss360Count)}
        />
        <ReportPanel
          title="Driveri de distres"
          count={driverCount}
          items={driverAverages}
          suffix="%"
          max={100}
          description="Toți driverii sunt afișați; interpretarea apare doar peste 50%."
          suppressed={isSmallCohort(driverCount)}
          actionHref={`${reportsPath}/drivers`}
          actionLabel="Detalii"
        />
      </section>

      {((pcmBaseDistribution.length > 0 && aggregate.pcm_base_count >= MIN_REPORT_COHORT_SIZE) ||
        (pcmPhaseDistribution.length > 0 && aggregate.pcm_phase_count >= MIN_REPORT_COHORT_SIZE) ||
        (commonDriverResults.length > 0 && driverCount >= MIN_REPORT_COHORT_SIZE)) ? (
        <section className="grid gap-5 lg:grid-cols-3">
          {aggregate.pcm_base_count >= MIN_REPORT_COHORT_SIZE ? (
            <ChartPanel title="PCM bază">
              <DonutChart title="Distribuție PCM bază" data={pcmBaseDistribution} />
            </ChartPanel>
          ) : null}
          {aggregate.pcm_phase_count >= MIN_REPORT_COHORT_SIZE ? (
            <ChartPanel title="PCM fază">
              <DonutChart title="Distribuție PCM fază" data={pcmPhaseDistribution} />
            </ChartPanel>
          ) : null}
          {driverCount >= MIN_REPORT_COHORT_SIZE ? (
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

      <section className="overflow-hidden rounded-xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <p className="text-xs font-semibold text-burgundy/75">Asignări raportabile</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Status răspunsuri proiect</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted text-xs font-semibold text-foreground/50">
              <tr>
                <th className="px-5 py-3">Chestionar</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Trimis</th>
                <th className="px-5 py-3">Scorat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {assignments.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-5 py-6 text-center text-foreground/62">
                    Nu există încă asignări în proiect.
                  </td>
                </tr>
              ) : (
                assignments.map((assignment) => (
                  <tr key={assignment.id}>
                    <td className="px-5 py-4 font-semibold text-foreground">
                      {inviteQuestionnaireLabel(assignment.questionnaire_key)}
                    </td>
                    <td className="px-5 py-4 text-foreground/62">{assignment.status}</td>
                    <td className="px-5 py-4 text-foreground/62">{formatDate(assignment.submitted_at)}</td>
                    <td className="px-5 py-4 text-foreground/62">{formatDate(assignment.scored_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function OverviewCard({ title, label, detail }: { title: string; label: string; detail: string }) {
  return (
    <article className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">{title}</p>
      <h2 className="mt-2 text-lg font-semibold text-foreground">{label}</h2>
      <p className="mt-2 text-sm leading-6 text-foreground/58">{detail}</p>
    </article>
  );
}

function HierarchyDiagnosticsPanel({ issues }: { issues: ReportHierarchyIssue[] }) {
  const visibleIssues = issues.slice(0, 4);
  const hiddenCount = Math.max(issues.length - visibleIssues.length, 0);

  return (
    <section className="rounded-xl border border-amber-300/70 bg-amber-50 px-5 py-4 text-amber-950 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.1em]">Atenție structură</p>
      <h2 className="mt-1 text-base font-semibold">Unele relații de raportare nu au fost mapate în echipe.</h2>
      <ul className="mt-3 space-y-2 text-sm leading-6">
        {visibleIssues.map((issue, index) => (
          <li key={`${issue.code}-${issue.participant_id ?? index}`}>{issue.message}</li>
        ))}
      </ul>
      {hiddenCount > 0 ? (
        <p className="mt-2 text-sm font-semibold">Încă {hiddenCount} diagnostice sunt disponibile în datele raportului.</p>
      ) : null}
    </section>
  );
}

function ReportMetric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  tone?: "neutral" | "success" | "warning";
}) {
  const color = tone === "success" ? "text-emerald-600" : tone === "warning" ? "text-amber-600" : "text-burgundy";
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function ReportPanel({
  title,
  count,
  items,
  suffix = "",
  max,
  valueLabel,
  legend,
  description,
  suppressed,
  actionHref,
  actionLabel,
}: {
  title: string;
  count: number;
  items: ReportAverage[];
  suffix?: string;
  max: number;
  valueLabel?: string;
  legend?: Array<{ range: string; label: string }>;
  description?: string;
  suppressed?: boolean;
  actionHref?: string;
  actionLabel?: string;
}) {
  const content = (
    <>
      <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] pb-3">
        <div>
          <h3 className="font-semibold text-foreground">{title}</h3>
          {actionHref && actionLabel ? (
            <span className="mt-2 inline-flex rounded-full border border-[rgb(230,92,92)] bg-burgundy/10 px-3 py-1.5 text-xs font-bold text-burgundy transition group-hover:bg-burgundy group-hover:text-white">
              {actionLabel}
            </span>
          ) : null}
        </div>
        <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy">{formatResponseCount(count)}</span>
      </div>
      {description ? <p className="mt-3 text-xs leading-5 text-foreground/58">{description}</p> : null}
      {suppressed ? (
        <p className="mt-4 rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-3 text-xs font-semibold leading-5 text-foreground/58">
          Rezultatele sunt ascunse până există cel puțin {MIN_REPORT_COHORT_SIZE} răspunsuri pentru acest instrument.
        </p>
      ) : items.length === 0 ? (
        <p className="py-10 text-center text-sm text-foreground/52">Rezultatele apar după completare și scorare.</p>
      ) : (
        <div className="mt-4 space-y-3">
          {legend ? (
            <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-3 text-xs leading-5 text-foreground/62">
              {legend.map((item) => (
                <p key={item.range}>
                  <strong className="text-foreground">{item.range}:</strong> {item.label}
                </p>
              ))}
            </div>
          ) : null}
          {items.map((item) => (
            <div key={item.id}>
              <div className="flex justify-between text-xs font-semibold text-foreground/68">
                <span>{item.label}</span>
                <span>
                  {item.avg}
                  {suffix}
                  {valueLabel ? ` / ${valueLabel}` : ""}
                </span>
              </div>
              {item.interpretation ? (
                <p className="mt-1 text-xs leading-5 text-foreground/52">
                  {item.range_label ? `${item.range_label}: ` : ""}
                  {item.interpretation}
                </p>
              ) : null}
              <ScaledBar value={item.avg} max={max} />
            </div>
          ))}
        </div>
      )}
    </>
  );

  if (actionHref) {
    return (
      <Link
        href={actionHref}
        className="group block rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-burgundy/30 hover:shadow-md"
      >
        {content}
      </Link>
    );
  }

  return (
    <section className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      {content}
    </section>
  );
}

function ChartPanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <h3 className="mb-4 font-semibold text-foreground">{title}</h3>
      {children}
    </section>
  );
}

const lencioniLegend = [
  { range: "8-9", label: "Disfuncția probabil nu este o problemă." },
  { range: "6-7", label: "Disfuncția poate fi o problemă." },
  { range: "3-5", label: "Disfuncția trebuie probabil abordată." },
];

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ro-RO");
}

function formatResponseCount(count: number): string {
  return count === 1 ? "1 răspuns" : `${count} răspunsuri`;
}

function isSmallCohort(count: number): boolean {
  return count > 0 && count < MIN_REPORT_COHORT_SIZE;
}
