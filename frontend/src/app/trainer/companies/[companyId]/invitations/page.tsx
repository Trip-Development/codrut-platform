import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { InvitationsWorkspace } from "./InvitationsWorkspace";

export default async function CompanyInvitationsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const company = await getCompanyDetail(companyId, await getServerApiRequestOptions());

  return (
    <InvitationsWorkspace
      companyId={companyId}
      companyName={company?.name ?? "Compania curentă"}
      participants={company?.participants ?? []}
      assignments={company?.assignments ?? []}
      invitationStatuses={company?.invitationStatuses ?? []}
      teams={company?.teams ?? []}
    />
  );
}
