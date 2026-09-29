import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import {
  participantActiveHref,
  participantCanViewResults,
  participantScopeParams,
  participantActiveProjectType,
  participantDisplayName,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";
import { AccountWorkspace } from "./AccountWorkspace";
import { participantAccountContexts } from "../proiectele-contului";

export default async function ParticipantAccountPage({
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

  // plicul 166 A4: în meniu, numele din profil; adresa rămâne numai în conținutul paginii Cont
  const name = participantDisplayName(summary);
  const scopeParams = participantScopeParams(summary);
  const projectType = participantActiveProjectType(summary);

  const contexteCont = await participantAccountContexts(requestOptions.headers, routeParams, summary.contexts);
  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Contul tău"
      description=""
      navItems={participantScopedNavItems(scopeParams, {
        projectType,
        showResults: participantCanViewResults(summary),
        contexts: contexteCont,
      })}
      activeHref={participantActiveHref("/participant/account", scopeParams)}
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
      <AccountWorkspace session={participant} summary={summary} />
    </AppShell>
  );
}
