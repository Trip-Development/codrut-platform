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

  // Un chestionar care nu se poate cere NU are voie sa inchida tot spatiul — plicul 127.
  //
  // Pe 22 septembrie (`Ref: 3146487137`) cererea a raspuns 400, fiindca definitia chestionarului
  // PCM lipsea din baza de proba. Functia arunca, iar paginile care o cheama PRIMA cadeau
  // intregi: omul vedea „Nu am putut incarca pagina", fara sa afle ce si de ce.
  //
  // Acum: orice necaz inseamna „nu e cerut niciun chestionar". Spatiul se deschide, fara anunt.
  // Cele doua feluri de necaz sunt amandoua aici: un raspuns de eroare, si o cerere care nu
  // ajunge deloc (backend repornit, retea cazuta) — la a doua `fetch` ARUNCA, nu raspunde.
  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/participant/onboarding?${params}`, {
      cache: "no-store",
      ...requestOptions,
    });
    if (!response.ok) {
      console.error(
        `[onboarding] cererea a raspuns ${response.status}; spatiul se deschide fara anunt.`,
      );
      return emptyOnboarding();
    }
    return (await response.json()) as ParticipantOnboardingState;
  } catch (error) {
    console.error("[onboarding] cererea nu a ajuns; spatiul se deschide fara anunt.", error);
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
