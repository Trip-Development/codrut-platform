import { getTrainerSession } from "@/api/auth-server";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { QuestionnairesWorkspace } from "./QuestionnairesWorkspace";

export default async function TrainerQuestionnairesPage() {
  const trainer = await getTrainerSession();

  return (
    <AppShell
      audience="trainer"
      eyebrow="Chestionare"
      title="Catalog chestionare și versiuni"
      description="Coordonarea formelor Codrut-native: definitii versionate, persoane asignate, drafturi si submit-uri."
      navItems={trainerNavItems}
      activeHref="/trainer/questionnaires"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <QuestionnairesWorkspace />
    </AppShell>
  );
}
