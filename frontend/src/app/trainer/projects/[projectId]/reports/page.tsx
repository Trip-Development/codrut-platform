import type { ReactNode } from "react";

import Link from "next/link";

import { getCompanyReportAggregate, type CompanyAssignment, type CompanyParticipant } from "@/api/companies";
import { inviteQuestionnaireLabel } from "@/api/invites";
import { getServerApiRequestOptions } from "@/api/server-request";
import type { ScoringResultRecord } from "@/api/trainer";
import {
  buildReportAggregation,
  driverLabels,
  findReportAggregationMismatches,
  type ReportAverage,
  type TeamLens,
} from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { EmptyState } from "@/components/presentation/empty-state";
import { DonutChart, ScaledBar } from "@/components/reports/native-charts";
import { getProjectReportData } from "../project-data";

const MIN_REPORT_COHORT_SIZE = 3;
const distressDriverKeys = new Set(["distress_drivers", "distress_drivers_en"]);

export default async function ProjectReportsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const { project, participants, assignments } = await getProjectReportData(projectId, requestOptions);
  const aggregate = await getCompanyReportAggregate(project.company_id, requestOptions, { projectId: project.id });
  const resultMap = new Map(
    aggregate.results.map((result) => [result.assignment_id, result as ScoringResultRecord]),
  );
  const report = buildReportAggregation(assignments, resultMap, participants);
  const mismatches = findReportAggregationMismatches(aggregate, report);
  const totalAssigned = aggregate.total_assigned;
  const totalCompleted = aggregate.total_completed;
  const completionRate = totalAssigned > 0 ? Math.round((totalCompleted / totalAssigned) * 100) : 0;
  const pending = Math.max(totalAssigned - totalCompleted, 0);
  const lencioniAverages = aggregate.lencioni_averages;
  const driverAverages = report.driverAverages;
  const boss360Averages = aggregate.boss_360_averages;
  const lencioniCount = aggregate.lencioni_count;
  const driverCount = aggregate.driver_count;
  const boss360Count = aggregate.boss_360_count;
  const commonDriverResults = driverAverages.filter((item) => item.avg > 50);
  const reportsPath = `/trainer/projects/${projectId}/reports`;

  if (mismatches.length > 0) {
    return (
      <EmptyState
        title="Rezultatele proiectului nu sunt gata pentru afișare."
        description="Totalurile și agregatele de scor nu se aliniază între sursele disponibile. Verifică procesarea rezultatelor înainte de a reveni aici."
      />
    );
  }

  if (report.hierarchyAmbiguous) {
    return (
      <EmptyState
        title="Structura echipelor are nume ambigue."
        description={report.hierarchyAmbiguityMessage ?? "Există nume duplicate folosite în relațiile de raportare. Corectează rosterul înainte de rezultate."}
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
          actionLabel="Vezi pe echipe"
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
          actionLabel="Vezi detalii"
        />
      </section>

      {((report.pcmBaseDistribution.length > 0 && report.pcmBaseCount >= MIN_REPORT_COHORT_SIZE) ||
        (report.pcmPhaseDistribution.length > 0 && report.pcmPhaseCount >= MIN_REPORT_COHORT_SIZE) ||
        (commonDriverResults.length > 0 && driverCount >= MIN_REPORT_COHORT_SIZE)) ? (
        <section className="grid gap-5 lg:grid-cols-3">
          {report.pcmBaseCount >= MIN_REPORT_COHORT_SIZE ? (
            <ChartPanel title="PCM bază">
              <DonutChart title="Distribuție PCM bază" data={report.pcmBaseDistribution} />
            </ChartPanel>
          ) : null}
          {report.pcmPhaseCount >= MIN_REPORT_COHORT_SIZE ? (
            <ChartPanel title="PCM fază">
              <DonutChart title="Distribuție PCM fază" data={report.pcmPhaseDistribution} />
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
            <span className="mt-2 inline-flex rounded-full border border-burgundy/18 bg-burgundy/10 px-3 py-1.5 text-xs font-bold text-burgundy transition group-hover:bg-burgundy group-hover:text-white">
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

function SuppressedTeamSection({ title, count }: { title: string; count: number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">{title}</p>
        <span className="text-xs font-semibold text-foreground/52">{formatResponseCount(count)}</span>
      </div>
      <p className="mt-3 text-xs font-semibold leading-5 text-foreground/58">
        Ascuns până există cel puțin {MIN_REPORT_COHORT_SIZE} răspunsuri.
      </p>
    </div>
  );
}

export function LencioniTeamBreakdown({ teams, overviewHref }: { teams: TeamLens[]; overviewHref: string }) {
  const teamsWithData = teams.filter((team) => team.lencioniCount > 0);

  return (
    <section id="lencioni-pe-echipe" className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <div className="flex flex-col gap-3 border-b border-[var(--border)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold text-burgundy/75">Lencioni pe echipe</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Detaliu pe structura proiectului</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/58">
            Afișăm scorurile pe echipe doar când există cel puțin {MIN_REPORT_COHORT_SIZE} răspunsuri pentru instrument.
          </p>
        </div>
        <Link
          href={overviewHref}
          className="tap-soft inline-flex justify-center rounded-full border border-[var(--border)] bg-surface-muted px-4 py-2 text-sm font-bold text-foreground/70 hover:bg-surface"
        >
          Înapoi la sumar
        </Link>
      </div>

      {teamsWithData.length === 0 ? (
        <p className="py-8 text-center text-sm text-foreground/52">Nu există încă rezultate Lencioni pe echipe.</p>
      ) : (
        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          {teamsWithData.map((team) => (
            <article key={team.id} className="rounded-xl border border-[var(--border)] bg-background p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-foreground">{team.name}</h3>
                  <p className="mt-1 text-xs text-foreground/52">
                    {team.memberCount} membri · {formatResponseCount(team.lencioniCount)} Lencioni
                  </p>
                </div>
                <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy">
                  {team.completionRate}%
                </span>
              </div>
              <div className="mt-4">
                {team.lencioniCount >= MIN_REPORT_COHORT_SIZE ? (
                  <TeamAverages
                    title="Lencioni"
                    count={team.lencioniCount}
                    items={team.lencioniAverages}
                    max={10}
                    valueLabel="0-10"
                  />
                ) : (
                  <SuppressedTeamSection title="Lencioni" count={team.lencioniCount} />
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

type DriverIndividualResult = {
  assignmentId: string;
  participantName: string;
  participantEmail: string;
  targetLabel: string;
  submittedAt: string | null;
  scores: ReportAverage[];
};

export function DriverDetailBreakdown({
  teams,
  individuals,
  overviewHref,
}: {
  teams: TeamLens[];
  individuals: DriverIndividualResult[];
  overviewHref: string;
}) {
  const teamsWithDriverData = teams.filter((team) => team.driverCount > 0);

  return (
    <section id="driveri-detaliu" className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <div className="flex flex-col gap-3 border-b border-[var(--border)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold text-burgundy/75">Driveri de distres</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Detaliu pe echipe și persoane</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/58">
            Driverii sunt autoevaluări individuale. Pe echipe afișăm agregate doar când există cel puțin {MIN_REPORT_COHORT_SIZE} răspunsuri; pe persoane afișăm scoruri calculate, nu răspunsurile brute.
          </p>
        </div>
        <Link
          href={overviewHref}
          className="tap-soft inline-flex justify-center rounded-full border border-[var(--border)] bg-surface-muted px-4 py-2 text-sm font-bold text-foreground/70 hover:bg-surface"
        >
          Înapoi la sumar
        </Link>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(24rem,0.9fr)]">
        <div>
          <div className="mb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">Pe echipe</p>
            <p className="mt-1 text-sm text-foreground/58">Agregate utile pentru comparații între structurile proiectului.</p>
          </div>
          {teamsWithDriverData.length === 0 ? (
            <p className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-6 text-center text-sm text-foreground/52">
              Nu există încă rezultate de driveri asociate echipelor proiectului.
            </p>
          ) : (
            <div className="space-y-4">
              {teamsWithDriverData.map((team) => (
                <article key={team.id} className="rounded-xl border border-[var(--border)] bg-background p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-foreground">{team.name}</h3>
                      <p className="mt-1 text-xs text-foreground/52">
                        {team.memberCount} membri · {formatResponseCount(team.driverCount)} driveri
                      </p>
                    </div>
                    <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy">
                      {team.completionRate}%
                    </span>
                  </div>
                  <div className="mt-4">
                    {team.driverCount >= MIN_REPORT_COHORT_SIZE ? (
                      <TeamAverages
                        title="Driveri de distres"
                        count={team.driverCount}
                        items={team.driverAverages}
                        max={100}
                        suffix="%"
                        description="Toți driverii sunt afișați; interpretarea apare doar pentru valorile peste 50%."
                      />
                    ) : (
                      <SuppressedTeamSection title="Driveri de distres" count={team.driverCount} />
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="mb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">Pe persoane</p>
            <p className="mt-1 text-sm text-foreground/58">Scoruri individuale calculate pentru debrief, fără răspunsuri brute.</p>
          </div>
          {individuals.length === 0 ? (
            <p className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-6 text-center text-sm text-foreground/52">
              Nu există încă autoevaluări de driveri scorate.
            </p>
          ) : (
            <div className="space-y-4">
              {individuals.map((item) => (
                <article key={item.assignmentId} className="rounded-xl border border-[var(--border)] bg-background p-4">
                  <div className="flex flex-col gap-1 border-b border-[var(--border)] pb-3">
                    <h3 className="font-semibold text-foreground">{item.participantName}</h3>
                    <p className="text-xs text-foreground/52">{item.participantEmail}</p>
                    <p className="text-xs font-semibold text-foreground/48">
                      {item.targetLabel} · {formatDate(item.submittedAt)}
                    </p>
                  </div>
                  <div className="mt-3 space-y-3">
                    {item.scores.map((score) => (
                      <div key={score.id}>
                        <div className="flex justify-between gap-3 text-xs font-semibold text-foreground/68">
                          <span>{score.label}</span>
                          <span className="shrink-0">{score.avg}%</span>
                        </div>
                        {score.interpretation ? (
                          <p className="mt-1 text-xs leading-5 text-foreground/52">
                            {score.range_label ? `${score.range_label}: ` : ""}
                            {score.interpretation}
                          </p>
                        ) : null}
                        <ScaledBar value={score.avg} max={100} />
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
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

function TeamAverages({
  title,
  count,
  items,
  max,
  suffix = "",
  valueLabel,
  description,
}: {
  title: string;
  count: number;
  items: ReportAverage[];
  max: number;
  suffix?: string;
  valueLabel?: string;
  description?: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">{title}</p>
        <span className="text-xs font-semibold text-foreground/52">{formatResponseCount(count)}</span>
      </div>
      {description ? <p className="mt-2 text-xs leading-5 text-foreground/52">{description}</p> : null}
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-foreground/52">Nu există încă rezultate scorate pentru echipă.</p>
      ) : (
        <div className="mt-3 space-y-3">
          {items.map((item) => (
            <div key={item.id}>
              <div className="flex justify-between gap-3 text-xs font-semibold text-foreground/68">
                <span>{item.label}</span>
                <span className="shrink-0">
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
    </div>
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

const completedStatusesForReports = new Set(["submitted", "validated", "scored"]);

export function buildDriverIndividualResults(
  assignments: CompanyAssignment[],
  resultMap: Map<string, ScoringResultRecord>,
  participants: CompanyParticipant[],
): DriverIndividualResult[] {
  const participantById = new Map(participants.map((participant) => [participant.id, participant]));

  return assignments
    .filter((assignment) => completedStatusesForReports.has(assignment.status) && distressDriverKeys.has(assignment.questionnaire_key))
    .flatMap((assignment) => {
      const result = resultMap.get(assignment.id);
      if (!result?.scores) return [];
      const participant = participantById.get(assignment.respondent_profile_id);
      const scores = Object.entries(driverLabels).map(([id, label]) => {
        const score = extractNumericScore(result.scores[id]);
        return {
          id,
          label,
          avg: score,
          ...(score > 50
            ? {
                interpretation: "Driver prezent peste pragul de atenție; merită explorat în debrief.",
                range_label: ">50",
              }
            : {
                interpretation: null,
                range_label: null,
              }),
        };
      });

      return [
        {
          assignmentId: assignment.id,
          participantName: participant?.full_name ?? "Participant necunoscut",
          participantEmail: participant?.email ?? "Email indisponibil",
          targetLabel: assignment.target_type === "self" ? "Autoevaluare" : "Evaluare individuală",
          submittedAt: assignment.submitted_at,
          scores,
        },
      ];
    })
    .sort((first, second) => (second.submittedAt ?? "").localeCompare(first.submittedAt ?? ""));
}

function extractNumericScore(value: unknown): number {
  const raw = typeof value === "object" && value !== null && "score" in value ? (value as { score?: unknown }).score : value;
  if (typeof raw === "number" && Number.isFinite(raw)) return Number(raw.toFixed(1));
  if (typeof raw === "string" && raw.trim() !== "") {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? Number(parsed.toFixed(1)) : 0;
  }
  return 0;
}
