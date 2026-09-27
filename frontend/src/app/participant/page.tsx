import { redirect } from "next/navigation";

import { getParticipantSession } from "@/api/auth-server";
import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { ParticipantClientWorkspace } from "./ParticipantClientWorkspace";
import { participantAccountContexts } from "./proiectele-contului";
import {
  participantScopedHref,
  participantShouldOpenWelcome,
  participantWorkspaceRequestOptions,
  PARTICIPANT_WELCOME_PATH,
  type ParticipantRouteSearchParams,
} from "./participant-context";

export default async function ParticipantWorkspacePage({
  searchParams,
}: {
  searchParams: Promise<ParticipantRouteSearchParams>;
}) {
  const routeParams = await searchParams;
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(participantWorkspaceRequestOptions(requestOptions.headers, routeParams)),
  ]);
  // Plicul 160 B: omul cu 2+ proiecte, fără proiect ales (și după login), ajunge la bun venit.
  // Cu un singur proiect, sau cu proiectul ales în adresă, pagina e cea de până acum.
  const contexteCont = await participantAccountContexts(requestOptions.headers, routeParams, summary.contexts);
  if (participantShouldOpenWelcome(routeParams, contexteCont)) {
    const params = new URLSearchParams();
    const profil = routeParams.profile;
    if (typeof profil === "string" && profil) params.set("profile", profil);
    redirect(participantScopedHref(PARTICIPANT_WELCOME_PATH, params));
  }
  const onboarding = await getParticipantOnboardingState(summary.participantProfileId);

  // Chestionarul se CERE, nu se IMPUNE — plicul 127, hotararea lui Andrei din 22 septembrie:
  // „Am partea de chestionare, si am partea de exersat cu Cody. Ce treaba are una cu alta?"
  //
  // Pana azi aici era `redirect(onboarding.href)`: un om fara PCM completat era trimis fortat la
  // chestionar si n-avea alta usa — nici spre Cody, nici spre altceva. Acum spatiul se deschide
  // mereu, iar chestionarul ramas de completat ajunge acolo ca ANUNT, cu legatura lui.
  //
  // Regula din backend nu s-a atins: „fara PCM → ti se cere PCM" e tot adevarata.
  return (
    <ParticipantClientWorkspace
      session={participant}
      summaryData={summary}
      accountContexts={contexteCont}
      onboardingHref={onboarding.required ? onboarding.href : null}
    />
  );
}
