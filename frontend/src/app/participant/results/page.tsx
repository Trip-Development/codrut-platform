import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import {
  getParticipantWorkspaceSummary,
  type ParticipantWorkspaceSummary,
} from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { redirect } from "next/navigation";
import {
  ParticipantResultsPanel,
  type ParticipantResultsComparison,
} from "../ParticipantClientWorkspace";
import {
  ParticipantContextSelector,
  ParticipantResultCycleControls,
} from "../ParticipantContextSelector";
import {
  firstValue,
  participantActiveHref,
  participantScopeParams,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";

export default async function ParticipantResultsPage({
  searchParams,
}: {
  searchParams: Promise<ParticipantRouteSearchParams>;
}) {
  const routeParams = await searchParams;
  const requestOptions = await getServerApiRequestOptions();
  const requestedComparisonId = firstValue(routeParams.compare);
  const requestedCycleId = requestedComparisonId ?? firstValue(routeParams.cycle);
  const selectedSummary = await getParticipantWorkspaceSummary({
      ...participantWorkspaceRequestOptions(requestOptions.headers, routeParams),
      cycleId: requestedCycleId,
  });
  const onboarding = await getParticipantOnboardingState(
    selectedSummary.participantProfileId,
  );

  if (onboarding.required && onboarding.href) redirect(onboarding.href);

  const orderedCycles = [...selectedSummary.cycles].sort((left, right) => left.sequence - right.sequence);
  const currentCycle =
    orderedCycles.find((cycle) => cycle.id === selectedSummary.assessmentCycleId) ??
    orderedCycles.at(-1);
  const requestedBaselineId = firstValue(routeParams.baseline);
  const comparisonEnabled = Boolean(
    requestedBaselineId &&
      requestedComparisonId &&
      requestedBaselineId !== requestedComparisonId &&
      orderedCycles.some((cycle) => cycle.id === requestedBaselineId) &&
      orderedCycles.some((cycle) => cycle.id === requestedComparisonId),
  );

  let displaySummary = selectedSummary;
  let comparison: ParticipantResultsComparison | null = null;
  let canCompare = false;

  if (comparisonEnabled && requestedBaselineId && requestedComparisonId) {
    const [baselineSummary, currentSummary] = await Promise.all([
      loadCycleSummary(selectedSummary, requestOptions.headers, requestedBaselineId),
      selectedSummary.assessmentCycleId === requestedComparisonId
        ? Promise.resolve(selectedSummary)
        : loadCycleSummary(selectedSummary, requestOptions.headers, requestedComparisonId),
    ]);
    displaySummary = currentSummary;
    comparison = {
      baselineLabel: cycleLabel(orderedCycles, requestedBaselineId),
      currentLabel: cycleLabel(orderedCycles, requestedComparisonId),
      baselineResults: baselineSummary.results,
      baselineReceivedFeedback: baselineSummary.receivedFeedback,
      baselineReceivedFeedbackGroups: baselineSummary.receivedFeedbackGroups,
      baselinePcmBase: baselineSummary.pcmBase,
      baselinePcmPhase: baselineSummary.pcmPhase,
    };
    canCompare = hasComparisonData(baselineSummary) && hasComparisonData(currentSummary);
  } else if (currentCycle) {
    const currentIndex = orderedCycles.findIndex((cycle) => cycle.id === currentCycle.id);
    const previousCycle = currentIndex > 0 ? orderedCycles[currentIndex - 1] : undefined;
    if (previousCycle && hasComparisonData(selectedSummary)) {
      const previousSummary = await loadCycleSummary(
        selectedSummary,
        requestOptions.headers,
        previousCycle.id,
      );
      canCompare = hasComparisonData(previousSummary);
    }
  }

  const scopeParams = participantScopeParams(displaySummary);
  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Rezultate"
      description=""
      navItems={participantScopedNavItems(scopeParams)}
      activeHref={participantActiveHref("/participant/results", scopeParams)}
      userLabel={displaySummary.participantFullName.split(/\s+/)[0] || "Participant"}
    >
      <ParticipantContextSelector
        contexts={displaySummary.contexts}
        selectedProfileId={displaySummary.participantProfileId}
        selectedProjectId={displaySummary.projectId}
      />
      <ParticipantResultCycleControls
        cycles={orderedCycles}
        currentCycleId={displaySummary.assessmentCycleId}
        baselineCycleId={comparisonEnabled ? requestedBaselineId : null}
        comparisonCycleId={comparisonEnabled ? requestedComparisonId : null}
        canCompare={canCompare}
      />
      <ParticipantResultsPanel
        results={displaySummary.results}
        receivedFeedback={displaySummary.receivedFeedback}
        receivedFeedbackGroups={displaySummary.receivedFeedbackGroups}
        pcmBase={displaySummary.pcmBase}
        pcmPhase={displaySummary.pcmPhase}
        hasTasks={displaySummary.tasks.length > 0}
        allTasksComplete={
          displaySummary.tasks.length > 0 &&
          displaySummary.tasks.every((task) => task.status === "completed")
        }
        comparison={comparison}
      />
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

function cycleLabel(
  cycles: ParticipantWorkspaceSummary["cycles"],
  cycleId: string,
): string {
  return cycles.find((cycle) => cycle.id === cycleId)?.name ?? "Evaluare";
}

function hasComparisonData(summary: ParticipantWorkspaceSummary): boolean {
  return (
    summary.results.length > 0 ||
    summary.receivedFeedbackGroups.some((feedback) => feedback.visible) ||
    Boolean(summary.receivedFeedback?.visible)
  );
}
