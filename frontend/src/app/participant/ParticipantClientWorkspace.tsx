import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";

import type { SessionState } from "@/api/auth";
import type { InviteTask } from "@/api/invites";
import { formatPcmLabel, getPcmProfile } from "@/api/pcm";
import type {
  ParticipantQuestionnaireProject,
  ParticipantReceivedFeedbackSummary,
  ParticipantWorkspaceContext,
  ParticipantWorkspaceCycle,
  ParticipantWorkspaceProject,
  ParticipantWorkspaceResult,
} from "@/api/participants";
import { EmptyState } from "@/components/presentation/empty-state";
import { CycleComparisonBars, type CycleComparisonRow } from "@/components/reports/CycleComparisonBars";
import { cycleAccent } from "@/components/reports/cycle-accents";
import { IcarePerspectiveGrid } from "@/components/reports/IcarePerspectiveGrid";
import { InterpretationDisclosure } from "@/components/reports/InterpretationDisclosure";
import { ResultSignalBadge } from "@/components/reports/ResultSignalBadge";
import { AppShell } from "@/components/shell/app-shell";
import { Card } from "@/components/ui/card";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { cn } from "@/utils/cn";
import { ParticipantCompletionState } from "./ParticipantCompletionState";
import { ParticipantContextSelector } from "./ParticipantContextSelector";
import { ParticipantTaskList } from "./ParticipantTaskList";
import {
  participantActiveHref,
  participantScopeParams,
  participantScopedHref,
  participantScopedNavItems,
} from "./participant-context";
import { countAvailableParticipantResults, mergeParticipantFeedbackGroups } from "./result-state";
import {
  groupParticipantTasksByProject,
  participantTaskProjectsFromCatalog,
} from "./task-display";

type ParticipantClientWorkspaceProps = {
  session: SessionState;
  summaryData: {
    projectName: string;
    projectId?: string | null;
    assessmentCycleId?: string | null;
    participantProfileId?: string;
    contextSelectionRequired?: boolean;
    contexts?: ParticipantWorkspaceContext[];
    cycles?: ParticipantWorkspaceCycle[];
    projects?: ParticipantWorkspaceProject[];
    questionnaireProjects?: ParticipantQuestionnaireProject[];
    companyName?: string;
    participantFullName?: string;
    anonymousName?: string | null;
    participantEmail: string;
    deadlineLabel: string;
    tasks: InviteTask[];
    pcmBase?: string | null;
    pcmPhase?: string | null;
    results: ParticipantWorkspaceResult[];
    receivedFeedback?: ParticipantReceivedFeedbackSummary | null;
    receivedFeedbackGroups?: ParticipantReceivedFeedbackSummary[];
    emptyState?: {
      title: string;
      description: string;
    };
  };
};

