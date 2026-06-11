import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { CompanyTabs } from "./CompanyTabs";

export default async function CompanyDetailLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const company = await getCompanyDetail(companyId, await getServerApiRequestOptions());
  const companyName = company?.name ?? "Companie";
  const basePath = `/trainer/companies/${companyId}`;

  return (
    <AppShell
      audience="trainer"
      eyebrow="Companie"
      title={companyName}
      description={`Spațiu pentru participanți, organigramă, echipe, invitații și rapoarte pentru ${companyName}.`}
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
    >
      <CompanyTabs basePath={basePath} />

      {children}
    </AppShell>
  );
}
