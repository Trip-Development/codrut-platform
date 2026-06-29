import { getCompanyList } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { CompaniesWorkspace } from "./CompaniesWorkspace";

export default async function TrainerCompaniesPage() {
  const companies = await getCompanyList(await getServerApiRequestOptions());

  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title="Companiile tale"
      description="Caută rapid o companie și intră în spațiul ei pentru proiecte, participanți și echipe."
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
    >
      <CompaniesWorkspace initialCompanies={companies} />
    </AppShell>
  );
}