export function ParticipantClientWorkspace({ session, summaryData }: ParticipantClientWorkspaceProps) {
  const participantIdentity =
    summaryData.participantFullName?.trim() || summaryData.anonymousName?.trim() || "Participant";
  const participantFirstName = participantIdentity.split(/\s+/)[0];
  const taskProjects =
    (summaryData.questionnaireProjects?.length ?? 0) > 0
      ? participantTaskProjectsFromCatalog(
          summaryData.questionnaireProjects ?? [],
        )
      : groupParticipantTasksByProject(
          summaryData.tasks,
          summaryData.projects ?? [],
        );
  const activeTaskProjects = taskProjects.filter(
    (project) =>
      project.historyBucket === "current" && project.status === "active",
  );
  const activeTasks = activeTaskProjects.flatMap((project) =>
    project.groups.flatMap((group) => group.tasks),
  );
  const pendingActiveTasks = activeTasks.filter(
    (task) => task.status !== "completed",
  );
  const activeTaskGroups = activeTaskProjects.flatMap(
    (project) => project.groups,
  );
  const pendingTaskGroups = activeTaskGroups.filter(
    (group) => group.status !== "completed",
  );
  const completedTasksCount = activeTasks.length - pendingActiveTasks.length;
  const tasksProgressPct =
    activeTasks.length > 0
      ? Math.round((completedTasksCount / activeTasks.length) * 100)
      : 0;
  const hasAnyTasks = activeTasks.length > 0;
  const isComplete = hasAnyTasks && pendingActiveTasks.length === 0;
  const resultCount = countAvailableParticipantResults(summaryData);
  const projects = taskProjects;
  const hasMultipleProjects = taskProjects.length > 1;
  const projectCountCopy = participantProjectCountCopy(projects);
  const contexts = summaryData.contexts ?? [];
  const scopeParams = participantScopeParams(summaryData);
  const questionnairesHref = participantScopedHref("/participant/questionnaires", scopeParams);
  const resultsHref = participantScopedHref("/participant/results", scopeParams);
  const navItems = participantScopedNavItems(scopeParams);

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title={`Bună, ${participantFirstName}`}
      description=""
      navItems={navItems}
      activeHref={participantActiveHref("/participant", scopeParams)}
      userLabel={participantFirstName}
      session={session}
    >
      <ParticipantContextSelector
        contexts={contexts}
        selectedProfileId={summaryData.participantProfileId}
        selectedProjectId={summaryData.projectId}
      />
      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_16rem] xl:gap-10">
        <section
          className="min-w-0"
          aria-labelledby={isComplete ? "participant-completion-title" : "participant-tasks-title"}
        >
          {isComplete ? (
            <>
              <ParticipantCompletionState resultCount={resultCount} resultsHref={resultsHref} />
              <div className="mt-8">
                <ParticipantTaskList
                  projects={taskProjects}
                  persistenceIdentityKey={`${session.user.id}:${summaryData.participantProfileId ?? "all"}`}
                  returnTo={questionnairesHref}
                  emptyTitle="Toate răspunsurile au fost trimise"
                  emptyDescription="Nu mai ai sarcini active."
                />
              </div>
            </>
          ) : (
            <>
              <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
                <div>
                  <h2 id="participant-tasks-title" className="text-xl font-semibold tracking-tight text-foreground">
                    {pendingTaskGroups.length > 0 ? "De completat" : "Chestionare"}
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {hasMultipleProjects ? projectCountCopy : summaryData.projectName}
                  </p>
                  {pendingTaskGroups.length > 0 ? (
                    <p className="mt-2 text-xs font-semibold text-brand-text">
                      Următorul pas: Completează următorul chestionar
                    </p>
                  ) : null}
                </div>
                {pendingTaskGroups.length > 0 ? (
                  <div
                    className="flex items-baseline gap-2 text-brand-text"
                    role="status"
                    aria-label={`${pendingTaskGroups.length} ${pendingTaskGroups.length === 1 ? "sarcină activă" : "sarcini active"}`}
                  >
                    <span className="font-mono text-2xl font-semibold tabular-nums">{pendingTaskGroups.length}</span>
                    <span className="text-sm font-semibold">active</span>
                  </div>
                ) : null}
              </div>
              <ParticipantTaskList
                projects={taskProjects}
                persistenceIdentityKey={`${session.user.id}:${summaryData.participantProfileId ?? "all"}`}
                returnTo={questionnairesHref}
                emptyTitle={summaryData.emptyState?.title ?? "Nu ai chestionare disponibile"}
                emptyDescription={
                  summaryData.emptyState?.description ??
                  "Deschide linkul unei invitații noi pentru a vedea sarcinile asociate."
                }
              />
            </>
          )}

          {!isComplete && resultCount > 0 ? (
            <div className="mt-8 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                Ai {resultCount} {resultCount === 1 ? "rezultat disponibil" : "rezultate disponibile"}.
              </p>
              <Link href={resultsHref} className={serverLinkButtonClassName({ variant: "ghost", className: "w-fit text-brand-text" })}>
                Vezi rezultatele
                <ArrowRightIcon data-icon="inline-end" aria-hidden="true" strokeWidth={2.2} />
              </Link>
            </div>
          ) : null}
        </section>

        <aside className="border-t border-border pt-6 xl:border-l xl:border-t-0 xl:pl-8 xl:pt-0" aria-label="Stadiul proiectului">
          <p className="text-sm font-semibold text-foreground">Progres</p>
          <p className="mt-3 font-mono text-5xl font-semibold tracking-tight text-brand-text tabular-nums">{tasksProgressPct}%</p>
          <div
            className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label="Progresul sarcinilor"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={tasksProgressPct}
          >
            <div className="h-full rounded-full bg-burgundy transition-[width] duration-200" style={{ width: `${tasksProgressPct}%` }} />
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            {completedTasksCount}/{activeTasks.length} finalizate
          </p>
          {hasMultipleProjects ? (
            <div className="mt-7 border-y border-border" aria-label="Progres pe proiecte">
              {projects.map((project) => {
                return (
                  <div key={project.id} className="border-b border-border py-3 last:border-b-0">
                    <p className="text-sm font-semibold text-foreground">{project.name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {project.completedCount}/{project.totalCount} finalizate · {project.deadlineLabel}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : null}
          <dl className={cn("divide-y divide-border border-y border-border", hasMultipleProjects ? "mt-5" : "mt-7")}>
            <ContextRow label="Companie" value={summaryData.companyName || "Neasociată"} />
            {!hasMultipleProjects ? <ContextRow label="Termen" value={summaryData.deadlineLabel || "Fără termen"} /> : null}
            <ContextRow label="Profil" value={participantIdentity} />
          </dl>
        </aside>
      </div>
    </AppShell>
  );
}

function participantProjectCountCopy(
  projects: Array<{ historyBucket: "current" | "history" }>,
): string {
  const currentCount = projects.filter(
    (project) => project.historyBucket === "current",
  ).length;
  const historyCount = projects.length - currentCount;

  if (currentCount > 0 && historyCount > 0) {
    return `${currentCount} în desfășurare · ${historyCount} în istoric`;
  }
  if (currentCount > 0) {
    return `${currentCount} ${currentCount === 1 ? "proiect în desfășurare" : "proiecte în desfășurare"}`;
  }
  return `${historyCount} ${historyCount === 1 ? "proiect în istoric" : "proiecte în istoric"}`;
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="py-3">
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words text-sm font-semibold text-foreground">{value}</dd>
    </div>
  );
}

export function ParticipantResultsPanel({
  results,
  receivedFeedback,
  receivedFeedbackGroups = [],
  pcmBase,
  pcmPhase,
  hasTasks = false,
  allTasksComplete = false,
  comparison,
}: {
  results: ParticipantWorkspaceResult[];
  receivedFeedback?: ParticipantReceivedFeedbackSummary | null;
  receivedFeedbackGroups?: ParticipantReceivedFeedbackSummary[];
  pcmBase?: string | null;
  pcmPhase?: string | null;
  hasTasks?: boolean;
  allTasksComplete?: boolean;
  comparison?: ParticipantResultsComparison | null;
}) {
  const feedbackGroups = mergeParticipantFeedbackGroups(receivedFeedbackGroups, receivedFeedback);
  const visibleFeedbackCount = feedbackGroups.filter((feedback) => feedback.visible).length;
  const profileResultCount = pcmBase || pcmPhase ? 1 : 0;
  const availableResultCount = results.length + visibleFeedbackCount + profileResultCount;
  const lencioniResults = results.filter((result) => resultKind(result.questionnaireKey) === "lencioni");
  const icareResults = results.filter((result) => resultKind(result.questionnaireKey) === "icare");
  const driverResults = results.filter((result) => resultKind(result.questionnaireKey) === "drivers");
  const otherResults = results.filter((result) => resultKind(result.questionnaireKey) === "other");
  return (
    <section className="flex flex-col gap-10">
      {availableResultCount > 0 ? (
        <header className="flex flex-col gap-3 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold text-brand-text">Disponibile acum</p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
              {availableResultCount} {availableResultCount === 1 ? "rezultat" : "rezultate"}
            </h2>
          </div>
          <p className="text-sm font-semibold text-muted-foreground">Lencioni · iCARE · TA Drivers</p>
        </header>
      ) : null}

      {comparison && (pcmBase || pcmPhase || comparison.baselinePcmBase || comparison.baselinePcmPhase) ? (
        <PcmComparison
          baselineLabel={comparison.baselineLabel}
          currentLabel={comparison.currentLabel}
          baselineBase={comparison.baselinePcmBase}
          baselinePhase={comparison.baselinePcmPhase}
          currentBase={pcmBase}
          currentPhase={pcmPhase}
        />
      ) : pcmBase || pcmPhase ? (
        <Card asChild className="px-5 [--card-spacing:--spacing(5)] md:px-6">
          <section className="grid gap-7 md:grid-cols-[minmax(10rem,0.7fr)_minmax(0,1.3fr)] md:items-center" aria-labelledby="participant-pcm-title">
            <div>
              <p className="text-sm font-semibold text-brand-text">Profil personal</p>
              <h2 id="participant-pcm-title" className="mt-1 text-2xl font-semibold tracking-tight text-foreground">PCM</h2>
            </div>
            <div className="flex flex-wrap gap-x-12 gap-y-5">
              {pcmBase ? <PcmResultChip label="Bază PCM" value={pcmBase} /> : null}
              {pcmPhase ? <PcmResultChip label="Fază PCM" value={pcmPhase} /> : null}
            </div>
          </section>
        </Card>
      ) : null}

      <ParticipantResultSection
        id="lencioni"
        title="Lencioni"
        empty="Rezultatul Lencioni apare aici după ce evaluarea este finalizată."
        hasContent={lencioniResults.length > 0}
      >
        {lencioniResults.map((result) => <ResultCard key={result.assignmentId} result={result} />)}
      </ParticipantResultSection>

      <ParticipantResultSection
        id="icare"
        title="iCARE"
        empty="Rezultatele iCARE apar aici când perspectivele sunt disponibile."
        hasContent={feedbackGroups.length > 0 || icareResults.length > 0}
      >
        {feedbackGroups.map((feedback, index) => (
          <ReceivedFeedbackPanel
            key={`${feedback.assignmentRoundId ?? "round"}-${feedback.cohort}-${index}`}
            feedback={feedback}
          />
        ))}
        {icareResults.map((result) => <ResultCard key={result.assignmentId} result={result} />)}
      </ParticipantResultSection>

      <ParticipantResultSection
        id="ta-drivers"
        title="TA Drivers"
        empty="Rezultatul TA Drivers apare aici după finalizare."
        hasContent={driverResults.length > 0}
      >
        {driverResults.map((result) => <ResultCard key={result.assignmentId} result={result} />)}
      </ParticipantResultSection>

      {otherResults.length > 0 ? (
        <Card asChild className="gap-0 divide-y divide-border py-0">
          <section aria-label="Alte rezultate">
            {otherResults.map((result) => <ResultCard key={result.assignmentId} result={result} />)}
          </section>
        </Card>
      ) : null}

      {availableResultCount === 0 && feedbackGroups.length === 0 ? (
        <EmptyState
          title={allTasksComplete && hasTasks ? "Răspunsurile au fost trimise" : "Nu există rezultate disponibile încă"}
          description={allTasksComplete && hasTasks
            ? "Rezultatele vor apărea aici după procesare."
            : "Finalizează chestionarele eligibile pentru a vedea rezultatele."}
        />
      ) : null}
    </section>
  );
}

export type ParticipantCycleResultSummary = {
  cycle: ParticipantWorkspaceCycle;
  results: ParticipantWorkspaceResult[];
  receivedFeedback?: ParticipantReceivedFeedbackSummary | null;
  receivedFeedbackGroups?: ParticipantReceivedFeedbackSummary[];
  pcmBase?: string | null;
  pcmPhase?: string | null;
};

export function ParticipantResultsHistory({
  cycles,
}: {
  cycles: ParticipantCycleResultSummary[];
}) {
  const lencioniRows = participantResultComparisonRows(cycles, "lencioni");
  const driverRows = participantResultComparisonRows(cycles, "drivers");
  const selfIcareRows = participantResultComparisonRows(cycles, "icare");
  const directTeamRows = participantFeedbackComparisonRows(cycles, "direct_team");
  const leadershipPeerRows = participantFeedbackComparisonRows(cycles, "leadership_peers");
  const pcmAvailable = cycles.some(({ pcmBase, pcmPhase }) => pcmBase || pcmPhase);
  const lencioniScale = participantComparisonScale(cycles, "lencioni", 3, 9);
  const driverScale = participantComparisonScale(cycles, "drivers", 0, 100);
  const selfIcareScale = participantComparisonScale(cycles, "icare", 0, 100);
  const directScale = participantFeedbackComparisonScale(cycles, "direct_team");
  const peerScale = participantFeedbackComparisonScale(cycles, "leadership_peers");

  return (
    <section className="flex flex-col gap-10" aria-label="Comparația rezultatelor">
      {pcmAvailable ? (
        <PcmEvolution cycles={cycles} />
      ) : null}

      <ParticipantResultSection
        id="history-lencioni"
        title="Lencioni"
        empty="Rezultatul Lencioni apare aici după finalizarea unei evaluări."
        hasContent={lencioniRows.length > 0}
        contained={false}
      >
        <CycleComparisonBars
          title="Evoluția dimensiunilor"
          rows={lencioniRows}
          min={lencioniScale.min}
          max={lencioniScale.max}
          deltaUnit="points"
          higherIsBetter
          empty="Nu există încă rezultate Lencioni comparabile."
        />
      </ParticipantResultSection>

      <ParticipantResultSection
        id="history-icare"
        title="iCARE"
        empty="Rezultatele iCARE apar aici când perspectivele sunt disponibile."
        hasContent={cycles.some((cycle) => (
          cycle.results.some((result) => resultKind(result.questionnaireKey) === "icare")
          || mergeParticipantFeedbackGroups(cycle.receivedFeedbackGroups ?? [], cycle.receivedFeedback).length > 0
        ))}
        contained={false}
      >
        <IcarePerspectiveGrid
          perspectives={[
            {
              id: "direct-team",
              label: "Cum te vede echipa ta",
              responseCount: participantFeedbackResponseCount(cycles, "direct_team"),
              content: (
                <CycleComparisonBars
                  title="Cum te vede echipa ta"
                  rows={directTeamRows}
                  min={directScale.min}
                  max={directScale.max}
                  deltaUnit={directScale.suffix === "%" ? "pp" : "points"}
                  higherIsBetter
                  empty={participantFeedbackEmptyCopy(cycles, "direct_team")}
                />
              ),
            },
            {
              id: "leadership-peers",
              label: "Cum te văd colegii din leadership",
              responseCount: participantFeedbackResponseCount(cycles, "leadership_peers"),
              content: (
                <CycleComparisonBars
                  title="Cum te văd colegii din leadership"
                  rows={leadershipPeerRows}
                  min={peerScale.min}
                  max={peerScale.max}
                  deltaUnit={peerScale.suffix === "%" ? "pp" : "points"}
                  higherIsBetter
                  empty={participantFeedbackEmptyCopy(cycles, "leadership_peers")}
                />
              ),
            },
            {
              id: "self",
              label: "Cum te evaluezi",
              responseCount: cycles.filter((cycle) => cycle.results.some((result) => resultKind(result.questionnaireKey) === "icare")).length,
              content: (
                <CycleComparisonBars
                  title="Cum te evaluezi"
                  rows={selfIcareRows}
                  min={selfIcareScale.min}
                  max={selfIcareScale.max}
                  deltaUnit={selfIcareScale.suffix === "%" ? "pp" : "points"}
                  higherIsBetter
                  empty="Autoevaluarea nu este încă disponibilă."
                />
              ),
            },
          ]}
        />
      </ParticipantResultSection>

      <ParticipantResultSection
        id="history-ta-drivers"
        title="TA Drivers"
        empty="Rezultatul TA Drivers apare aici după finalizare."
        hasContent={driverRows.length > 0}
        contained={false}
      >
        <CycleComparisonBars
          title="Evoluția driverilor de stres"
          rows={driverRows}
          min={driverScale.min}
          max={driverScale.max}
          deltaUnit="pp"
          higherIsBetter={false}
          empty="Nu există încă rezultate TA comparabile."
        />
      </ParticipantResultSection>
    </section>
  );
}

function participantResultComparisonRows(
  cycles: ParticipantCycleResultSummary[],
  kind: ResultKind,
): CycleComparisonRow[] {
  const dimensions = new Map<string, string>();
  cycles.forEach(({ results }) => results
    .filter((result) => resultKind(result.questionnaireKey) === kind)
    .forEach((result) => scoreItemsForResult(result)
      .forEach((item) => dimensions.set(item.id, item.label))));

  return [...dimensions].map(([id, label]) => {
    let guidance: string | null = null;
    const values = cycles.flatMap(({ cycle, results }, index) => {
      const result = results.find((candidate) => resultKind(candidate.questionnaireKey) === kind);
      const item = result ? scoreItemsForResult(result).find((candidate) => candidate.id === id) : null;
      if (!result || !item) return [];
      const scale = resultScoreScale(result, kind);
      if (kind === "drivers" && item.score > 50 && item.explanation) guidance = item.explanation;
      return [{
        cycleId: cycle.id,
        cycleLabel: cycle.name,
        color: cycleAccent(index).color,
        value: item.score,
        valueLabel: `${formatScore(item.score)}${scale.suffix}`,
        status: kind === "drivers" ? (item.score > 50 ? "watch" as const : "ok" as const) : undefined,
      }];
    });
    return { id: `${kind}-${id}`, label, values, note: guidance };
  });
}

function participantFeedbackComparisonRows(
  cycles: ParticipantCycleResultSummary[],
  cohort: ParticipantReceivedFeedbackSummary["cohort"],
): CycleComparisonRow[] {
  const dimensions = new Map<string, string>();
  cycles.forEach((cycle) => participantFeedbackForCycle(cycle, cohort)?.dimensions
    .forEach((dimension) => dimensions.set(dimension.id, dimension.label)));

  return [...dimensions].map(([id, label]) => ({
    id: `${cohort}-${id}`,
    label,
    values: cycles.flatMap((cycle, index) => {
      const feedback = participantFeedbackForCycle(cycle, cohort);
      const dimension = feedback?.visible
        ? feedback.dimensions.find((candidate) => candidate.id === id)
        : null;
      if (!dimension || !feedback) return [];
      const max = receivedFeedbackScaleMax(feedback);
      return [{
        cycleId: cycle.cycle.id,
        cycleLabel: cycle.cycle.name,
        color: cycleAccent(index).color,
        value: dimension.averageScore,
        valueLabel: `${formatScore(dimension.averageScore)}${receivedFeedbackScoreSuffix(feedback, max)}`,
      }];
    }),
  }));
}

function participantFeedbackForCycle(
  cycle: ParticipantCycleResultSummary,
  cohort: ParticipantReceivedFeedbackSummary["cohort"],
): ParticipantReceivedFeedbackSummary | null {
  return mergeParticipantFeedbackGroups(cycle.receivedFeedbackGroups ?? [], cycle.receivedFeedback)
    .find((feedback) => feedback.cohort === cohort) ?? null;
}

function participantComparisonScale(
  cycles: ParticipantCycleResultSummary[],
  kind: ResultKind,
  fallbackMin: number,
  fallbackMax: number,
) {
  const scales = cycles.flatMap(({ results }) => results
    .filter((result) => resultKind(result.questionnaireKey) === kind)
    .map((result) => resultScoreScale(result, kind)));
  return {
    min: scales.length > 0 ? Math.min(...scales.map((scale) => scale.min)) : fallbackMin,
    max: scales.length > 0 ? Math.max(...scales.map((scale) => scale.max)) : fallbackMax,
    suffix: scales.length > 0 && scales.every((scale) => scale.suffix === scales[0].suffix)
      ? scales[0].suffix
      : "",
  };
}

function PcmEvolution({ cycles }: { cycles: ParticipantCycleResultSummary[] }) {
  return (
    <Card asChild className="px-5 [--card-spacing:--spacing(5)] md:px-6">
      <section aria-labelledby="participant-history-pcm">
        <h2 id="participant-history-pcm" className="text-xl font-semibold tracking-tight text-foreground">PCM</h2>
        <div className="mt-5 grid gap-7">
          <PcmEvolutionLane label="Bază" cycles={cycles} select={(cycle) => cycle.pcmBase} />
          <PcmEvolutionLane label="Fază" cycles={cycles} select={(cycle) => cycle.pcmPhase} />
        </div>
      </section>
    </Card>
  );
}

function PcmEvolutionLane({
  label,
  cycles,
  select,
}: {
  label: string;
  cycles: ParticipantCycleResultSummary[];
  select: (cycle: ParticipantCycleResultSummary) => string | null | undefined;
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-foreground">{label}</h3>
      <ol className="mt-3 grid auto-cols-[minmax(9.5rem,1fr)] grid-flow-col overflow-x-auto pb-2">
        {cycles.map((cycle, index) => {
          const value = select(cycle);
          const previousValue = index > 0 ? select(cycles[index - 1]) : null;
          const changed = index > 0 && Boolean(value && previousValue && value !== previousValue);
          const profile = getPcmProfile(value);
          return (
            <li key={cycle.cycle.id} className="relative min-w-0 pr-8 last:pr-0">
              {index > 0 ? (
                <ArrowRightIcon
                  aria-hidden="true"
                  className="absolute -left-6 top-9 size-4 text-muted-foreground"
                  strokeWidth={1.8}
                />
              ) : null}
              <p className="truncate text-[0.68rem] font-semibold text-muted-foreground">{cycle.cycle.name}</p>
              <p className="mt-2 flex items-center gap-2 text-base font-semibold text-foreground">
                <span className="size-2.5 shrink-0" style={{ backgroundColor: profile?.color ?? "var(--border)" }} aria-hidden="true" />
                <span className="truncate">{value ? formatPcmLabel(value) : "În așteptare"}</span>
              </p>
              {index > 0 ? (
                <p className={cn("mt-1 text-[0.68rem] font-semibold", changed ? "text-brand-text" : "text-muted-foreground")}>
                  {changed ? "Profil schimbat" : "Fără schimbare"}
                </p>
              ) : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function participantFeedbackComparisonScale(
  cycles: ParticipantCycleResultSummary[],
  cohort: ParticipantReceivedFeedbackSummary["cohort"],
) {
  const feedback = cycles
    .map((cycle) => participantFeedbackForCycle(cycle, cohort))
    .filter((item): item is ParticipantReceivedFeedbackSummary => Boolean(item));
  const suffixes = feedback.map((item) => receivedFeedbackScoreSuffix(item, receivedFeedbackScaleMax(item)));
  return {
    min: feedback.length > 0 ? Math.min(...feedback.map((item) => item.scaleMin ?? 0)) : 0,
    max: feedback.length > 0 ? Math.max(...feedback.map(receivedFeedbackScaleMax)) : 100,
    suffix: suffixes.length > 0 && suffixes.every((suffix) => suffix === suffixes[0])
      ? suffixes[0]
      : "",
  };
}

function participantFeedbackResponseCount(
  cycles: ParticipantCycleResultSummary[],
  cohort: ParticipantReceivedFeedbackSummary["cohort"],
): number {
  return cycles.reduce(
    (sum, cycle) => sum + (participantFeedbackForCycle(cycle, cohort)?.completedCount ?? 0),
    0,
  );
}

function participantFeedbackEmptyCopy(
  cycles: ParticipantCycleResultSummary[],
  cohort: ParticipantReceivedFeedbackSummary["cohort"],
): string {
  const feedback = [...cycles]
    .reverse()
    .map((cycle) => participantFeedbackForCycle(cycle, cohort))
    .find((item): item is ParticipantReceivedFeedbackSummary => Boolean(item));
  return feedback
    ? receivedFeedbackUnavailableCopy(feedback)
    : "Această perspectivă nu este încă disponibilă.";
}

function ParticipantResultSection({
  id,
  title,
  empty,
  hasContent,
  children,
  contained = true,
}: {
  id: string;
  title: string;
  empty: string;
  hasContent: boolean;
  children: React.ReactNode;
  contained?: boolean;
}) {
  return (
    <section aria-labelledby={`participant-result-${id}`}>
      <h2 id={`participant-result-${id}`} className="text-xl font-semibold tracking-tight text-foreground">{title}</h2>
      {hasContent ? (
        contained ? (
          <Card className="mt-4 gap-0 divide-y divide-border py-0">{children}</Card>
        ) : (
          <div className="mt-4">{children}</div>
        )
      ) : (
        <EmptyState className="mt-4" title={`Niciun rezultat ${title} disponibil`} description={empty} />
      )}
    </section>
  );
}

export type ParticipantResultsComparison = {
  baselineLabel: string;
  currentLabel: string;
  baselineResults: ParticipantWorkspaceResult[];
  baselineReceivedFeedback?: ParticipantReceivedFeedbackSummary | null;
  baselineReceivedFeedbackGroups?: ParticipantReceivedFeedbackSummary[];
  baselinePcmBase?: string | null;
  baselinePcmPhase?: string | null;
};

function PcmComparison({
  baselineLabel,
  currentLabel,
  baselineBase,
  baselinePhase,
  currentBase,
  currentPhase,
}: {
  baselineLabel: string;
  currentLabel: string;
  baselineBase?: string | null;
  baselinePhase?: string | null;
  currentBase?: string | null;
  currentPhase?: string | null;
}) {
  return (
    <Card asChild className="px-5 [--card-spacing:--spacing(5)] md:px-6">
      <section aria-labelledby="pcm-comparison-title">
        <h2 id="pcm-comparison-title" className="text-xl font-semibold tracking-tight text-foreground">Profil PCM</h2>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <PcmCycleValues label={baselineLabel} base={baselineBase} phase={baselinePhase} tone="baseline" />
          <PcmCycleValues label={currentLabel} base={currentBase} phase={currentPhase} tone="current" />
        </div>
      </section>
    </Card>
  );
}

function PcmCycleValues({
  label,
  base,
  phase,
  tone,
}: {
  label: string;
  base?: string | null;
  phase?: string | null;
  tone: "baseline" | "current";
}) {
  return (
    <div className={cn("border-l-2 pl-4", tone === "current" ? "border-burgundy" : "border-zinc-400")}>
      <p className={cn("text-xs font-semibold", tone === "current" ? "text-brand-text" : "text-muted-foreground")}>{label}</p>
      {base || phase ? (
        <div className="mt-3 flex flex-wrap gap-x-8 gap-y-3">
          <PcmInlineValue label="Bază" value={base} />
          <PcmInlineValue label="Fază" value={phase} />
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">În așteptare</p>
      )}
    </div>
  );
}

function PcmInlineValue({ label, value }: { label: string; value?: string | null }) {
  const profile = getPcmProfile(value);
  return (
    <div>
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <p className="mt-1 flex items-center gap-2 text-base font-semibold text-foreground">
        {value ? <span className="size-2.5 rounded-full" style={{ backgroundColor: profile?.color ?? "var(--border)" }} /> : null}
        {value ? formatPcmLabel(value) : "În așteptare"}
      </p>
    </div>
  );
}

function ReceivedFeedbackPanel({ feedback }: { feedback: ParticipantReceivedFeedbackSummary }) {
  const visible = feedback.visible;
  const scaleMin = feedback.scaleMin ?? 0;
  const scaleMax = receivedFeedbackScaleMax(feedback);
  const scoreSuffix = receivedFeedbackScoreSuffix(feedback, scaleMax);
  const cohortTitle = feedback.cohort === "direct_team"
    ? "Cum te vede echipa ta"
    : "Cum te văd colegii din leadership";

  return (
    <article className="px-5 py-6">
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <h3 className="text-xl font-semibold tracking-tight text-foreground">{cohortTitle}</h3>
          {feedback.projectName ? (
            <p className="mt-1 text-sm font-semibold text-brand-text">{feedback.projectName}</p>
          ) : null}
          {feedback.questionnaireTitle ? (
            <p className="mt-1 text-sm text-muted-foreground">{feedback.questionnaireTitle}</p>
          ) : null}
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Vezi doar media grupului, niciodată răspunsurile unei persoane.</p>
        </div>
        <div className="flex gap-10">
          <FeedbackMetric label="Feedbackuri" value={String(feedback.completedCount)} />
          <FeedbackMetric label="Medie" value={visible ? `${formatScore(feedback.overallAverage ?? 0)}${scoreSuffix}` : "N/A"} />
        </div>
      </div>

      {visible && feedback.dimensions.length > 0 ? (
        <div className="mt-6 divide-y divide-border border-t border-border">
          {feedback.dimensions.map((dimension) => (
            <ScoreRow
              key={dimension.id}
              item={{
                id: dimension.id,
                label: dimension.label,
                score: dimension.averageScore,
              }}
              min={scaleMin}
              max={scaleMax}
              suffix={scoreSuffix}
              showSignal={false}
              showStatus={false}
            />
          ))}
        </div>
      ) : !visible ? (
        <p className="mt-6 border-l-2 border-burgundy bg-muted px-4 py-3 text-sm leading-6 text-muted-foreground">
          {receivedFeedbackUnavailableCopy(feedback)}
        </p>
      ) : null}
    </article>
  );
}

function receivedFeedbackUnavailableCopy(feedback: ParticipantReceivedFeedbackSummary): string {
  if (feedback.unavailableReason === "no_eligible_dimensions") {
    return "Acest chestionar nu are încă dimensiuni care pot fi afișate în rezultat.";
  }
  if (feedback.unavailableReason === "scoring_unavailable") {
    return "Răspunsurile au fost trimise, dar rezultatul nu este disponibil momentan. Nu trebuie completate din nou.";
  }
  const missing = Math.max(feedback.minimumCompleted - feedback.completedCount, 1);
  return `Pentru confidențialitate, mai avem nevoie de cel puțin ${missing} ${missing === 1 ? "răspuns" : "răspunsuri"} înainte să putem afișa media grupului.`;
}

function receivedFeedbackScaleMax(feedback: ParticipantReceivedFeedbackSummary): number {
  if (feedback.scoreUnit === "percent") return feedback.scaleMax ?? 100;
  if (feedback.scoreUnit === "grade_1_to_5") return feedback.scaleMax ?? 5;
  const observedMaximum = Math.max(
    feedback.overallAverage ?? 0,
    ...feedback.dimensions.map((dimension) => dimension.averageScore),
  );
  if (observedMaximum > 5) {
    return Math.max(100, feedback.scaleMax ?? 0);
  }
  return Math.max(5, feedback.scaleMax ?? 0, observedMaximum);
}

function receivedFeedbackScoreSuffix(feedback: ParticipantReceivedFeedbackSummary, scaleMax: number): string {
  if (feedback.scoreUnit === "percent") return "%";
  if (feedback.scoreUnit === "grade_1_to_5") return ` din ${scaleMax}`;
  return Math.max(feedback.overallAverage ?? 0, ...feedback.dimensions.map((dimension) => dimension.averageScore)) > 5
    ? "%"
    : ` din ${scaleMax}`;
}

function PcmResultChip({ label, value }: { label: string; value?: string | null }) {
  const profile = getPcmProfile(value);
  const color = profile?.color ?? "var(--border)";
  return (
    <div>
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <p className="mt-1.5 flex items-center gap-2.5 text-xl font-semibold text-foreground">
        <span className="size-3 rounded-full ring-2 ring-border" style={{ backgroundColor: color }} />
        {formatPcmLabel(value)}
      </p>
    </div>
  );
}

function ResultCard({ result }: { result: ParticipantWorkspaceResult }) {
  const kind = resultKind(result.questionnaireKey);
  const items = scoreItemsForResult(result);
  const scale = resultScoreScale(result, kind);
  const average = averageScore(items);
  const scaleUnavailable = result.scoreScaleCompatible === false
    || result.unavailableReason === "incompatible_score_scales";

  return (
    <article className="px-5 py-6">
      <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-brand-text">{resultKindLabel(kind)}</p>
          <h3 className="mt-2 text-2xl font-semibold leading-8 tracking-tight text-foreground" title={result.title}>{result.title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {[result.projectName, result.targetLabel].filter(Boolean).join(" · ")}
          </p>
        </div>
        {!scaleUnavailable ? (
          <dl className="flex flex-wrap gap-x-8 gap-y-3">
            <ResultStat label="Dimensiuni" value={String(items.length)} />
            <ResultStat
              label="Scor mediu"
              value={average === null ? "N/A" : `${formatScore(average)}${scale.suffix}`}
            />
            <ResultStat label="Scală" value={`${scale.min}-${scale.max}`} />
          </dl>
        ) : null}
      </div>

      {scaleUnavailable ? (
        <p className="mt-6 text-sm leading-6 text-muted-foreground">
          Acest rezultat folosește dimensiuni cu scale diferite sau fără o scală definită. Nu îl afișăm pe o scară aproximativă.
        </p>
      ) : null}

      {!scaleUnavailable && result.primaryResult ? (
        <p className="mt-5 text-sm text-muted-foreground">
          Rezultat principal:{" "}
          <strong className="text-foreground">
            {labelForScore(result.primaryResult, result.scores[result.primaryResult])}
          </strong>
        </p>
      ) : null}

      {!scaleUnavailable ? (
        <div className="mt-7 divide-y divide-border border-t border-border" aria-label="Scoruri detaliate">
          {items.map((item) => (
            <ScoreRow
              key={item.id}
              item={item}
              min={scale.min}
              max={scale.max}
              suffix={scale.suffix}
              showSignal={kind === "drivers" && item.score > 50}
              showStatus={kind === "drivers"}
            />
          ))}
        </div>
      ) : null}
    </article>
  );
}

function ResultStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-lg font-semibold text-foreground">{value}</dd>
    </div>
  );
}

function ScoreRow({
  item,
  min = 0,
  max,
  suffix = "",
  showSignal,
  showStatus,
}: {
  item: ScoreItem;
  min?: number;
  max: number;
  suffix?: string;
  showSignal: boolean;
  showStatus: boolean;
}) {
  const range = Math.max(max - min, Number.EPSILON);
  const width = Math.max(0, Math.min(100, ((item.score - min) / range) * 100));
  const tone = showSignal ? "bg-destructive" : "bg-foreground";

  return (
    <div className="grid gap-3 py-4 md:grid-cols-[minmax(0,1fr)_7rem] md:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-base font-semibold leading-6 text-foreground">{item.label}</h4>
          {showStatus ? (
            <ResultSignalBadge status={showSignal ? "watch" : "ok"} />
          ) : null}
        </div>
        <div className="mt-2 grid gap-2 lg:grid-cols-[minmax(0,1fr)_9rem] lg:items-center">
          {item.interpretation ? (
            <p className="text-sm leading-6 text-muted-foreground">{item.interpretation}</p>
          ) : null}
          <div
            className="h-1.5 overflow-hidden rounded-full bg-muted"
            role="meter"
            aria-label={`Scor ${item.label}`}
            aria-valuemin={min}
            aria-valuemax={max}
            aria-valuenow={item.score}
          >
            <div
              className={cn("h-full rounded-full", tone)}
              style={{ width: `${width}%` }}
              aria-hidden="true"
            />
          </div>
        </div>
        {showSignal && item.explanation ? (
          <InterpretationDisclosure>{item.explanation}</InterpretationDisclosure>
        ) : null}
      </div>
      <div className="md:text-right">
        <p className="font-mono text-2xl font-semibold tabular-nums text-foreground">{formatScore(item.score)}{suffix}</p>
        <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">scor</p>
      </div>
    </div>
  );
}

type ResultKind = "drivers" | "lencioni" | "icare" | "other";

type ScoreItem = {
  id: string;
  label: string;
  score: number;
  interpretation?: string | null;
  explanation?: string;
};

function resultKind(questionnaireKey: string): ResultKind {
  if (questionnaireKey === "distress_drivers" || questionnaireKey === "distress_drivers_en") return "drivers";
  if (questionnaireKey === "lencioni" || questionnaireKey === "lencioni_en") return "lencioni";
  if (questionnaireKey === "boss_360" || questionnaireKey === "boss_360_en" || questionnaireKey === "icare") return "icare";
  return "other";
}

function resultKindLabel(kind: ResultKind): string {
  if (kind === "drivers") return "Driveri de stres";
  if (kind === "lencioni") return "Lencioni";
  if (kind === "icare") return "iCARE 360";
  return "Chestionar";
}

function resultScoreScale(
  result: ParticipantWorkspaceResult,
  kind: ResultKind,
): { min: number; max: number; suffix: string } {
  const fallbackMax = kind === "lencioni" ? 9 : 100;
  const min = result.scaleMin ?? (kind === "lencioni" ? 3 : 0);
  const max = result.scaleMax ?? fallbackMax;
  if (result.scoreUnit === "percent") return { min, max, suffix: "%" };
  if (result.scoreUnit === "grade_1_to_5") return { min, max, suffix: ` din ${max}` };
  if (result.scoreUnit && result.scaleMax != null) return { min, max, suffix: ` / ${max}` };
  return { min, max, suffix: "" };
}

function scoreItemsForResult(result: ParticipantWorkspaceResult): ScoreItem[] {
  const items: ScoreItem[] = [];
  for (const [id, value] of Object.entries(result.scores)) {
    const score = extractScore(value);
    if (score === null) continue;
    items.push({
      id,
      label: labelForScore(id, value),
      score,
      interpretation: extractInterpretation(value),
      explanation: extractFeedback(value),
    });
  }
  return items.sort((first, second) => second.score - first.score);
}

function averageScore(items: ScoreItem[]): number | null {
  if (items.length === 0) return null;
  const total = items.reduce((sum, item) => sum + item.score, 0);
  return Math.round((total / items.length) * 10) / 10;
}

function labelForScore(id: string, value: unknown): string {
  if (typeof value === "object" && value !== null && "label" in value) {
    const label = (value as { label?: unknown }).label;
    if (typeof label === "string" && label.trim()) return label.trim();
  }
  return prettifyScoreKey(id);
}

function extractScore(value: unknown): number | null {
  const raw = typeof value === "object" && value !== null && "score" in value ? (value as { score?: unknown }).score : value;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string" && raw.trim() !== "") {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function extractInterpretation(value: unknown): string | null {
  if (typeof value !== "object" || value === null || !("interpretation" in value)) return null;
  const interpretation = (value as { interpretation?: unknown }).interpretation;
  return typeof interpretation === "string" && interpretation.trim() ? interpretation : null;
}

function extractFeedback(value: unknown): string | undefined {
  if (typeof value !== "object" || value === null || !("feedback" in value)) return undefined;
  const feedback = (value as { feedback?: unknown }).feedback;
  return typeof feedback === "string" && feedback.trim() ? feedback.trim() : undefined;
}

function prettifyScoreKey(value: string): string {
  return value
    .replace(/^icare_\d+_/, "")
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase("ro-RO") + part.slice(1))
    .join(" ");
}

function formatScore(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function FeedbackMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-20">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  );
}
