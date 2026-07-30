import { getParticipantSession } from "@/api/auth-server";
import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import {
  getParticipantWorkspaceSummary,
  type ParticipantWorkspaceSummary,
} from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { cn } from "@/utils/cn";
import { redirect } from "next/navigation";
import { ParticipantResultsPanel } from "../ParticipantClientWorkspace";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import {
  participantActiveHref,
  participantScopeParams,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";

const CYCLE_ACCENTS = [
  { dot: "bg-burgundy", rail: "border-burgundy" },
  { dot: "bg-ochre", rail: "border-ochre" },
  { dot: "bg-foreground", rail: "border-foreground" },
  { dot: "bg-muted-foreground", rail: "border-muted-foreground" },
] as const;

export default async function ParticipantResultsPage({
  searchParams,
}: {
  searchParams: Promise<ParticipantRouteSearchParams>;
}) {
  const routeParams = await searchParams;
  const requestOptions = await getServerApiRequestOptions();
  const [participant, selectedSummary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(
      participantWorkspaceRequestOptions(requestOptions.headers, {
        profile: routeParams.profile,
        project: routeParams.project,
      }),
    ),
  ]);
  const onboarding = await getParticipantOnboardingState(
    selectedSummary.participantProfileId,
  );
  if (onboarding.required && onboarding.href) redirect(onboarding.href);

  const orderedCycles = [...selectedSummary.cycles].sort(
    (left, right) => left.sequence - right.sequence,
  );
  const cycleSummaries = orderedCycles.length > 0
    ? await Promise.all(
        orderedCycles.map((cycle) =>
          loadCycleSummary(selectedSummary, requestOptions.headers, cycle.id),
        ),
      )
    : [selectedSummary];
  const scopeParams = participantScopeParams(selectedSummary);

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Rezultate"
      description=""
      navItems={participantScopedNavItems(scopeParams)}
      activeHref={participantActiveHref("/participant/results", scopeParams)}
      userLabel={selectedSummary.participantFullName.split(/\s+/)[0] || "Participant"}
      session={participant}
    >
      <ParticipantContextSelector
        contexts={selectedSummary.contexts}
        selectedProfileId={selectedSummary.participantProfileId}
        selectedProjectId={selectedSummary.projectId}
      />

      <header className="mb-10 border-b border-border pb-6">
        <p className="text-sm font-semibold text-burgundy">{selectedSummary.projectName}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-foreground">Istoricul rezultatelor</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Fiecare evaluare rămâne vizibilă. Culorile marchează ciclurile, iar denumirea este afișată lângă fiecare rezultat.
        </p>
        {orderedCycles.length > 0 ? (
          <ul className="mt-5 flex flex-wrap gap-x-5 gap-y-3" aria-label="Legendă cicluri de evaluare">
            {orderedCycles.map((cycle, index) => (
              <li key={cycle.id} className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <span aria-hidden="true" className={cn("size-2.5 rounded-full", CYCLE_ACCENTS[index % CYCLE_ACCENTS.length].dot)} />
                Ciclul {cycle.sequence}: {cycle.name}
              </li>
            ))}
          </ul>
        ) : null}
      </header>

      <div className="grid gap-14">
        {cycleSummaries.map((summary, index) => {
          const cycle = orderedCycles[index];
          const accent = CYCLE_ACCENTS[index % CYCLE_ACCENTS.length];
          return (
            <article
              key={cycle?.id ?? "current"}
              className={cn("border-l-2 pl-5 sm:pl-7", accent.rail)}
              aria-labelledby={`cycle-results-${cycle?.id ?? "current"}`}
            >
              <header className="mb-8 flex flex-col gap-2 border-b border-border pb-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-xs font-semibold text-muted-foreground">
                    {cycle ? `Ciclul ${cycle.sequence}` : "Evaluarea curentă"}
                  </p>
                  <h2 id={`cycle-results-${cycle?.id ?? "current"}`} className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
                    {cycle?.name ?? summary.projectName}
                  </h2>
                </div>
                <p className="text-xs font-semibold text-muted-foreground">
                  {cycle?.status === "active" ? "În desfășurare" : cycle?.status === "closed" ? "Finalizat" : "În pregătire"}
                </p>
              </header>
              <ParticipantResultsPanel
                results={summary.results}
                receivedFeedback={summary.receivedFeedback}
                receivedFeedbackGroups={summary.receivedFeedbackGroups}
                pcmBase={summary.pcmBase}
                pcmPhase={summary.pcmPhase}
                hasTasks={summary.tasks.length > 0}
                allTasksComplete={
                  summary.tasks.length > 0
                  && summary.tasks.every((task) => task.status === "completed")
                }
              />
            </article>
          );
        })}
      </div>
    </AppShell>
  );
}

async function loadCycleSummary(
  selected: ParticipantWorkspaceSummary,
  headers: HeadersInit | undefined,
  cycleId: string,
): Promise<ParticipantWorkspaceSummary> {
  return getParticipantWorkspaceSummary({
    headers,
    participantProfileId: selected.participantProfileId,
    projectId: selected.projectId,
    cycleId,
  });
}
