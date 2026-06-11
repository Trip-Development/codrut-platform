import {
  getCompanyAssignments,
  getCompanyDetail,
  getCompanyInvitationStatuses,
} from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { InvitationsWorkspace } from "./InvitationsWorkspace";

export default async function CompanyInvitationsPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string }>;
  searchParams: Promise<{ projectId?: string }>;
}) {
  const { companyId } = await params;
  const { projectId } = await searchParams;
  const requestOptions = await getServerApiRequestOptions();
  const company = await getCompanyDetail(companyId, requestOptions);
  const selectedProjectId = company?.projects.some((project) => project.id === projectId)
    ? projectId ?? null
    : null;
  const [assignments, invitationStatuses] = selectedProjectId
    ? await Promise.all([
        getCompanyAssignments(companyId, requestOptions, { projectId: selectedProjectId }),
        getCompanyInvitationStatuses(companyId, requestOptions, { projectId: selectedProjectId }),
      ])
    : [company?.assignments ?? [], company?.invitationStatuses ?? []];

  return (
    <InvitationsWorkspace
      companyId={companyId}
      companyName={company?.name ?? "Compania curentă"}
      projects={company?.projects ?? []}
      selectedProjectId={selectedProjectId}
      participants={company?.participants ?? []}
      assignments={assignments}
      invitationStatuses={invitationStatuses}
      teams={company?.teams ?? []}
    />
  );
}
