import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

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

  return (
    <AppShell
      audience="trainer"
      eyebrow="Companie"
      title={companyName}
      description={`Pagina companiei pentru proiecte active, sumar operațional și setări administrative pentru ${companyName}.`}
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
    >
      {children}
    </AppShell>
  );
}
