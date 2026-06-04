import { getTrainerSession } from "@/api/auth";
import { getCompanyDetail, getCompanyList } from "@/api/companies";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

import { OrgExplorer, type OrgExplorerCompany } from "./org-explorer";

export default async function TrainerOrgPage() {
  const [trainer, companies] = await Promise.all([getTrainerSession(), getCompanyList()]);
  const details = await Promise.all(companies.map((company) => getCompanyDetail(company.id)));
  const explorerCompanies: OrgExplorerCompany[] = details
    .filter((company): company is NonNullable<typeof company> => Boolean(company))
    .map((company) => ({
      id: company.id,
      name: company.name,
      participants: company.participants,
    }));

  return (
    <AppShell
      audience="trainer"
      eyebrow="Organigrama"
      title="Harta organizatiei"
      description="Exploreaza ierarhia activa din roster, cauta persoane si restrange ramuri pentru validarea relatiei manageriale."
      navItems={trainerNavItems}
      activeHref="/trainer/org"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <OrgExplorer companies={explorerCompanies} />
    </AppShell>
  );
}
