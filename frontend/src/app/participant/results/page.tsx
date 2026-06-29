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
      eyebrow={summary.projectName}
      title="Rezultatele tale"
      description="Scoruri sumarizate pentru chestionarele finalizate. Răspunsurile brute rămân private."
      navItems={participantNavItems}
      activeHref="/participant/results"
      userLabel={summary.anonymousName ?? "Profil anonim"}
    >
      <ParticipantResultsPanel
        results={summary.results}
        pcmBase={summary.pcmBase}
        pcmPhase={summary.pcmPhase}
      />
    </AppShell>
  );
}
