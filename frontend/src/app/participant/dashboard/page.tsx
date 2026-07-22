import { getParticipantSession } from "@/api/auth-server";
import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { redirect } from "next/navigation";
import { ParticipantClientWorkspace } from "../ParticipantClientWorkspace";
import { participantWorkspaceRequestOptions, type ParticipantRouteSearchParams } from "../participant-context";

export default async function ParticipantDashboardPage({
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
  const onboarding = await getParticipantOnboardingState(summary.participantProfileId);

  if (onboarding.required && onboarding.href) {
    redirect(onboarding.href);
  }

  return (
    <ParticipantClientWorkspace
      session={participant}
      summaryData={summary}
    />
  );
}
