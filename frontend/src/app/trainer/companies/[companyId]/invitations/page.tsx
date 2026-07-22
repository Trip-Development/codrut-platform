import { notFound } from "next/navigation";

import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyInvitationsWorkspace } from "./LazyInvitationsWorkspace";

export default async function CompanyInvitationsPage({
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
    <LazyInvitationsWorkspace
      companyId={company.id}
      companyName={company.name}
      projects={company.projects}
      selectedProjectId={null}
      participants={company.participants}
      assignments={company.assignments}
      invitationStatuses={company.invitationStatuses}
      teams={company.teams}
      mode="combined"
    />
  );
}
