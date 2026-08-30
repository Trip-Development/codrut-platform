import { AppShell } from "@/components/shell/app-shell";
import { getParticipantSession } from "@/api/auth-server";
import { PracticeParticipantDashboard } from "../dashboard/PracticeParticipantDashboard";

export default async function TablouParticipantPage() {
  const participant = await getParticipantSession();
  const participantFirstName =
    participant?.user?.name?.split(/\s+/)[0] || "Participant";

  return (
    <AppShell
      audience="participant"
      eyebrow="Antrenament & Competențe"
      title={`Tabloul tău, ${participantFirstName}`}
      description="Evoluția deprinderilor dobândite în simulările de conversație cu Cody."
      userLabel={participantFirstName}
      session={participant}
    >
      <div className="max-w-5xl mx-auto w-full">
        <PracticeParticipantDashboard />
      </div>
    </AppShell>
  );
}
