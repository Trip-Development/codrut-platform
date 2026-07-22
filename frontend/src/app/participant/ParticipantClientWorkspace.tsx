import Link from "next/link";
import { ArrowRightIcon, ClipboardCheckIcon, MessageSquareTextIcon } from "lucide-react";

import type { SessionState } from "@/api/auth";
import type { InviteTask } from "@/api/invites";
import { formatPcmLabel, getPcmProfile } from "@/api/pcm";
import type {
  ParticipantReceivedFeedbackSummary,
  ParticipantWorkspaceProject,
  ParticipantWorkspaceResult,
} from "@/api/participants";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { cn } from "@/utils/cn";
import { ParticipantTaskList } from "./ParticipantTaskList";
import { groupParticipantTasks } from "./task-display";

type ParticipantClientWorkspaceProps = {
  session: SessionState;
  summaryData: {
    projectName: string;
    projects?: ParticipantWorkspaceProject[];
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

export function ParticipantClientWorkspace({ summaryData }: ParticipantClientWorkspaceProps) {
  const participantIdentity =
    summaryData.participantFullName?.trim() || summaryData.anonymousName?.trim() || "Participant";
  const participantFirstName = participantIdentity.split(/\s+/)[0];
  const pendingTasks = summaryData.tasks.filter((task) => task.status !== "completed");
  const taskGroups = groupParticipantTasks(summaryData.tasks);
  const pendingTaskGroups = taskGroups.filter((group) => group.status !== "completed");
  const completedTasksCount = summaryData.tasks.length - pendingTasks.length;
  const tasksProgressPct =
    summaryData.tasks.length > 0 ? Math.round((completedTasksCount / summaryData.tasks.length) * 100) : 0;
  const hasAnyTasks = summaryData.tasks.length > 0;
  const isComplete = hasAnyTasks && pendingTasks.length === 0;
  const resultCount = summaryData.results.length;
  const projects = summaryData.projects ?? [];
  const hasMultipleProjects = projects.length > 1;

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title={`Bună, ${participantFirstName}`}
      description=""
      navItems={participantNavItems}
      activeHref="/participant"
      userLabel={participantFirstName}
    >
      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_17rem] xl:gap-12">
        <section className="min-w-0" aria-labelledby="participant-tasks-title">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
            <div>
              <h2 id="participant-tasks-title" className="text-2xl font-semibold tracking-tight text-foreground">
                {pendingTaskGroups.length > 0 ? "De completat" : isComplete ? "Totul este trimis" : "Chestionare"}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {hasMultipleProjects ? `${projects.length} proiecte active` : summaryData.projectName}
              </p>
            </div>
            <div
              className="flex items-baseline gap-2 text-burgundy"
              role="status"
              aria-label={`${pendingTaskGroups.length} ${pendingTaskGroups.length === 1 ? "sarcină activă" : "sarcini active"}`}
            >
              <span className="font-mono text-2xl font-semibold tabular-nums">{pendingTaskGroups.length}</span>
              <span className="text-sm font-semibold">active</span>
            </div>
          </div>
          <ParticipantTaskList
            groups={taskGroups}
            returnTo="/participant/questionnaires"
            emptyTitle={
              isComplete
                ? "Toate răspunsurile au fost trimise"
                : summaryData.emptyState?.title ?? "Nu ai chestionare disponibile"
            }
            emptyDescription={
              isComplete
                ? "Nu mai ai sarcini active."
                : summaryData.emptyState?.description ??
                  "Deschide linkul unei invitații noi pentru a vedea sarcinile asociate."
            }
          />

          {resultCount > 0 ? (
            <div className="mt-8 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                Ai {resultCount} {resultCount === 1 ? "rezultat disponibil" : "rezultate disponibile"}.
              </p>
              <Link href="/participant/results" className={serverLinkButtonClassName({ variant: "ghost", className: "w-fit text-burgundy" })}>
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
            {completedTasksCount}/{summaryData.tasks.length} finalizate
          </p>
          {hasMultipleProjects ? (
            <div className="mt-7 border-y border-border" aria-label="Progres pe proiecte">
              {projects.map((project) => {
                const projectTasks = summaryData.tasks.filter((task) => task.projectId === project.id);
                const completed = projectTasks.filter((task) => task.status === "completed").length;
                return (
                  <div key={project.id} className="border-b border-border py-3 last:border-b-0">
                    <p className="text-sm font-semibold text-foreground">{project.name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {completed}/{projectTasks.length} finalizate · {project.deadlineLabel}
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
}: {
  results: ParticipantWorkspaceResult[];
  receivedFeedback?: ParticipantReceivedFeedbackSummary | null;
  receivedFeedbackGroups?: ParticipantReceivedFeedbackSummary[];
  pcmBase?: string | null;
  pcmPhase?: string | null;
}) {
  const feedbackGroups = receivedFeedbackGroups.length > 0
    ? receivedFeedbackGroups
    : receivedFeedback
      ? [receivedFeedback]
      : [];
  return (
    <section className="flex flex-col gap-10">
      {pcmBase || pcmPhase ? (
        <section className="grid gap-7 rounded-lg bg-foreground px-6 py-6 text-background md:grid-cols-[minmax(10rem,0.7fr)_minmax(0,1.3fr)] md:items-center md:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-background/55">Profil personal</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">PCM</h2>
          </div>
          <div className="flex flex-wrap gap-x-12 gap-y-5">
            {pcmBase ? <PcmResultChip label="Bază PCM" value={pcmBase} /> : null}
            {pcmPhase ? <PcmResultChip label="Fază PCM" value={pcmPhase} /> : null}
          </div>
        </section>
      ) : null}

      {feedbackGroups.map((feedback, index) => (
        <ReceivedFeedbackPanel
          key={feedback.assignmentRoundId ?? `${feedback.projectId ?? feedback.projectName ?? "legacy"}-${index}`}
          feedback={feedback}
        />
      ))}

      {results.length > 0 ? (
        <div className="divide-y divide-border border-y border-border">
          {results.map((result) => (
            <ResultCard key={result.assignmentId} result={result} />
          ))}
        </div>
      ) : feedbackGroups.length > 0 ? null : (
        <div className="border-y border-border py-8">
          <h3 className="text-base font-semibold text-foreground">Nu există scoruri calculate încă</h3>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            După ce finalizezi chestionarele cu scor, sumarul apare aici automat.
          </p>
        </div>
      )}
    </section>
  );
}

function ReceivedFeedbackPanel({ feedback }: { feedback: ParticipantReceivedFeedbackSummary }) {
  const visible = feedback.visible && feedback.overallAverage !== null && feedback.overallAverage !== undefined && feedback.dimensions.length > 0;
  const observedMaximum = Math.max(
    feedback.overallAverage ?? 0,
    ...feedback.dimensions.map((dimension) => dimension.averageScore),
  );
  const scaleMax = feedback.scaleMax ?? (observedMaximum > 5 ? 100 : 5);

  return (
    <article className="border-t border-border pt-6">
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <h3 className="text-2xl font-semibold tracking-tight text-foreground">Feedback primit</h3>
          {feedback.projectName ? (
            <p className="mt-1 text-sm font-semibold text-burgundy">{feedback.projectName}</p>
          ) : null}
          {feedback.questionnaireTitle ? (
            <p className="mt-1 text-sm text-muted-foreground">{feedback.questionnaireTitle}</p>
          ) : null}
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Mediile sunt anonime și nu includ răspunsuri individuale.</p>
        </div>
        <div className="flex gap-10">
          <FeedbackMetric label="Feedbackuri" value={String(feedback.completedCount)} />
          <FeedbackMetric label="Medie" value={visible ? formatScore(feedback.overallAverage ?? 0) : "N/A"} />
        </div>
      </div>

      {visible ? (
        <div className="mt-6 divide-y divide-border border-y border-border">
          {feedback.dimensions.map((dimension) => (
            <ScoreRow
              key={dimension.id}
              item={{
                id: dimension.id,
                label: dimension.label,
                score: dimension.averageScore,
              }}
              max={scaleMax}
              showSignal={false}
            />
          ))}
        </div>
      ) : (
        <p className="mt-6 border-l-2 border-burgundy bg-muted px-4 py-3 text-sm leading-6 text-muted-foreground">
          Media apare după minimum {feedback.minimumCompleted} feedbackuri completate. Pragul protejează anonimitatea respondenților.
        </p>
      )}
    </article>
  );
}

function PcmResultChip({ label, value }: { label: string; value?: string | null }) {
  const profile = getPcmProfile(value);
  const color = profile?.color ?? "var(--border)";
  return (
    <div>
      <p className="text-xs font-semibold text-background/55">{label}</p>
      <p className="mt-1.5 flex items-center gap-2.5 text-xl font-semibold text-background">
        <span className="size-3 rounded-full ring-2 ring-background/15" style={{ backgroundColor: color }} />
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
    <article className="py-8">
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
        <section className="mt-7 border-l-2 border-burgundy pl-5" aria-labelledby={`guidance-${result.assignmentId}`}>
          <div className="flex items-center gap-2 text-burgundy">
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

      <div className="mt-7 divide-y divide-border border-y border-border" aria-label="Scoruri detaliate">
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
      <div className="flex items-center gap-2 text-burgundy">
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
  showSignal,
}: {
  item: ScoreItem;
  max: number;
  showSignal: boolean;
}) {
  const width = Math.max(0, Math.min(100, (item.score / max) * 100));
  const tone = showSignal ? "bg-burgundy" : "bg-foreground";

  return (
    <div className="grid gap-3 py-4 md:grid-cols-[minmax(0,1fr)_7rem] md:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-base font-semibold leading-6 text-foreground">{item.label}</h4>
          {showSignal ? (
            <span className="rounded-md bg-burgundy/10 px-2 py-1 text-[11px] font-semibold text-burgundy">
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
        <p className="font-mono text-2xl font-semibold tabular-nums text-foreground">{formatScore(item.score)}</p>
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
