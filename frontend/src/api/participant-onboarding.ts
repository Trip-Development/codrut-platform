import "server-only";

import { getApiBaseUrl } from "./runtime";
import { getServerApiRequestOptions } from "./server-request";

export type ParticipantOnboardingState = {
  required: boolean;
  questionnaire_key: string | null;
  assignment_id: string | null;
  href: string | null;
};

export async function getParticipantOnboardingState(): Promise<ParticipantOnboardingState> {
  const requestOptions = await getServerApiRequestOptions();

  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/participant/onboarding`, {
      cache: "no-store",
      ...requestOptions,
    });
    if (!response.ok) {
      return emptyOnboarding();
    }
    return (await response.json()) as ParticipantOnboardingState;
  } catch {
    return emptyOnboarding();
  }
}

function emptyOnboarding(): ParticipantOnboardingState {
  return {
    required: false,
    questionnaire_key: null,
    assignment_id: null,
    href: null,
  };
}
