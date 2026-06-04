import { getTrainerSession } from "@/api/auth";
import { getCompanyList } from "@/api/companies";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

import { RosterImporter } from "./roster-importer";

export default async function TrainerRosterPage() {
  const [trainer, companies] = await Promise.all([getTrainerSession(), getCompanyList()]);

  return (
    <AppShell
      audience="trainer"
      eyebrow="Roster"
      title="Import participanti"
      description="Incarca fisierul de organizatie si valideaza coloanele inainte de importul in proiect."
      navItems={trainerNavItems}
      activeHref="/trainer/roster"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <RosterImporter companies={companies.map(({ id, name }) => ({ id, name }))} />
    </AppShell>
  );
}
