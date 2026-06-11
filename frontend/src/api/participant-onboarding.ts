import "server-only";

import { cookies } from "next/headers";

import { getApiBaseUrl } from "./runtime";

export type ParticipantOnboardingState = {
  required: boolean;
  questionnaire_key: string | null;
  assignment_id: string | null;
  href: string | null;
};

export async function getParticipantOnboardingState(): Promise<ParticipantOnboardingState> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("codrut_session");
  if (!sessionCookie?.value) {
    return emptyOnboarding();
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/participant/onboarding`, {
      cache: "no-store",
      headers: {
        Cookie: `codrut_session=${sessionCookie.value}`,
      },
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
