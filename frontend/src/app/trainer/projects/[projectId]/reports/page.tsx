import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";

import type {
  IcareCohortSummary,
  LeadershipMemberSummary,
  ReportAverage,
  ReportHierarchyIssue,
} from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { EmptyState } from "@/components/presentation/empty-state";
import { ParticipantFrequencyPie, ScaledBar } from "@/components/reports/native-charts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { getProjectAssessmentCyclesData, getProjectReportWorkspaceData } from "../project-data";
import { CycleComparisonControls } from "./CycleComparisonControls";
import { ReportPrintButton } from "./ReportPrintButton";
import { buildProjectReportQuery } from "./report-cycle";

const ICARE_LABELS: Record<IcareCohortSummary["cohort"], string> = {
  direct_team: "Cum vede echipa leadershipul",
  leadership_peers: "Cum se văd colegii din leadership",
  self: "Cum se evaluează liderii",
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
  const selectedCycle = cycles.find((cycle) => cycle.id === query.cycle) ?? cycles.at(-1) ?? null;
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

  if (aggregate.hierarchy_ambiguous) {
    return (
      <EmptyState
        title="Structura echipelor are nume ambigue."
        description={aggregate.hierarchy_ambiguity_message ?? "Există nume duplicate în organigramă. Corectează rosterul înainte de a deschide rezultatele."}
      />
    );
  }

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

      {aggregate.hierarchy_issues.length > 0 ? (
        <HierarchyDiagnosticsPanel issues={aggregate.hierarchy_issues} />
      ) : null}

      <ResultSection
        eyebrow="01"
        title="Lencioni"
        description="Imaginea de ansamblu a proiectului, cu acces separat la fiecare echipă."
      >
        <AveragePanel
          title="Rezultatul întregului proiect"
          count={aggregate.lencioni_count}
          items={aggregate.lencioni_averages}
          max={10}
        />
        <Link
          href={`${reportsPath}/lencioni${reportQuery}`}
          className="inline-flex w-fit items-center gap-2 text-sm font-semibold text-burgundy hover:underline"
        >
          Vezi rezultatele pe echipe
          <ArrowRightIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
        </Link>
      </ResultSection>

      <ResultSection
        eyebrow="02"
        title="iCARE"
        description="Trei perspective separate, fără a amesteca echipa, colegii și autoevaluarea."
      >
        <div className="grid gap-4 xl:grid-cols-3">
          {(["direct_team", "leadership_peers", "self"] as const).map((cohort) => {
            const summary = aggregate.icare_cohorts.find((item) => item.cohort === cohort);
            return (
              <AveragePanel
                key={cohort}
                title={ICARE_LABELS[cohort]}
                count={summary?.response_count ?? 0}
                items={summary?.averages ?? []}
                max={100}
                suffix="%"
              />
            );
          })}
        </div>
      </ResultSection>

      <ResultSection
        eyebrow="03"
        title="TA Drivers"
        description="Media procentuală și frecvența primilor doi driveri pentru fiecare persoană."
      >
        <AveragePanel
          title="Media procentuală"
          count={aggregate.driver_count}
          items={aggregate.driver_averages}
          max={100}
          suffix="%"
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
              ? "Un rezultat TA finalizat nu a putut fi inclus, deoarece nu are suficiente scoruri pentru a stabili primii doi driveri."
              : `${aggregate.driver_rank_summary.insufficient_driver_score_count} rezultate TA finalizate nu au putut fi incluse, deoarece nu au suficiente scoruri pentru a stabili primii doi driveri.`}
          </p>
        ) : null}
      </ResultSection>

      <ResultSection
        eyebrow="04"
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
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="grid gap-6 border-b border-border pb-10" aria-labelledby={`result-section-${eyebrow}`}>
      <div className="grid gap-2 md:grid-cols-[3rem_minmax(0,1fr)]">
        <p className="font-mono text-sm font-semibold text-burgundy">{eyebrow}</p>
        <div>
          <h2 id={`result-section-${eyebrow}`} className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="grid gap-5 md:pl-12">{children}</div>
    </section>
  );
}

function AveragePanel({
  title,
  count,
  items,
  max,
  suffix = "",
}: {
  title: string;
  count: number;
  items: ReportAverage[];
  max: number;
  suffix?: string;
}) {
  return (
    <article className="border-y border-border bg-surface px-5 py-5">
      <div className="flex items-start justify-between gap-4">
        <h3 className="text-lg font-semibold text-foreground">{title}</h3>
        <span className="shrink-0 text-xs font-semibold text-muted-foreground">
          {count} {count === 1 ? "răspuns" : "răspunsuri"}
        </span>
      </div>
      {items.length > 0 ? (
        <div className="mt-5 grid gap-4">
          {items.map((item) => (
            <div key={item.id}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="font-semibold text-foreground">{item.label}</span>
                <span className="font-mono font-semibold tabular-nums text-foreground">{item.avg}{suffix}</span>
              </div>
              <ScaledBar value={item.avg} max={max} />
              {item.interpretation ? (
                <p className="mt-2 text-xs leading-5 text-muted-foreground">{item.interpretation}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-5 text-sm text-muted-foreground">Rezultatele apar după completare și scorare.</p>
      )}
    </article>
  );
}

function ChartPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <article className="border-y border-border bg-surface px-5 py-5">
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <div className="mt-5">{children}</div>
    </article>
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
    return <p className="border-y border-border py-8 text-sm text-muted-foreground">Nu există încă membri de leadership în organigramă.</p>;
  }
  return (
    <div className="divide-y divide-border border-y border-border">
      {members.map((member) => (
        <Link
          key={member.participant_profile_id}
          href={`${reportsPath}/leadership/${member.participant_profile_id}${query}`}
          className="group flex items-center justify-between gap-4 py-4"
        >
          <span>
            <span className="block font-semibold text-foreground group-hover:text-burgundy">{member.full_name}</span>
            <span className="mt-1 block text-sm text-muted-foreground">{member.position || "Membru leadership"}</span>
          </span>
          <ArrowRightIcon aria-hidden="true" className="size-4 text-muted-foreground group-hover:text-burgundy" strokeWidth={1.8} />
        </Link>
      ))}
    </div>
  );
}

function HierarchyDiagnosticsPanel({ issues }: { issues: ReportHierarchyIssue[] }) {
  return (
    <Alert className="status-warning px-5 py-4">
      <AlertTitle>Unele relații din organigramă nu au putut fi asociate.</AlertTitle>
      <AlertDescription>
        Verifică persoanele și managerii indicați înainte de a interpreta rezultatele pe echipe.
        <ul className="mt-2 list-disc pl-5">
          {issues.slice(0, 4).map((issue, index) => (
            <li key={`${issue.code}-${issue.participant_id ?? index}`}>{issue.message}</li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
