import Link from "next/link";
import { ArrowRightIcon, ClipboardCheckIcon, MessageSquareTextIcon } from "lucide-react";

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
      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_17rem] xl:gap-12">
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
                  <h2 id="participant-tasks-title" className="text-2xl font-semibold tracking-tight text-foreground">
                    {pendingTaskGroups.length > 0 ? "De completat" : "Chestionare"}
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {hasMultipleProjects ? projectCountCopy : summaryData.projectName}
                  </p>
                </div>
                {pendingTaskGroups.length > 0 ? (
                  <div
                    className="flex items-baseline gap-2 text-burgundy"
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
              <Link href={resultsHref} className={serverLinkButtonClassName({ variant: "ghost", className: "w-fit text-burgundy" })}>
                Vezi rezultatele
                <ArrowRightIcon data-icon="inline-end" aria-hidden="true" strokeWidth={2.2} />
              </Link>
            </div>
          ) : null}
        </section>

        <aside className="border-t border-border pt-6 xl:border-l xl:border-t-0 xl:pl-8 xl:pt-0" aria-label="Stadiul proiectului">
          <p className="text-sm font-semibold text-foreground">Progres</p>
          <p className="mt-3 font-mono text-5xl font-semibold tracking-tight text-burgundy tabular-nums">{tasksProgressPct}%</p>
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
            <p className="text-xs font-semibold text-burgundy">Disponibile acum</p>
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
              <p className="text-sm font-semibold text-burgundy">Profil personal</p>
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

function ParticipantResultSection({
  id,
  title,
  empty,
  hasContent,
  children,
}: {
  id: string;
  title: string;
  empty: string;
  hasContent: boolean;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={`participant-result-${id}`}>
      <h2 id={`participant-result-${id}`} className="text-xl font-semibold tracking-tight text-foreground">{title}</h2>
      {hasContent ? (
        <Card className="mt-4 gap-0 divide-y divide-border py-0">{children}</Card>
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
      <p className={cn("text-xs font-semibold", tone === "current" ? "text-burgundy" : "text-muted-foreground")}>{label}</p>
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
            <p className="mt-1 text-sm font-semibold text-burgundy">{feedback.projectName}</p>
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
              max={scaleMax}
              suffix={scoreSuffix}
              showSignal={false}
            />
          ))}
        </div>
      ) : !visible ? (
        <p className="mt-6 border-l-2 border-burgundy bg-muted px-4 py-3 text-sm leading-6 text-muted-foreground">
          Pentru confidențialitate, mai avem nevoie de cel puțin {Math.max(feedback.minimumCompleted - feedback.completedCount, 1)}{" "}
          {feedback.minimumCompleted - feedback.completedCount === 1 ? "răspuns" : "răspunsuri"} înainte să putem afișa media grupului.
        </p>
      ) : null}
    </article>
  );
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
  const max = maxScoreForKind(kind);
  const average = averageScore(items);
  const scaleLabel = scaleLabelForKind(kind, max);
  const highlightedItems = items.filter((item) => kind === "drivers" && item.score > 50 && item.explanation);

  return (
    <article className="px-5 py-6">
      <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-burgundy">{resultKindLabel(kind)}</p>
          <h3 className="mt-2 text-2xl font-semibold leading-8 tracking-tight text-foreground" title={result.title}>{result.title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {[result.projectName, result.targetLabel].filter(Boolean).join(" · ")}
          </p>
        </div>
        <dl className="flex flex-wrap gap-x-8 gap-y-3">
          <ResultStat label="Dimensiuni" value={String(items.length)} />
          <ResultStat label="Scor mediu" value={average === null ? "N/A" : formatScore(average)} />
          <ResultStat label="Scală" value={scaleLabel.replace("scală ", "")} />
        </dl>
      </div>

      {result.primaryResult ? (
        <p className="mt-5 text-sm text-muted-foreground">
          Rezultat principal:{" "}
          <strong className="text-foreground">
            {labelForScore(result.primaryResult, result.scores[result.primaryResult])}
          </strong>
        </p>
      ) : null}

      {highlightedItems.length > 0 ? (
        <section className="mt-7 border-l-2 border-destructive pl-5" aria-labelledby={`guidance-${result.assignmentId}`}>
          <div className="flex items-center gap-2 text-destructive">
            <MessageSquareTextIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
            <h4 id={`guidance-${result.assignmentId}`} className="text-sm font-semibold">Ce merită atenție</h4>
          </div>
          <div className="mt-4 grid gap-5">
            {highlightedItems.map((item) => (
              <GuidanceBlock key={item.id} item={item} />
            ))}
          </div>
        </section>
      ) : null}

      <div className="mt-7 divide-y divide-border border-t border-border" aria-label="Scoruri detaliate">
        {items.map((item) => (
          <ScoreRow key={item.id} item={item} max={max} showSignal={kind === "drivers" && item.score > 50} />
        ))}
      </div>
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

function GuidanceBlock({ item }: { item: ScoreItem }) {
  if (!item.explanation) return null;

  return (
    <article>
      <div className="flex items-center gap-2 text-destructive">
        <ClipboardCheckIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
        <h5 className="text-sm font-semibold">Punct de lucru pentru {item.label}</h5>
      </div>
      <p className="mt-2 max-w-4xl text-base leading-7 text-foreground">{item.explanation}</p>
    </article>
  );
}

function ScoreRow({
  item,
  max,
  suffix = "",
  showSignal,
}: {
  item: ScoreItem;
  max: number;
  suffix?: string;
  showSignal: boolean;
}) {
  const width = Math.max(0, Math.min(100, (item.score / max) * 100));
  const tone = showSignal ? "bg-destructive" : "bg-foreground";

  return (
    <div className="grid gap-3 py-4 md:grid-cols-[minmax(0,1fr)_7rem] md:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-base font-semibold leading-6 text-foreground">{item.label}</h4>
          {showSignal ? (
            <span className="rounded-md bg-destructive/10 px-2 py-1 text-[11px] font-semibold text-destructive">
              De urmărit
            </span>
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
            aria-valuemin={0}
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

function maxScoreForKind(kind: ResultKind): number {
  if (kind === "lencioni") return 10;
  return 100;
}

function scaleLabelForKind(kind: ResultKind, max: number): string {
  if (kind === "icare") return "scor procentual";
  return `scală 0-${max}`;
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
