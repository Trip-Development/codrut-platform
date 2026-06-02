import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";

export default function TrainerQuestionnairesPage() {
  return (
    <AppShell
      audience="trainer"
      eyebrow="Chestionare"
      title="Assignment si completare"
      description="Coordonarea formelor Codrut-native: definitii versionate, persoane asignate, drafturi si submit-uri."
      navItems={trainerNavItems}
      activeHref="/trainer/questionnaires"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <PlaceholderCard title="Definitii" description="PCM baseline, Phase A, distress drivers si formele aprobate." />
        <PlaceholderCard title="Asignari" description="Task-uri pe persoana, rol/grup si context organizational." />
        <PlaceholderCard title="Completare" description="Pornit, draft, trimis, validat si scorabil." />
      </div>
    </AppShell>
  );
}
