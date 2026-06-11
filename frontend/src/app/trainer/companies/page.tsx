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
      eyebrow="Companii"
      title="Companiile tale"
      description="Lista companiilor cu care lucrezi, statusul fiecărei companii și progresul operațional."
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
    >
      <CompaniesWorkspace initialCompanies={companies} />
    </AppShell>
  );
}
