import { getParticipantSession } from "@/api/auth-server";
import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { redirect } from "next/navigation";
import { ParticipantClientWorkspace } from "../ParticipantClientWorkspace";

export default async function ParticipantDashboardPage() {
  const [participant, summary, onboarding] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(),
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
