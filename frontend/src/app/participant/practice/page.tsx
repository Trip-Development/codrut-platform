import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import {
  participantActiveHref,
  participantScopeParams,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";
import { PracticeWorkspace } from "./PracticeWorkspace";

export default async function ParticipantPracticePage({
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

  const name = summary.participantFullName || participant.user.name || participant.user.id;
  const scopeParams = participantScopeParams(summary);

  return (
    <AppShell
      audience="participant"
      eyebrow="Antrenament cu Cody"
      title="Conversație de practică"
      description="Exersează comunicarea asertivă și feedbackul în scenarii simulate cu inteligență artificială"
      navItems={participantScopedNavItems(scopeParams)}
      activeHref={participantActiveHref("/participant/practice", scopeParams)}
      userLabel={name.split(" ")[0]}
      session={participant}
    >
      <ParticipantContextSelector
        contexts={summary.contexts}
        selectedProfileId={summary.participantProfileId}
        selectedProjectId={summary.projectId}
      />
      <PracticeWorkspace
        projectId={summary.projectId}
      />
    </AppShell>
  );
}
