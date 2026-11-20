import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import {
  participantActiveHref,
  participantScopeParams,
  participantScopedHref,
  participantActiveProjectType,
  participantDisplayName,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";
import { participantAccountContexts } from "../proiectele-contului";
import { AlegereaObiectivului } from "./AlegereaObiectivului";
import { TEXTE } from "./texte";

// Plicul 232: omul își alege obiectivul de aplicare. Ruta stă sub /participant, deci e
// păzită de middleware și de participant/layout.tsx, ca toate paginile omului.
export default async function ParticipantObiectivPage({
  searchParams,
}: {
  searchParams: Promise<ParticipantRouteSearchParams>;
}) {
  const routeParams = await searchParams;
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(
      participantWorkspaceRequestOptions(requestOptions.headers, routeParams),
    ),
  ]);

  const name = participantDisplayName(summary);
  const scopeParams = participantScopeParams(summary);
  const projectType = participantActiveProjectType(summary);
  const contexteCont = await participantAccountContexts(requestOptions.headers, routeParams, summary.contexts);
  const inapoiHref = participantScopedHref("/participant/practice", scopeParams);

  return (
    <AppShell
      audience="participant"
      eyebrow={TEXTE.T12.eyebrow}
      title={TEXTE.T12.title}
      description={TEXTE.T12.description}
      navItems={participantScopedNavItems(scopeParams, { projectType, contexts: contexteCont })}
      activeHref={participantActiveHref("/participant/practice", scopeParams)}
      userLabel={name.split(" ")[0]}
      session={participant}
      sidebarTop={
        <ParticipantContextSelector
          contexts={contexteCont}
          selectedProfileId={summary.participantProfileId}
          selectedProjectId={summary.projectId}
        />
      }
    >
      <AlegereaObiectivului projectId={summary.projectId ?? ""} inapoiHref={inapoiHref} />
    </AppShell>
  );
}
