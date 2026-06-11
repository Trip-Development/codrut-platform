import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { AccountWorkspace } from "./AccountWorkspace";

export default async function ParticipantAccountPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(requestOptions),
  ]);

  const name = summary.participantFullName || participant.user.name || participant.user.id;

  return (
    <AppShell
      audience="participant"
      eyebrow="Profil"
      title="Contul tău"
      description="Aici poți vedea detaliile contului tău corporate, integrarea cu programul de training și setările de confidențialitate."
      navItems={participantNavItems}
      activeHref="/participant/account"
      userLabel={name.split(" ")[0]}
      session={participant}
    >
      <AccountWorkspace session={participant} summary={summary} />
    </AppShell>
  );
}
