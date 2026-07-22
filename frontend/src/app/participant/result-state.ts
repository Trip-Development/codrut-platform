import type {
  ParticipantReceivedFeedbackSummary,
  ParticipantWorkspaceResult,
} from "@/api/participants";

type ParticipantResultState = {
  results: ParticipantWorkspaceResult[];
  receivedFeedback?: ParticipantReceivedFeedbackSummary | null;
  receivedFeedbackGroups?: ParticipantReceivedFeedbackSummary[];
  pcmBase?: string | null;
  pcmPhase?: string | null;
};

export function mergeParticipantFeedbackGroups(
  groups: ParticipantReceivedFeedbackSummary[] = [],
  legacy?: ParticipantReceivedFeedbackSummary | null,
): ParticipantReceivedFeedbackSummary[] {
  const merged = legacy ? [...groups, legacy] : groups;
  const seen = new Set<string>();
  return merged.filter((feedback) => {
    const identity = feedback.assignmentRoundId
      ? `round:${feedback.assignmentRoundId}`
      : [
          feedback.projectId ?? feedback.projectName ?? "none",
          feedback.questionnaireKey ?? feedback.questionnaireTitle ?? "legacy",
        ].join(":");
    if (seen.has(identity)) return false;
    seen.add(identity);
    return true;
  });
}

export function countAvailableParticipantResults(state: ParticipantResultState): number {
  const visibleFeedbackCount = mergeParticipantFeedbackGroups(
    state.receivedFeedbackGroups,
    state.receivedFeedback,
  ).filter((feedback) => feedback.visible).length;
  const profileResultCount = state.pcmBase || state.pcmPhase ? 1 : 0;
  return state.results.length + visibleFeedbackCount + profileResultCount;
}
