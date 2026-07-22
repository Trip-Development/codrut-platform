import { notFound } from "next/navigation";

import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyCompanySettingsWorkspace } from "./LazyCompanySettingsWorkspace";

export default async function CompanySettingsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const [{ companyId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const company = await getCompanyDetail(companyId, requestOptions);

  if (!company) {
    notFound();
  }

  return <LazyCompanySettingsWorkspace company={company} />;
}
