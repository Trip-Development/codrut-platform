import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { redirect } from "next/navigation";
import { ParticipantResultsPanel } from "../ParticipantClientWorkspace";

export default async function ParticipantResultsPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [summary, onboarding] = await Promise.all([
    getParticipantWorkspaceSummary(requestOptions),
    getParticipantOnboardingState(),
  ]);

  if (onboarding.required && onboarding.href) {
    redirect(onboarding.href);
  }

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Rezultate"
      description=""
      navItems={participantNavItems}
      activeHref="/participant/results"
      userLabel={summary.participantFullName.split(/\s+/)[0] || "Participant"}
    >
      <ParticipantResultsPanel
        results={summary.results}
        receivedFeedback={summary.receivedFeedback}
        receivedFeedbackGroups={summary.receivedFeedbackGroups}
        pcmBase={summary.pcmBase}
        pcmPhase={summary.pcmPhase}
        hasTasks={summary.tasks.length > 0}
        allTasksComplete={summary.tasks.length > 0 && summary.tasks.every((task) => task.status === "completed")}
      />
    </AppShell>
  );
}
