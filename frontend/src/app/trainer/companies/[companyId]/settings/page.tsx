import { notFound } from "next/navigation";

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
    notFound();
  }

  return <CompanySettingsWorkspace company={company} />;
}
