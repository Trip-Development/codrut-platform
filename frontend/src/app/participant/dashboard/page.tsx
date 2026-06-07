import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { ParticipantClientWorkspace } from "../ParticipantClientWorkspace";

export default async function ParticipantDashboardPage() {
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(),
  ]);

  return (
    <ParticipantClientWorkspace
      session={participant}
      summaryData={summary}
    />
  );
}
