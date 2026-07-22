import { getParticipantSession } from "@/api/auth-server";
import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { redirect } from "next/navigation";
import { AccountWorkspace } from "./AccountWorkspace";

export default async function ParticipantAccountPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary, onboarding] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(requestOptions),
    getParticipantOnboardingState(),
  ]);

  if (onboarding.required && onboarding.href) {
    redirect(onboarding.href);
  }

  const name = summary.participantFullName || participant.user.name || participant.user.id;

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Contul tău"
      description=""
      navItems={participantNavItems}
      activeHref="/participant/account"
      userLabel={name.split(" ")[0]}
      session={participant}
    >
      <AccountWorkspace session={participant} summary={summary} />
    </AppShell>
  );
}
