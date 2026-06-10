import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { CompanySettingsWorkspace } from "./CompanySettingsWorkspace";

export default async function CompanySettingsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const company = await getCompanyDetail(companyId, await getServerApiRequestOptions());

  if (!company) {
    return (
      <section className="rounded-2xl border border-dashed border-[var(--border)] bg-surface/70 p-8 text-center">
        <p className="text-base font-semibold text-foreground">Compania nu a fost găsită.</p>
      </section>
    );
  }

  return <CompanySettingsWorkspace company={company} />;
}
