import "server-only";

import { getApiBaseUrl } from "./runtime";
import { getServerApiRequestOptions } from "./server-request";

export type ParticipantOnboardingState = {
  required: boolean;
  questionnaire_key: string | null;
  assignment_id: string | null;
  href: string | null;
};

export async function getParticipantOnboardingState(
  participantProfileId?: string | null,
): Promise<ParticipantOnboardingState> {
  if (!participantProfileId) return emptyOnboarding();
  const requestOptions = await getServerApiRequestOptions();

  const params = new URLSearchParams({ participant_profile_id: participantProfileId });
  const response = await fetch(`${getApiBaseUrl()}/forms/participant/onboarding?${params}`, {
      cache: "no-store",
      ...requestOptions,
  });
  if (!response.ok) {
    throw new Error(`Participant onboarding request failed (${response.status}).`);
  }
  return (await response.json()) as ParticipantOnboardingState;
}

function emptyOnboarding(): ParticipantOnboardingState {
  return {
    required: false,
    questionnaire_key: null,
    assignment_id: null,
    href: null,
  };
}
