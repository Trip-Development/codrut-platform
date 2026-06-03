import { audienceAccessNote, getParticipantSession } from "@/api/auth";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";
import { TaskBundle } from "@/components/tasks/task-bundle";

export default async function ParticipantWorkspacePage() {
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(),
  ]);

  return (
    <AppShell
      audience="participant"
      eyebrow="Participant"
      title="Sarcinile tale pentru proiect"
      description="Aici vezi doar chestionarele asociate emailului tau in proiectul curent. Nu ai acces la organigrama sau la raspunsurile altor persoane."
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

      <div className="mt-5">
        <TaskBundle
          tasks={summary.tasks}
          projectName={summary.projectName}
          participantEmail={summary.participantEmail}
          deadlineLabel={summary.deadlineLabel}
          compact
        />
      </div>
    </AppShell>
  );
}
