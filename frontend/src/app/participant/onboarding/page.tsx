import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { ParticipantClientWorkspace } from "../ParticipantClientWorkspace";

export default async function ParticipantOnboardingPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(requestOptions),
  ]);

  return (
    <ParticipantClientWorkspace
      session={participant}
      summaryData={summary}
    />
  );
}
