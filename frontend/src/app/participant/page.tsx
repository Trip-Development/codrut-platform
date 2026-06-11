import { getParticipantSession } from "@/api/auth-server";
import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { redirect } from "next/navigation";
import { ParticipantClientWorkspace } from "./ParticipantClientWorkspace";

export default async function ParticipantWorkspacePage() {
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary, onboarding] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(requestOptions),
    getParticipantOnboardingState(),
  ]);

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
