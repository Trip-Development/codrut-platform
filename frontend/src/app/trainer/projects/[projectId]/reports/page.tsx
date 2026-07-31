import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";

import type {
  IcareCohortSummary,
  LeadershipMemberSummary,
  ReportAverage,
  ReportHierarchyIssue,
} from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { HistoricalIcareNotice } from "@/components/reports/HistoricalIcareNotice";
import { IcarePerspectiveTabs } from "@/components/reports/IcarePerspectiveTabs";
import { ParticipantFrequencyPie, ScaledBar } from "@/components/reports/native-charts";
import { reportScaleEmptyCopy, resolveReportScoreScale } from "@/components/reports/score-scale";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { getProjectAssessmentCyclesData, getProjectReportWorkspaceData } from "../project-data";
import { CycleComparisonControls } from "./CycleComparisonControls";
import { ReportPrintButton } from "./ReportPrintButton";
import { buildProjectReportQuery } from "./report-cycle";

const ICARE_LABELS: Record<IcareCohortSummary["cohort"], string> = {
  direct_team: "Cum vede echipa leadershipul",
  leadership_peers: "Cum se văd colegii din leadership",
  self: "Cum se evaluează liderii",
};

const ICARE_TAB_LABELS: Record<IcareCohortSummary["cohort"], string> = {
  direct_team: "Echipa",
  leadership_peers: "Colegii din leadership",
  self: "Autoevaluare",
};

function tieBreakLabel(count: number): string {
  return count === 1 ? "o departajare" : `${count} departajări`;
}

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
  const selectedCycle = cycles.find((cycle) => cycle.id === query.cycle)
    ?? cycles.filter((cycle) => cycle.status !== "draft").at(-1)
    ?? cycles.at(-1)
    ?? null;
  const { project, participants, aggregate } = await getProjectReportWorkspaceData(
    projectId,
    requestOptions,
    { assessmentCycleId: selectedCycle?.id },
  );
  const reportQuery = buildProjectReportQuery({
    cycle: selectedCycle?.id,
  });
  const reportsPath = `/trainer/projects/${projectId}/reports`;
  const driverPieEmptyLabel = aggregate.driver_rank_summary.insufficient_driver_score_count > 0
    ? "Nu există rezultate TA care pot fi incluse în aceste grafice."
    : undefined;
  const lencioniScale = resolveReportScoreScale(
    aggregate.lencioni_scale,
    { min: 0, max: 10, suffix: "" },
  );
  const driverScale = resolveReportScoreScale(
    aggregate.driver_scale,
    { min: 0, max: 100, suffix: "%" },
  );

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-5 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-burgundy">Rezultate proiect</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-foreground">{project.name}</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {selectedCycle?.name ?? "Toate evaluările"} · {aggregate.total_completed} din {aggregate.total_assigned} răspunsuri
          </p>
        </div>
        <ReportPrintButton />
      </header>

      {cycles.length > 1 && selectedCycle ? (
        <CycleComparisonControls
          cycles={cycles}
          cycleId={selectedCycle.id}
        />
      ) : null}

      <ScoringAvailabilityAlert
        pending={aggregate.reportable_pending_score_count}
        failed={aggregate.reportable_failed_score_count}
        orphaned={aggregate.reportable_orphaned_score_count}
      />

      <ResultSection
        id="lencioni"
        title="Lencioni"
        description="Imaginea de ansamblu a proiectului, cu acces separat la fiecare echipă."
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
            className="inline-flex w-fit items-center gap-2 text-sm font-semibold text-burgundy hover:underline"
          >
            Vezi rezultatele pe echipe
            <ArrowRightIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
          </Link>
        )}
      </ResultSection>

      <ResultSection
        id="icare"
        title="iCARE"
        description="Trei perspective separate, fără a amesteca echipa, colegii și autoevaluarea."
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
        <IcarePerspectiveTabs
          perspectives={(["direct_team", "leadership_peers", "self"] as const).map((cohort) => {
            const summary = aggregate.icare_cohorts.find((item) => item.cohort === cohort);
            if (aggregate.hierarchy_ambiguous && cohort !== "self") {
              return {
                id: cohort,
                label: ICARE_LABELS[cohort],
                tabLabel: ICARE_TAB_LABELS[cohort],
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
              tabLabel: ICARE_TAB_LABELS[cohort],
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
      </ResultSection>

      <ResultSection
        id="ta-drivers"
        title="TA Drivers"
        description="Media procentuală și frecvența primilor doi driveri pentru fiecare persoană."
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
      </ResultSection>

      <ResultSection
        id="leadership"
        title="Echipa de leadership"
        description="Deschide raportul unei persoane pentru profilul și rezultatele sale complete."
      >
        <LeadershipMembers
          members={aggregate.leadership_members}
          reportsPath={reportsPath}
          query={reportQuery}
        />
      </ResultSection>

      <footer className="border-t border-border pt-5 text-sm text-muted-foreground">
        {participants.length} {participants.length === 1 ? "participant" : "participanți"} în proiect ·{" "}
        {aggregate.completion_rate}% completat
      </footer>
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
    <section className="grid gap-6 border-b border-border pb-10" aria-labelledby={`result-section-${id}`}>
      <div>
        <h2 id={`result-section-${id}`} className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      <div className="grid gap-5">{children}</div>
    </section>
  );
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
            <span className="block font-semibold text-foreground group-hover:text-burgundy">{member.full_name}</span>
            <span className="mt-1 block text-sm text-muted-foreground">{member.position || "Membru leadership"}</span>
          </span>
          <ArrowRightIcon aria-hidden="true" className="size-4 text-muted-foreground group-hover:text-burgundy" strokeWidth={1.8} />
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
