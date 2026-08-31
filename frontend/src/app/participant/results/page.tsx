import { getParticipantSession } from "@/api/auth-server";
import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import {
  getParticipantWorkspaceSummary,
  type ParticipantWorkspaceSummary,
} from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { cycleAccent } from "@/components/reports/cycle-accents";
import { cn } from "@/utils/cn";
import { redirect } from "next/navigation";
import { ParticipantResultsHistory, ParticipantResultsPanel } from "../ParticipantClientWorkspace";
import { ParticipantContextSelector, ParticipantResultCycleControls } from "../ParticipantContextSelector";
import {
  participantActiveHref,
  participantDefaultContext,
  participantScopeParams,
  participantActiveProjectType,
  participantIsTraining,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  firstValue,
  type ParticipantRouteSearchParams,
} from "../participant-context";

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
  if (!participantWorkspaceRequestOptions(undefined, routeParams).projectId) {
    const preferred = participantDefaultContext(selectedSummary.contexts);
    if (preferred) {
      const params = new URLSearchParams({
        profile: preferred.participantProfileId,
        project: preferred.projectId,
      });
      redirect(`/participant/results?${params.toString()}`);
    }
  }
  const onboarding = await getParticipantOnboardingState(
    selectedSummary.participantProfileId,
  );
  if (onboarding.required && onboarding.href) redirect(onboarding.href);

  const orderedCycles = [...selectedSummary.cycles].sort(
    (left, right) => left.sequence - right.sequence,
  );
  const requestedCycleId = firstValue(routeParams.cycle);
  const selectedCycle = orderedCycles.find((cycle) => cycle.id === requestedCycleId) ?? null;
  const defaultBaseline = orderedCycles[0];
  const defaultComparison = orderedCycles.at(-1) ?? defaultBaseline;
  const requestedBaseline = orderedCycles.find((cycle) => cycle.id === firstValue(routeParams.baseline));
  const requestedComparison = orderedCycles.find((cycle) => cycle.id === firstValue(routeParams.compare));
  const baselineCycle = requestedBaseline ?? defaultBaseline;
  const comparisonCycle = requestedComparison && requestedComparison.id !== baselineCycle?.id
    ? requestedComparison
    : [...orderedCycles].reverse().find((cycle) => cycle.id !== baselineCycle?.id) ?? defaultComparison;
  const displayedCycles = selectedCycle
    ? [selectedCycle]
    : [baselineCycle, comparisonCycle].filter(
        (cycle, index, cycles): cycle is NonNullable<typeof cycle> => Boolean(cycle) && cycles.findIndex((candidate) => candidate?.id === cycle.id) === index,
      );
  const cycleSummaries = displayedCycles.length > 0
    ? await Promise.all(displayedCycles.map((cycle) => loadCycleSummary(selectedSummary, requestOptions.headers, cycle.id)))
    : [selectedSummary];
  const scopeParams = participantScopeParams(selectedSummary);
  const projectType = participantActiveProjectType(selectedSummary);
  // Un meniu ascuns nu e o regulă, e o sugestie: un om de la training
  // care scrie adresa direct în bară e trimis înapoi, nu i se arată ecranul.
  if (participantIsTraining(projectType)) redirect("/participant");

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Rezultate"
      description=""
      navItems={participantScopedNavItems(scopeParams, projectType)}
      activeHref={participantActiveHref("/participant/results", scopeParams)}
      userLabel={selectedSummary.participantFullName.split(/\s+/)[0] || "Participant"}
      session={participant}
    >
      <ParticipantContextSelector
        contexts={selectedSummary.contexts}
        selectedProfileId={selectedSummary.participantProfileId}
        selectedProjectId={selectedSummary.projectId}
      />
      {baselineCycle && comparisonCycle ? (
        <ParticipantResultCycleControls
          cycles={orderedCycles}
          cycleId={selectedCycle?.id}
          baselineId={baselineCycle.id}
          compareId={comparisonCycle.id}
        />
      ) : null}

      <header className="mb-9 max-w-3xl">
        <p className="text-xs font-semibold text-brand-text">{selectedSummary.projectName}</p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
          {selectedCycle ? selectedCycle.name : "Evoluția rezultatelor"}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          {selectedCycle
            ? "Scorurile și interpretările disponibile pentru evaluarea selectată."
            : "Compară prima evaluare cu cea mai recentă pe aceleași dimensiuni."}
        </p>
        {orderedCycles.length > 0 ? (
          <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2" aria-label="Legendă cicluri de evaluare">
            {displayedCycles.map((cycle, index) => (
              <li key={cycle.id} className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <span aria-hidden="true" className={cn("size-2.5 rounded-full", cycleAccent(index).dot)} />
                Ciclul {cycle.sequence}: {cycle.name}
              </li>
            ))}
          </ul>
        ) : null}
      </header>

      {!selectedCycle && displayedCycles.length > 1 ? (
        <ParticipantResultsHistory
          cycles={cycleSummaries.map((summary, index) => ({
            cycle: displayedCycles[index],
            results: summary.results,
            receivedFeedback: summary.receivedFeedback,
            receivedFeedbackGroups: summary.receivedFeedbackGroups,
            pcmBase: summary.pcmBase,
            pcmPhase: summary.pcmPhase,
          }))}
        />
      ) : (
        <ParticipantResultsPanel
          results={cycleSummaries[0].results}
          receivedFeedback={cycleSummaries[0].receivedFeedback}
          receivedFeedbackGroups={cycleSummaries[0].receivedFeedbackGroups}
          pcmBase={cycleSummaries[0].pcmBase}
          pcmPhase={cycleSummaries[0].pcmPhase}
          hasTasks={cycleSummaries[0].tasks.length > 0}
          allTasksComplete={
            cycleSummaries[0].tasks.length > 0
            && cycleSummaries[0].tasks.every((task) => task.status === "completed")
          }
        />
      )}
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
