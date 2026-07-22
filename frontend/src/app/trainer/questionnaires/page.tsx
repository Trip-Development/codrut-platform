import { getTrainerSession } from "@/api/auth-server";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { LazyQuestionnairesWorkspace } from "./LazyQuestionnairesWorkspace";

export default async function TrainerQuestionnairesPage() {
  const trainer = await getTrainerSession();

  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title="Chestionare"
      description=""
      navItems={trainerNavItems}
      activeHref="/trainer/questionnaires"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <LazyQuestionnairesWorkspace />
    </AppShell>
  );
}
