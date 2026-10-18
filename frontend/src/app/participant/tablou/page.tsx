import { redirect } from "next/navigation";

import { AppShell } from "@/components/shell/app-shell";
import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { PracticeParticipantDashboard } from "../dashboard/PracticeParticipantDashboard";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import {
  PARTICIPANT_WELCOME_PATH,
  participantActiveHref,
  participantActiveProjectType,
  participantDisplayName,
  participantScopeParams,
  participantScopedHref,
  participantScopedNavItems,
  participantShouldOpenWelcome,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";
import { TRAINING_PROJECT_TYPE } from "@/components/shell/nav";
import { participantAccountContexts } from "../proiectele-contului";

/**
 * Tabloul, pe proiectul ALES de om — plicul 143.
 *
 * Până la 143 pagina nu citea deloc contextul: tabloul se cerea fără proiect, deci serverul nu
 * avea de unde să știe competențele alese de trainer și arăta lista fixă din aplicația veche.
 * Acum proiectul vine din același loc ca la ecranul de exersare (rezumatul spațiului omului).
 */
export default async function TablouParticipantPage({
  searchParams,
}: {
  searchParams?: Promise<ParticipantRouteSearchParams>;
}) {
  const routeParams = (await searchParams) ?? {};
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(
      participantWorkspaceRequestOptions(requestOptions.headers, routeParams),
    ).catch(() => null),
  ]);
  // plicul 166 A4: numele din profil, niciodată cel făcut din adresă
  const participantFirstName = participantDisplayName(summary);
  const scopeParams = summary ? participantScopeParams(summary) : new URLSearchParams();
  const projectType =
    (summary ? participantActiveProjectType(summary) : null) ?? TRAINING_PROJECT_TYPE;

  const contexteCont = await participantAccountContexts(requestOptions.headers, routeParams, summary?.contexts);
  // Plicul 190: omul cu 2+ proiecte, fără proiect ales, ajunge la bun venit — ca la „Acasă” (160 B).
  // Fără gardă, cu Tabloul pe proiect (184), ar fi văzut 0 / „Încă nu ai exersat.”.
  if (participantShouldOpenWelcome(routeParams, contexteCont)) {
    const params = new URLSearchParams();
    const profil = routeParams.profile;
    if (typeof profil === "string" && profil) params.set("profile", profil);
    redirect(participantScopedHref(PARTICIPANT_WELCOME_PATH, params));
  }
  return (
    <AppShell
      audience="participant"
      eyebrow="Antrenament & Competențe"
      title="Tabloul tău"
      description="Evoluția deprinderilor dobândite în simulările de conversație cu Cody."
      navItems={participantScopedNavItems(scopeParams, { projectType, contexts: contexteCont })}
      activeHref={participantActiveHref("/participant/tablou", scopeParams)}
      userLabel={participantFirstName}
      session={participant}
      sidebarTop={
        <ParticipantContextSelector
          contexts={contexteCont}
          selectedProfileId={summary?.participantProfileId}
          selectedProjectId={summary?.projectId}
        />
      }
    >
      <div className="max-w-5xl mx-auto w-full">
        <PracticeParticipantDashboard projectId={summary?.projectId ?? null} />
      </div>
    </AppShell>
  );
}
