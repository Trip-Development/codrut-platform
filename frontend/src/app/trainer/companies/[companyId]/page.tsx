import { notFound } from "next/navigation";

import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { CompanyProjectsPanel } from "./CompanyProjectsPanel";

export default async function CompanyOverviewPage({
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

  return (
    <div className="flex flex-col gap-5">
      {company.dataErrors?.map((error) => (
        <InlineFeedback key={error} tone="danger">{error}</InlineFeedback>
      ))}
      <CompanyProjectsPanel
        companyId={companyId}
        initialProjects={company.projects}
        assignments={company.assignments}
      />
    </div>
  );
}
