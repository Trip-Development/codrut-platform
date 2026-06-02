import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";

export default function ParticipantQuestionnairesPage() {
  return (
    <AppShell
      audience="participant"
      eyebrow="Chestionare"
      title="Formele asignate tie"
      description="Flow-ul real va folosi definitii versionate si submit server-validat. Acum pastram suprafata vizuala."
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
    >
      <PlaceholderCard
        title="Questionnaire runner"
        description="Placeholder pentru PCM baseline, Phase A, distress drivers si formularele aprobate."
      />
    </AppShell>
  );
}
