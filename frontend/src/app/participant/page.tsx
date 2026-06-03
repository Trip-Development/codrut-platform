import { audienceAccessNote, getParticipantSession } from "@/api/auth";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { EmptyState } from "@/components/presentation/empty-state";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";

export default async function ParticipantWorkspacePage() {
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(),
  ]);

  return (
    <AppShell
      audience="participant"
      eyebrow="Participant"
      title="Sarcinile tale Codrut"
      description="Participantul vede doar propriile task-uri si chestionare asignate, nu organigrama completa a companiei."
      navItems={participantNavItems}
      activeHref="/participant"
      userLabel={participant.user.name}
      session={participant}
      accessNote={audienceAccessNote("participant")}
    >
      <div className="grid gap-4 md:grid-cols-3">
        {summary.cards.map((card) => (
          <PlaceholderCard key={card.title} {...card} />
        ))}
      </div>

      <div className="mt-4">
        <EmptyState {...summary.emptyState} />
      </div>
    </AppShell>
  );
}
