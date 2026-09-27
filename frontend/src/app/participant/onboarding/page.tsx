import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { ParticipantClientWorkspace } from "../ParticipantClientWorkspace";
import { participantAccountContexts } from "../proiectele-contului";
import { participantWorkspaceRequestOptions, type ParticipantRouteSearchParams } from "../participant-context";

export default async function ParticipantOnboardingPage({
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
  const contexteCont = await participantAccountContexts(requestOptions.headers, routeParams, summary.contexts);

  return (
    <ParticipantClientWorkspace
      session={participant}
      summaryData={summary}
      accountContexts={contexteCont}
    />
  );
}
