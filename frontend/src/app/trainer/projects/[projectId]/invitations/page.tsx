import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyInvitationDeliveryWorkspace } from "@/app/trainer/companies/[companyId]/invitations/LazyInvitationsWorkspace";
import { getProjectInvitationWorkspaceData } from "../project-data";

export default async function ProjectInvitationsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const [{ projectId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const data = await getProjectInvitationWorkspaceData(projectId, requestOptions);

  return (
    <LazyInvitationDeliveryWorkspace
      companyId={data.project.company_id}
      companyName={data.project.company_name ?? "Companie"}
      projects={[data.project]}
      selectedProjectId={data.project.id}
      participants={data.participants}
      assignments={data.assignments}
      invitationStatuses={data.invitationStatuses}
      teams={data.teams}
      showProjectSelector={false}
    />
  );
}
