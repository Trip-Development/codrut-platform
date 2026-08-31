import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import {
  participantActiveHref,
  participantScopeParams,
  participantActiveProjectType,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";
import { AccountWorkspace } from "./AccountWorkspace";

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

  const name = summary.participantFullName || participant.user.name || participant.user.id;
  const scopeParams = participantScopeParams(summary);
  const projectType = participantActiveProjectType(summary);

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Contul tău"
      description=""
      navItems={participantScopedNavItems(scopeParams, projectType)}
      activeHref={participantActiveHref("/participant/account", scopeParams)}
      userLabel={name.split(" ")[0]}
      session={participant}
    >
      <ParticipantContextSelector
        contexts={summary.contexts}
        selectedProfileId={summary.participantProfileId}
        selectedProjectId={summary.projectId}
      />
      <AccountWorkspace session={participant} summary={summary} />
    </AppShell>
  );
}
